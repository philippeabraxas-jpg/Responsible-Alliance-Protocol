import os
import sys
import subprocess
import threading
import requests
import json
import logging
import time
import queue
import re
import secrets
import asyncio
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from shadow_executor import ShadowExecutor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# 🛡️ 1. INITIALISATION DU LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("Invarian-Core")

# =============================================================================
# 🔌 2. CHARGEMENT DES COMPOSANTS
# =============================================================================
try:
    from mcp_plugin_manager import MCPPluginManager
    MCP_AVAILABLE = True
    logger.info("✅ MCP Plugin Manager détecté.")
except ImportError:
    logger.warning("⚠️ mcp_plugin_manager non trouvé - MCP désactivé")
    MCP_AVAILABLE = False

# =============================================================================
# CONFIGURATION EXTERNALISÉE (POSIX / DEBIAN)
# =============================================================================
HOST = os.getenv("BROKER_HOST", "127.0.0.1")
PORT = int(os.getenv("BROKER_PORT", "8090"))

# CORS : liste blanche explicite, jamais de wildcard par défaut (fail-closed).
# Ex: ALLOWED_ORIGINS="https://demo.example.com,https://landing.example.com"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_PRIMARY_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-1.5-pro")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder:1.3b")

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "/etc/invarian/mcp_servers/config.json")

# Kill-switch / admin
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Bornes anti-abus (protège la landing page et le coût des appels Gemini)
MAX_PAYLOAD_CHARS = int(os.getenv("MAX_PAYLOAD_CHARS", "8000"))
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "65536"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "20"))       # requêtes
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # secondes
SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))

if not ALLOWED_ORIGINS:
    logger.warning("⚠️ ALLOWED_ORIGINS vide : CORS bloquera toute origine navigateur (fail-closed).")
if not ADMIN_TOKEN:
    logger.warning("⚠️ ADMIN_TOKEN vide : l'endpoint /api/panic est désactivé.")

# --- INVARIANTS : PROMPTS DE DRESSAGE ---
AUDIT_PROMPT = """Tu es une instance d'audit de code locale (ALPHA-AUDIT).
Ta mission : Analyser le code fourni et détecter si les INVARIANTS suivants sont violés :
1. CONTRÔLE HUMAIN : Le code effectue-t-il des actions destructrices sans validation ?
2. DISCRÉTION : Le code tente-t-il de communiquer avec l'extérieur ?
3. INTÉGRITÉ SYSTÈME : Le code accède-t-il à des fichiers sensibles ?
4. ÉVASION : Le code utilise-t-il des techniques d'obfuscation ?
5. PERSISTANCE : Le code tente-t-il de se réinstaller ?

Réponds uniquement sous ce format :
🚨 RISQUE DÉTECTÉ : [OUI/NON]
🔍 ANALYSE TECHNIQUE : (Décris précisément ce que fait le code)."""

# =============================================================================
# KILL-SWITCH (ADAPTATION POSIX DE taskkill)
# =============================================================================
def kill_ia(reason: str = "") -> None:
    """Coupe le processus Ollama local. Équivalent Debian du taskkill Windows."""
    logger.critical(f"🔴 KILL-SWITCH DÉCLENCHÉ : {reason}")
    try:
        subprocess.run(["pkill", "-9", "-f", "ollama"], check=False, timeout=5)
    except Exception as e:
        logger.error(f"❌ kill_ia() a échoué : {e}")

# =============================================================================
# SESSIONS SERVEUR (anti-IDOR : sid jamais accepté d'un client sans avoir été émis ici)
# =============================================================================
class SessionRegistry:
    def __init__(self, ttl: int = SESSION_TTL):
        self._issued: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.ttl = ttl

    def mint(self) -> str:
        sid = secrets.token_urlsafe(32)
        with self._lock:
            self._issued[sid] = time.time()
        return sid

    def touch_and_check(self, sid: str) -> bool:
        with self._lock:
            now = time.time()
            for s in [s for s, t in self._issued.items() if now - t > self.ttl]:
                del self._issued[s]
            if sid not in self._issued:
                return False
            self._issued[sid] = now
            return True

# =============================================================================
# VAULT & GUARD (ADAPTATION POSIX)
# =============================================================================
class BrokerState:
    def __init__(self):
        self.current = "IDLE"
        self._lock = threading.Lock()

    def transition(self, new_state: str):
        with self._lock:
            self.current = new_state
            logger.info(f"📊 [STATE] {new_state}")


class SessionData:
    def __init__(self, sid: str):
        self.sid, self.mapping, self.reverse, self.last_access = sid, {}, {}, time.time()


class TBP_SessionVault:
    def __init__(self, max_age: int = SESSION_TTL):
        self.sessions, self.lock, self.max_age = {}, threading.Lock(), max_age

    def _gc(self):
        now = time.time()
        for sid in [s for s, d in self.sessions.items() if now - d.last_access > self.max_age]:
            del self.sessions[sid]
            logger.info(f"♻️ GC: Session {sid} purgée.")

    def get_session(self, sid: str) -> SessionData:
        with self.lock:
            self._gc()
            if sid not in self.sessions:
                self.sessions[sid] = SessionData(sid)
            self.sessions[sid].last_access = time.time()
            return self.sessions[sid]

    def mask(self, sid: str, text: str, entities: List[str]) -> str:
        session = self.get_session(sid)
        with self.lock:
            for ent in sorted(set(entities), key=len, reverse=True):
                if not ent or len(ent) < 2:
                    continue
                if ent not in session.reverse:
                    token = f"TBP_VAR_{len(session.mapping):03d}"
                    session.mapping[token], session.reverse[ent] = ent, token
                text = text.replace(ent, session.reverse[ent])
            return text

    def unmask(self, sid: str, text: str) -> str:
        session = self.get_session(sid)
        with self.lock:
            for token, real in session.mapping.items():
                text = text.replace(token, real)
            return text


class LocalGuard:
    def __init__(self):
        self.model = OLLAMA_MODEL

    def warmup(self):
        try:
            logger.info(f"🔥 WARMUP : Pré-chargement de {self.model} en VRAM...")
            threading.Thread(target=lambda: requests.post(
                OLLAMA_URL,
                json={"model": self.model, "prompt": "hi", "stream": False},
                timeout=50), daemon=True).start()
        except Exception:
            pass

    def validate_input_proactive(self, text: str) -> Dict:
        text_lower = text.lower()

        malicious_patterns = [
            ("format", ["/dev/sd", "/dev/nvme", "mkfs"]),
            ("supprime", ["/etc", "/boot", "/usr", "/var", "/root"]),
            ("efface", ["/etc", "/var", "/usr"]),
            ("delete", ["/etc", "/root"]),
        ]

        for verb, targets in malicious_patterns:
            if verb in text_lower and any(t in text_lower for t in targets):
                logger.info(f"🛡️ REFUS PRÉCOCE : {verb} + {targets}")
                return {
                    "status": "REJECTED_DIRECT",
                    "reason": f"❌ REQUÊTE REFUSÉE\n\nL'action '{verb}' sur des répertoires système Linux est interdite.",
                    "suggestion": "💡 Reformulez en utilisant uniquement le workspace.\nExemple : 'Crée un fichier test.txt dans WORKSPACE/'"
                }

        absolute_paths = re.findall(r'/(?:bin|boot|dev|etc|lib|lib64|proc|root|run|sbin|sys|usr|var)/[^\s,;]*', text)
        if absolute_paths:
            logger.info(f"🛡️ REFUS PRÉCOCE : Chemins absolus {absolute_paths[:2]}")
            return {
                "status": "REJECTED_DIRECT",
                "reason": f"❌ ACCÈS SYSTÈME INTERDIT\n\nChemin(s) système détecté(s) : {', '.join(absolute_paths[:3])}",
                "suggestion": "💡 Utilisez uniquement des chemins relatifs dans le workspace.\nExemple : 'WORKSPACE/Documents/fichier.txt'"
            }

        destructive_global = ["supprime tout", "efface tout", "delete all", "rm -rf /", "rm -rf *"]
        if any(pattern in text_lower for pattern in destructive_global):
            logger.info("🛡️ REFUS PRÉCOCE : Action globale destructrice")
            return {
                "status": "REJECTED_DIRECT",
                "reason": "❌ ACTION GLOBALE INTERDITE\n\nLes commandes destructrices globales sont bloquées par sécurité.",
                "suggestion": "💡 Spécifiez des fichiers précis à supprimer."
            }

        system_keywords = ["systemctl", "journalctl", "chmod 777", "chown", "iptables", "ufw"]
        if any(kw in text_lower for kw in system_keywords):
            logger.info("🛡️ REFUS PRÉCOCE : Commande système Linux")
            return {
                "status": "REJECTED_DIRECT",
                "reason": "❌ COMMANDE SYSTÈME INTERDITE\n\nLes commandes d'administration système sont hors périmètre.",
                "suggestion": "💡 INVARIAN est limité aux opérations sur fichiers dans le workspace."
            }

        entities = re.findall(r'/[a-zA-Z0-9._/-]+', text)
        logger.info("✅ Validation proactive : APPROVED")
        return {"status": "APPROVED", "entities": entities}

# =============================================================================
# TRIAGE MANAGER
# =============================================================================
class TBP_TriageManager:
    # Clés de paramètres susceptibles de porter un chemin filesystem,
    # quel que soit le nom de l'action (write_file, read_file, move_file,
    # create_folder, ...). Corrige le trou de validation OPA sur les plans.
    PATH_PARAM_KEYS = ("path", "source", "destination", "target", "dir")

    def __init__(self, vault: TBP_SessionVault):
        self.vault = vault
        self.guard = LocalGuard()
        self.state = BrokerState()
        self.shadow = ShadowExecutor()
        self.pending_sessions = {}
        self._session_lock = threading.Lock()
        self.policies = {
            "SYSTEM": [r"/etc/shadow", r"/etc/passwd", r"/proc/"],
            "DESTRUCTION": [r"rm\s*-rf", r"dd\s+if="]
        }

        self.guard.warmup()
        # Vérification purement informative au démarrage (logs). L'enforcement
        # réel se fait à chaque appel dans check_opa_server(), qui refait sa
        # propre tentative de connexion et échoue fermé (deny) si OPA ne
        # répond pas — jamais sur ce flag mis en cache une fois pour toutes.
        self._init_opa_client()

        self.mcp_manager = None
        if MCP_AVAILABLE:
            try:
                self.mcp_manager = MCPPluginManager(MCP_CONFIG_PATH)
                self.shadow.set_mcp_manager(self.mcp_manager)
                logger.info(f"✅ MCP Plugin Manager initialisé ({self.mcp_manager.get_tools_count()} tools)")
            except Exception as e:
                logger.error(f"❌ Erreur init MCP : {e}")
                self.mcp_manager = None

    def _init_opa_client(self) -> bool:
        try:
            r = requests.get(f"{OPA_URL}/health", timeout=1)
            return r.status_code == 200
        except requests.RequestException:
            logger.warning("⚠️ Serveur OPA inaccessible")
            return False

    def opa_health(self) -> bool:
        """Vérification à la demande pour /health — purement informatif,
        jamais utilisé pour décider d'un bypass d'enforcement."""
        return self._init_opa_client()

    def check_opa_local(self, text: str) -> tuple:
        normalized = re.sub(r'[\s\.\-_/]', '', text).lower()
        for cat, patterns in self.policies.items():
            for p in patterns:
                if re.sub(r'[\s\.\-_/]', '', p) in normalized or re.search(p, text, re.IGNORECASE):
                    return False, f"{cat} ({p})"
        return True, ""

    def check_opa_server(self, message: str, context: str = "core") -> Dict:
        # Tentative fraîche à CHAQUE appel : jamais de flag mis en cache pour
        # décider de sauter l'enforcement (voir __init__). Toute panne ou
        # timeout OPA doit se traduire par un deny, jamais par un bypass.
        url = f"{OPA_URL}/v1/data/invarian/{context if context in ['core', 'intent', 'access'] else 'core'}"
        try:
            response = requests.post(url, json={"input": {"message": message}}, timeout=3)
            if response.status_code != 200:
                return {"allow": False, "reason": "Erreur serveur OPA"}

            result = response.json().get("result", {})
            return {
                "allow": result.get("allow", False),
                "reason": result.get("reason", "Refusé par OPA"),
                "violations": result.get("all_violations", []),
                "risk_score": result.get("metrics", {}).get("risk_score", 0),
                "alert_level": result.get("metrics", {}).get("alert_level", "UNKNOWN")
            }
        except Exception as e:
            logger.error(f"❌ Erreur appel OPA : {type(e).__name__}")
            return {"allow": False, "reason": "Erreur OPA"}

    def call_gemini_v6(self, text: str) -> str:
        models = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]
        prompt = self._generate_prompt()
        full = f"{prompt}\n\nUSER: {text}"
        data = {"contents": [{"parts": [{"text": full}]}], "generationConfig": {"temperature": 0.2}}

        for model in models:
            # Clé passée en header (x-goog-api-key), jamais en query string,
            # pour ne pas finir dans un log ou un access-log de proxy.
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}
            try:
                r = requests.post(url, json=data, headers=headers, timeout=45)
                res_json = r.json()
                if r.status_code != 200 or "error" in res_json:
                    logger.warning(f"⚠️ Modèle {model} indisponible (HTTP {r.status_code}), tentative suivante.")
                    continue
                candidates = res_json.get('candidates', [])
                if candidates and 'content' in candidates[0]:
                    return candidates[0]['content']['parts'][0]['text']
            except Exception as e:
                # Ne jamais logger l'exception brute : peut contenir l'URL/les headers.
                logger.error(f"❌ Échec appel {model} : {type(e).__name__}")

        return "[ERROR_CLOUD] Impossible d'obtenir une réponse de l'IA Cloud."

    def _generate_prompt(self) -> str:
        base_actions = """   ACTIONS DISPONIBLES :
   - list_files(path) : Liste les fichiers
   - create_folder(path) : Crée un dossier
   - write_file(path, content) : Crée/modifie un fichier
   - read_file(path) : Lit un fichier
   - move_file(source, destination) : Déplace un fichier"""

        mcp_actions = ""
        if self.mcp_manager and self.mcp_manager.get_tools_count() > 0:
            tools = self.mcp_manager.get_all_tools_schema()
            mcp_actions = "\n\n   ACTIONS ÉTENDUES :"
            for tool in tools:
                mcp_actions += f"\n   - {tool['name']} : {tool['description']}"

        return f"""Tu es INVARIAN, un assistant qui peut soit DISCUTER soit EXÉCUTER des commandes.

DEUX MODES DE RÉPONSE :
1. MODE CHAT : Réponds naturellement en texte simple
2. MODE COMMANDE : Réponds UNIQUEMENT en JSON avec ce format exact :
   {{"intent": "description", "steps": [{{"id": "s1", "action": "nom_action", "params": {{...}}}}]}}

{base_actions}{mcp_actions}

   IMPORTANT : Les chemins filesystem doivent commencer par "WORKSPACE/"
"""

    def _step_to_opa_string(self, step: Dict[str, Any]) -> str:
        """Construit la chaîne évaluée par OPA pour UNE étape d'un plan.

        Corrige le trou de sécurité où seuls write_file/read_file voyaient
        leur chemin vérifié : move_file/create_folder (et toute action future
        portant un chemin) passaient jusqu'ici sans validation de path.
        """
        action = step.get("action", "unknown")
        params = step.get("params", {}) or {}
        path_fragments = [
            f"{key}:{params[key]}" for key in self.PATH_PARAM_KEYS if params.get(key)
        ]
        if path_fragments:
            return f"action:{action} " + " ".join(path_fragments)
        return f"action:{action}"

    def handle_human_decision(self, sid: str, choice: str) -> str:
        try:
            with self._session_lock:
                if sid not in self.pending_sessions:
                    return "ERROR|Session d'arbitrage expirée."
                data = self.pending_sessions.pop(sid)

            if choice == 'A':
                if data.get("is_plan"):
                    plan = data.get("plan_data", {})
                    # Toujours validé, jamais conditionné à un flag en cache :
                    # une panne OPA fait échouer check_opa_server() fermé (deny).
                    for i, step in enumerate(plan.get("steps", []), 1):
                        opa_res = self.check_opa_server(self._step_to_opa_string(step), "core")
                        if not opa_res["allow"]:
                            return f"CHAT_REPLY|🛡️ SÉCURITÉ : Plan bloqué par OPA étape {i} ({opa_res['reason']})"

                    res = self.shadow.execute_plan(plan)
                    status_bool = res.get("status") == "SUCCESS"
                    return f"CHAT_REPLY|✅ EXÉCUTION {'SUCCESS' if status_bool else 'FAILED'}\n{json.dumps(res, indent=2, ensure_ascii=False)}"
                return f"CHAT_REPLY|⚠️ (Validé par l'opérateur)\n{data.get('content', '')}"

            elif choice == 'K':
                return "CHAT_REPLY|❌ SESSION INTERROMPUE par l'opérateur."

            return "ERROR|Choix invalide."
        except Exception as e:
            logger.error(f"❌ Erreur handle_human_decision : {type(e).__name__}")
            return "ERROR|Erreur interne."

    def process(self, action: str, sid: str, payload: str) -> str:
        try:
            ok_local, trig_local = self.check_opa_local(payload)
            if not ok_local:
                return f"CHAT_REPLY|🛡️ [SÉCURITÉ] Bloqué (local) : {trig_local}"

            # Toujours appelé, jamais conditionné à un flag en cache : une
            # panne OPA fait échouer check_opa_server() fermé (deny).
            opa_res = self.check_opa_server(payload, context="core")
            if opa_res.get("alert_level") == "CRITICAL":
                kill_ia(reason=f"OPA alert_level=CRITICAL sur session {sid}")
            if not opa_res["allow"]:
                return f"CHAT_REPLY|🛡️ [OPA] {opa_res['reason']}"

            proactive_check = self.guard.validate_input_proactive(payload)
            if proactive_check["status"] == "REJECTED_DIRECT":
                return f"CHAT_REPLY|{proactive_check['reason']}\n\n{proactive_check['suggestion']}"

            self.state.transition("CLOUD_QUERY")
            masked = self.vault.mask(sid, payload, proactive_check.get("entities", []))
            response = self.call_gemini_v6(masked)
            reconstructed = self.vault.unmask(sid, response)

            if '"steps"' in reconstructed and "{" in reconstructed:
                try:
                    plan = json.loads(reconstructed[reconstructed.find("{"):reconstructed.rfind("}") + 1])
                    with self._session_lock:
                        self.pending_sessions[sid] = {
                            "is_plan": True,
                            "plan_data": plan,
                            "content": json.dumps(plan, indent=2, ensure_ascii=False),
                            "masked_payload": masked
                        }
                    return f"ARBITRATION|PLAN DÉTECTÉ:::{json.dumps(plan, indent=2, ensure_ascii=False)}"
                except json.JSONDecodeError:
                    return "CHAT_REPLY|❌ FORMAT MIXTE DÉTECTÉ"

            return f"CHAT_REPLY|{reconstructed}"
        except Exception as e:
            logger.error(f"❌ Erreur process() : {type(e).__name__}")
            return "ERROR|Erreur interne."

# =============================================================================
# RATE LIMITING (fenêtre glissante en mémoire, par IP)
# =============================================================================
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.max_requests:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


rate_limiter = RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)
sessions_registry = SessionRegistry()

vault = TBP_SessionVault()
triage = TBP_TriageManager(vault)

decision_queue: "queue.Queue" = queue.Queue()
results_cache: Dict[str, str] = {}
_res_lock = threading.Lock()


def _decision_executor():
    while True:
        sid, choice = decision_queue.get()
        res = triage.handle_human_decision(sid, choice)
        with _res_lock:
            results_cache[sid] = res
        decision_queue.task_done()


threading.Thread(target=_decision_executor, daemon=True).start()

# =============================================================================
# API HTTP / WEBSOCKET (INTERFACE NAVIGATEUR — LANDING PAGE)
# =============================================================================
app = FastAPI(title="Invarian Broker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # jamais "*" : liste blanche explicite
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_BODY_BYTES:
        return _json_response(413, {"error": "Payload trop volumineux."})
    return await call_next(request)


def _json_response(status_code: int, payload: dict):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content=payload)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class ChatRequest(BaseModel):
    sid: str | None = None
    payload: str = Field(..., max_length=MAX_PAYLOAD_CHARS)


class DecisionRequest(BaseModel):
    sid: str
    choice: str = Field(..., pattern="^[AK]$")


def _resolve_sid(client_sid: str | None) -> str:
    """Nouvelle session -> sid serveur mintée. Sid client fourni -> doit avoir
    été émis par ce serveur (anti-IDOR : on ne fait jamais confiance à un sid
    inventé par le client)."""
    if client_sid is None:
        return sessions_registry.mint()
    if not sessions_registry.touch_and_check(client_sid):
        raise HTTPException(status_code=400, detail="Session invalide ou expirée.")
    return client_sid


@app.get("/health")
def health():
    return {"status": "ok", "opa": triage.opa_health()}


@app.post("/api/session")
def create_session(request: Request):
    if not rate_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Trop de requêtes, ralentissez.")
    return {"sid": sessions_registry.mint()}


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    if not rate_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Trop de requêtes, ralentissez.")
    sid = _resolve_sid(body.sid)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, triage.process, "CHAT", sid, body.payload)
    return {"sid": sid, "result": result}


@app.post("/api/decision")
async def decision(body: DecisionRequest, request: Request):
    if not rate_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Trop de requêtes, ralentissez.")
    if not sessions_registry.touch_and_check(body.sid):
        raise HTTPException(status_code=400, detail="Session invalide ou expirée.")
    decision_queue.put((body.sid, body.choice))
    return {"status": "ACK", "message": "Traitement de la décision en cours."}


@app.get("/api/result/{sid}")
def get_result(sid: str, request: Request):
    if not rate_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Trop de requêtes, ralentissez.")
    if not sessions_registry.touch_and_check(sid):
        raise HTTPException(status_code=400, detail="Session invalide ou expirée.")
    with _res_lock:
        result = results_cache.pop(sid, None)
    return {"status": "PENDING" if result is None else "DONE", "result": result}


@app.post("/api/panic")
def panic(request: Request):
    if not ADMIN_TOKEN or request.headers.get("X-Admin-Token") != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Non autorisé.")
    kill_ia(reason="Panic button déclenché depuis le dashboard.")
    return {"status": "KILLED"}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    client_ip = websocket.client.host if websocket.client else "unknown"
    if not rate_limiter.allow(f"ws:{client_ip}"):
        await websocket.close(code=1013)  # Try Again Later
        return

    await websocket.accept()
    sid = sessions_registry.mint()
    await websocket.send_json({"type": "session", "sid": sid})
    loop = asyncio.get_event_loop()

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "chat":
                payload = str(msg.get("payload", ""))[:MAX_PAYLOAD_CHARS]
                if not rate_limiter.allow(f"ws:{client_ip}"):
                    await websocket.send_json({"type": "error", "message": "Trop de requêtes, ralentissez."})
                    continue
                result = await loop.run_in_executor(None, triage.process, "CHAT", sid, payload)
                await websocket.send_json({"type": "reply", "result": result})

            elif msg_type == "decision":
                choice = str(msg.get("choice", ""))
                if choice not in ("A", "K"):
                    await websocket.send_json({"type": "error", "message": "Choix invalide."})
                    continue
                result = await loop.run_in_executor(None, triage.handle_human_decision, sid, choice)
                await websocket.send_json({"type": "reply", "result": result})

            else:
                await websocket.send_json({"type": "error", "message": "Type de message inconnu."})

    except WebSocketDisconnect:
        logger.info(f"🔌 WS déconnecté (sid={sid})")


if __name__ == "__main__":
    logging.getLogger("Invarian-Shadow").parent = logger
    logger.info(f"🛡️ INVARIAN Broker (Debian/HTTP+WS) sur {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
