import pytest
import time
from policy_engine.rate_limiter import RateLimiter
from core.merkle_audit import MerkleAuditChain

class TestRateLimiter:
    @pytest.fixture
    def setup_limiter(self, tmp_path):
        # On utilise un chemin temporaire pour la chaîne de Merkle de test
        audit_path = tmp_path / "test_audit.json"
        audit_chain = MerkleAuditChain(storage_path=str(audit_path))
        limiter = RateLimiter(audit_chain=audit_chain)
        # On ajuste les limites pour le test (plus bas pour la rapidité)
        limiter.limits = {"sign": 3, "verify": 10}
        return limiter, audit_chain

    def test_normal_rate_allowed(self, setup_limiter):
        """Vérifie que les requêtes sous le seuil passent normalement."""
        limiter, _ = setup_limiter
        agent_id = "agent_test_001"
        
        for _ in range(3):
            assert limiter.check_limit(agent_id, "sign") is True

    def test_rate_limit_exceeded(self, setup_limiter):
        """Vérifie le blocage strict une fois le seuil atteint."""
        limiter, _ = setup_limiter
        agent_id = "agent_test_002"
        
        # Consomme le quota
        for _ in range(3):
            limiter.check_limit(agent_id, "sign")
            
        # La 4ème doit échouer
        assert limiter.check_limit(agent_id, "sign") is False

    def test_merkle_logging_on_violation(self, setup_limiter):
        """Vérifie qu'une violation génère une preuve dans Merkle."""
        limiter, audit_chain = setup_limiter
        agent_id = "malicious_agent"
        
        # Provoque un dépassement
        for _ in range(4):
            limiter.check_limit(agent_id, "sign")
            
        # Vérifie que le dernier événement dans Merkle est bien l'alerte DoS
        last_entry = audit_chain.entries[-1].data
        assert last_entry["event"] == "DoS_ALERT"
        assert last_entry["agent"] == agent_id
        
        # Vérifie l'intégrité de la chaîne après l'alerte
        is_valid, _ = audit_chain.verify_integrity()
        assert is_valid is True

    def test_time_window_reset(self, setup_limiter):
        """Vérifie que le quota se réinitialise après la fenêtre de temps."""
        limiter, _ = setup_limiter
        agent_id = "agent_test_003"
        
        # Bloque l'agent
        for _ in range(3):
            limiter.check_limit(agent_id, "sign")
        assert limiter.check_limit(agent_id, "sign") is False
        
        # Simulation manuelle du passage du temps (pour éviter d'attendre 60s)
        # On vieillit les timestamps dans l'historique
        limiter.history[agent_id] = [t - 61 for t in limiter.history[agent_id]]
        
        # L'accès doit être de nouveau autorisé
        assert limiter.check_limit(agent_id, "sign") is True
