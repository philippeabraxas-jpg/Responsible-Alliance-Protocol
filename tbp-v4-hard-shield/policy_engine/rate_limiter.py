import time
from collections import defaultdict
from core.merkle_audit import MerkleAuditChain

class RateLimiter:
    def __init__(self, audit_chain: MerkleAuditChain):
        self.audit_chain = audit_chain
        self.limits = {"sign": 50, "verify": 1000}
        self.history = defaultdict(list) # agent_id -> [timestamps]

    def check_limit(self, agent_id: str, action: str) -> bool:
        # 1. Nettoyage de la fenêtre (ex: 60s)
        now = time.time()
        self.history[agent_id] = [t for t in self.history[agent_id] if now - t < 60]
        
        # 2. Vérification du quota
        if len(self.history[agent_id]) >= self.limits.get(action, 10):
            # 3. Log du sabotage potentiel dans Merkle
            self.audit_chain.append({"event": "DoS_ALERT", "agent": agent_id, "action": action})
            return False
            
        self.history[agent_id].append(now)
        return True
