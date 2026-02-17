🛡️ Rate Limiter + HSM Protection Guide
Overview

Le Rate Limiter est un composant de résilience technique conçu pour protéger les ressources critiques du TBP — en particulier le processeur physique du HSM — contre la saturation ou le sabotage. Contrairement à un limiteur classique, il est Agent-Aware : il utilise l'identité cryptographique (agent_id) issue du HSM pour appliquer des quotas par agent.
Architecture
Extrait de code

graph TD
    A[Agent Request] --> B{Rate Limiter}
    B -- Limit Exceeded --> C[Log DoS_ALERT to Merkle]
    B -- Allowed --> D[HSM Signer]
    D --> E[Record Signature in Merkle]

Flux :

    La requête de l'agent arrive.

    Le Rate Limiter vérifie les compteurs en mémoire pour cet agent_id.

    Si le seuil est dépassé : l'action est bloquée et une alerte DoS_ALERT est inscrite dans la Merkle Audit Chain.

    Si le seuil est respecté : l'appel au HSM Signer est autorisé.

OPA & Integration Logic
Protection des ressources physiques

Le Rate Limiter agit comme une sentinelle avant l'entrée dans le moteur de politiques (OPA) ou l'appel au matériel (HSM).

Configuration des seuils (v4.2.1) :
Ressource	Action	Seuil (Secteur Public/Banque)	Justification
HSM	sign	50 req/min	Évite la surchauffe/usure des puces physiques (YubiKey/CloudHSM).
Enforcer	verify	1000 req/min	Empêche le déni de service logique sur le serveur de politiques.
Audit	append	2000 req/min	Protège l'espace disque du journal d'audit Merkle.
Python Integration
Option 1: Middleware / Enforcer Pattern
Python

from policy_engine.rate_limiter import RateLimiter
from core.hsm_signer import HSMSigner
from core.merkle_audit import MerkleAuditChain

class TBPEnforcer:
    """
    Enforcer TBP avec protection anti-DoS intégrée.
    """
    def __init__(self, hsm: HSMSigner, audit_chain: MerkleAuditChain):
        self.hsm = hsm
        self.audit_chain = audit_chain
        # Le limiter est directement lié à la chaîne d'audit
        self.limiter = RateLimiter(audit_chain=self.audit_chain)
    
    def secure_sign(self, agent_id: str, data: dict):
        """
        Signe une donnée uniquement si l'agent respecte ses quotas.
        """
        if not self.limiter.check_limit(agent_id, action="sign"):
            # L'alerte DoS_ALERT est déjà inscrite dans Merkle par le limiter
            raise PermissionError(f"HSM Protection triggered: Agent {agent_id} rate-limited.")
            
        return self.hsm.sign(data, agent_id=agent_id)

Option 2: Decorator Pattern (Expert)
Python

from functools import wraps
from policy_engine.rate_limiter import RateLimiter

# Global limiter instance
_limiter = RateLimiter(audit_chain=global_audit_chain)

def protect_hsm(func):
    """
    Décorateur pour protéger les méthodes consommant du HSM.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        agent_id = getattr(self, 'agent_id', 'unknown')
        
        if not _limiter.check_limit(agent_id, action="sign"):
            raise PermissionError(f"Rate limit exceeded for {agent_id}")
            
        return func(self, *args, **kwargs)
    return wrapper

Testing & Validation
Test : Détection de Sabotage
Python

def test_hsm_saturation_protection():
    limiter = RateLimiter(audit_chain=mock_chain)
    agent_id = "attacker_bot"
    
    # Simulation d'une attaque par saturation (Flood)
    for i in range(100):
        limiter.check_limit(agent_id, action="sign")
        
    # Vérification que le système a réagi
    assert limiter.check_limit(agent_id, action="sign") is False
    assert mock_chain.last_entry.data["event"] == "DoS_ALERT"

Deployment Checklist

    [ ] Installer rate_limiter.py dans le répertoire policy_engine/.

    [ ] Configurer les limites dans le fichier de config (défaut : 50 sign/min).

    [ ] S'assurer que chaque rejet (False) est bien suivi d'un append dans la MerkleAuditChain.

    [ ] Tester la réinitialisation de la fenêtre de temps (Time Window Reset).

Performance Considerations

    Latence : L'impact sur la requête est négligeable (< 1ms) car les compteurs sont en mémoire.

    Nettoyage : La liste des timestamps par agent est purgée à chaque appel pour éviter les fuites de mémoire.

    Persistance : En cas de redémarrage, les compteurs sont remis à zéro (comportement standard pour protéger la disponibilité).

Ce document fait partie de la documentation officielle du Teleological Bounding Protocol v4.2.1.
