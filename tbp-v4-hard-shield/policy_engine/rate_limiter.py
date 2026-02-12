import time
from collections import defaultdict
from typing import Dict, List, Optional
import logging

# Configuration des logs standards pour le suivi opérationnel
logger = logging.getLogger("tbp.rate_limiter")

class RateLimiter:
    """
    Rate Limiter Identity-Aware pour le protocole TBP v4.2.1.
    Protège les ressources cryptographiques (HSM) et logiques (OPA).
    """
    
    def __init__(self, audit_chain=None, window_seconds: int = 60):
        """
        Initialise le limiteur avec une fenêtre de temps glissante.
        
        Args:
            audit_chain: Instance de MerkleAuditChain pour l'ancrage des alertes.
            window_seconds: Taille de la fenêtre d'analyse (défaut: 60s).
        """
        self.audit_chain = audit_chain
        self.window_seconds = window_seconds
        
        # Seuils par défaut (Configurables pour le mode Corporate)
        self.limits = {
            "sign": 50,    # Protection physique du HSM
            "verify": 1000, # Protection du moteur de règles
            "default": 100
        }
        
        # Historique en mémoire : agent_id -> {action: [timestamps]}
        self._history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    def _clean_old_requests(self, agent_id: str, action: str, now: float):
        """Nettoie les timestamps expirés pour optimiser la mémoire."""
        self._history[agent_id][action] = [
            ts for ts in self._history[agent_id][action] 
            if now - ts < self.window_seconds
        ]

    def check_limit(self, agent_id: str, action: str = "default") -> bool:
        """
        Vérifie si l'agent a encore du quota pour l'action demandée.
        
        Returns:
            bool: True si autorisé, False si le seuil est dépassé (déclenche un log Merkle).
        """
        now = time.time()
        limit = self.limits.get(action, self.limits["default"])
        
        # 1. Nettoyage de la fenêtre glissante
        self._clean_old_requests(agent_id, action, now)
        
        # 2. Vérification du quota
        current_count = len(self._history[agent_id][action])
        
        if current_count >= limit:
            self._trigger_dos_alert(agent_id, action, current_count)
            return False
            
        # 3. Enregistrement de la requête
        self._history[agent_id][action].append(now)
        return True

    def _trigger_dos_alert(self, agent_id: str, action: str, count: int):
        """Journalise l'alerte de sabotage dans la chaîne de Merkle."""
        alert_data = {
            "event": "DoS_ALERT",
            "agent_id": agent_id,
            "action": action,
            "request_count": count,
            "threshold": self.limits.get(action),
            "severity": "CRITICAL" if action == "sign" else "HIGH"
        }
        
        logger.warning(f"Rate limit exceeded for agent {agent_id} on action {action}")
        
        if self.audit_chain:
            try:
                # Ancrage immuable de la tentative de sabotage
                self.audit_chain.append(alert_data)
            except Exception as e:
                logger.error(f"Failed to log DoS_ALERT to Merkle Chain: {e}")

    def get_stats(self, agent_id: str) -> Dict[str, int]:
        """Retourne l'utilisation actuelle des quotas pour un agent."""
        return {action: len(ts_list) for action, ts_list in self._history[agent_id].items()}
