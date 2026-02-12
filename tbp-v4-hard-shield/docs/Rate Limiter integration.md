🛡️ Rate Limiter + HSM Protection Guide
Overview

Le Rate Limiter protège les ressources critiques du TBP (notamment le processeur physique du HSM) contre la saturation. Contrairement à un limiteur classique, il est Agent-Aware : il utilise l'identité cryptographique issue du HSM pour appliquer des quotas par agent.
Architecture

┌─────────────────┐
│  Agent Request  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│    Rate Limiter     │  ◄── Protège le HSM (v4.2.1)
│ (rate_limiter.py)   │
└────────┬────────────┘
         │
         │ Token Validé ?
         ▼
┌─────────────────────┐
│     HSM Signer      │  ◄── Opération coûteuse
│  (hsm_signer.py)    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│    Audit System     │
│   (Merkle Chain)    │  ◄── Log les alertes DoS
└─────────────────────┘

Python Integration (Middleware Pattern)
Implémentation du TBPEnforcer avec Protection HSM
Python

from policy_engine.rate_limiter import RateLimiter
from core.hsm_signer import HSMSigner
from core.merkle_audit import MerkleAuditChain

class SecureTBPEnforcer:
    """
    Enforcer sécurisé intégrant le Rate Limiting et la protection HSM.
    """
    def __init__(self, hsm: HSMSigner, audit_chain: MerkleAuditChain):
        self.hsm = hsm
        self.audit_chain = audit_chain
        # Initialisation du limiteur lié à la chaîne d'audit
        self.limiter = RateLimiter(audit_chain=self.audit_chain)
        
    def sign_action(self, agent_id: str, action_data: dict):
        """
        Signe une action après vérification des quotas.
        """
        # 1. Vérification du Rate Limit AVANT d'appeler le HSM
        if not self.limiter.check_limit(agent_id, action="sign"):
            # L'alerte est déjà logguée dans Merkle par le limiter
            raise PermissionError(f"HSM Protection: Rate limit exceeded for agent {agent_id}")

        # 2. Si OK, on procède à la signature physique
        return self.hsm.sign(action_data, agent_id=agent_id)

# Usage
enforcer = SecureTBPEnforcer(hsm=my_hsm, audit_chain=my_chain)

try:
    sig = enforcer.sign_action("bot-001", {"amount": 1000})
except PermissionError as e:
    print(f"🚨 Sabotage bloqué : {e}")

Configuration des Quotas (Corporate Standard)

Dans rate_limiter.py, nous utilisons des seuils différenciés pour équilibrer agilité et sécurité.
Ressource	Action	Seuil (Default)	Justification
HSM (Sign)	sign	50 req / min	Protège la puce physique contre l'échauffement/usure.
OPA (Verify)	verify	1000 req / min	Protège le CPU contre les attaques par déni de service logique.
Audit (Log)	log	2000 req / min	Empêche la saturation de l'espace disque de l'audit.
OPA Integration (Optionnel)

Vous pouvez également passer l'état du Rate Limiter à OPA pour des décisions plus fines :
Extrait de code

package tbp.resilience

# Bloque l'action si le Rate Limiter a détecté une anomalie persistante
deny[msg] if {
    input.rate_limit_status.is_flagged == true
    msg := "Agent under temporary quarantine due to excessive requests."
}

Deployment Checklist

    [ ] Placer rate_limiter.py dans policy_engine/

    [ ] Injecter la MerkleAuditChain dans le constructeur du RateLimiter

    [ ] Configurer les seuils selon les capacités du HSM (YubiKey vs CloudHSM)

    [ ] Ajouter les tests unitaires (test_rate_limiter.py) au pipeline CI/CD

    [ ] Vérifier que DoS_ALERT remonte bien dans le dashboard de surveillance

Monitoring & Alerting

Le RateLimiter génère des entrées spécifiques dans la chaîne de Merkle. Voici comment les filtrer pour la surveillance :
Python

# Exemple de requête de surveillance
alerts = [e for e in chain.entries if e.data.get("event") == "DoS_ALERT"]
if len(alerts) > 10:
    trigger_admin_alert("Potential coordinated attack detected in Merkle Chain")
