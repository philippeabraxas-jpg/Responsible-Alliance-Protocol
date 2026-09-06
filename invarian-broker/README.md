# Invarian Broker (Debian)

Portage Debian du broker INVARIAN. Remplace le Named Pipe Windows par une API
HTTP + WebSocket (FastAPI/uvicorn), pour être appelé directement depuis une
landing page (fenêtre de chat + fenêtre d'injection JSON).

## Dépendances manquantes (à fournir séparément)

Ce fichier importe `shadow_executor.ShadowExecutor` (obligatoire) et
`mcp_plugin_manager.MCPPluginManager` (optionnel, désactivé proprement si
absent). Ces deux modules ne sont pas encore portés/fournis — les déposer à
côté de `broker.py` avant de lancer.

## Lancer

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis remplir GEMINI_API_KEY, ALLOWED_ORIGINS, etc.
python3 broker.py
```

Prérequis externes : OPA sur `OPA_URL` (défaut `http://localhost:8181`) avec
les policies `invarian/core` (et `intent`/`access` si utilisées), Ollama sur
`OLLAMA_URL` pour le modèle local.

## Ce qui a été corrigé par rapport à la version reçue

- **Fail-closed OPA** : une panne OPA bloque désormais la requête (avant :
  le flag `opa_available`, figé au démarrage, faisait sauter toute
  vérification si OPA était down au lancement — bypass total).
- **Bug du fallback Gemini** : la boucle primary/fallback construisait
  toujours l'URL avec un 3e modèle jamais itéré ; le fallback n'était jamais
  réellement appelé.
- **Trou de validation OPA sur les plans** : `move_file`/`create_folder`
  n'envoyaient pas leur chemin à OPA (seuls `write_file`/`read_file`
  l'étaient) — un plan pouvait déplacer/créer hors `WORKSPACE/` sans
  vérification.
- **Clé API Gemini** : passée en header (`x-goog-api-key`) au lieu de la
  query string, pour ne plus apparaître dans les logs/URLs.
- **Kill-switch** : `kill_ia()` (équivalent Debian du `taskkill` Windows sur
  `ollama.exe`) ajouté, déclenché automatiquement sur `alert_level=CRITICAL`
  d'OPA, et exposé manuellement via `POST /api/panic` (protégé par
  `ADMIN_TOKEN`).
- **Transport** : socket Unix brut remplacé par HTTP/WebSocket, avec CORS en
  liste blanche stricte (pas de wildcard), limite de taille de payload,
  rate limiting par IP, et sessions générées côté serveur (un `sid` fourni
  par le client n'est jamais accepté s'il n'a pas été émis par ce serveur —
  anti-IDOR).

## Endpoints

- `GET  /health`
- `POST /api/session` → `{sid}`
- `POST /api/chat` `{sid?, payload}` → `{sid, result}`
- `POST /api/decision` `{sid, choice: "A"|"K"}`
- `GET  /api/result/{sid}`
- `POST /api/panic` (header `X-Admin-Token`)
- `WS   /ws` — `{"type":"chat","payload":...}` / `{"type":"decision","choice":...}`

## Pour une exposition publique sérieuse

L'app fait sa part (CORS, rate limit, taille de payload, fail-closed OPA),
mais pour une vraie landing page en production, mettre un reverse proxy TLS
devant (nginx/Caddy) et garder `BROKER_HOST=127.0.0.1` (ne jamais bind
`0.0.0.0` directement sur une IP publique).
