import pytest
import json
from datetime import datetime, timezone
from core.tbp_signature_service import TBPFullAuditSystem


class TestTBPFullAuditSystem:
    @pytest.fixture
    def config(self, tmp_path):
        return {
            "hsm": {"hsm_type": "software"},
            "storage_path": str(tmp_path / "audit.json"),
            "tsa": {"enabled": False},
        }

    def test_init(self, config):
        system = TBPFullAuditSystem(config)
        assert system.hsm_signer is not None
        assert system.audit_chain is not None
        assert system.time_attester is None

    def test_log_decision(self, config):
        system = TBPFullAuditSystem(config)
        decision = {"action": "trade", "symbol": "BTC", "amount": 1.0}
        agent_id = "agent-001"
        context = {"ip": "127.0.0.1", "session": "xyz"}

        result = system.log_decision(decision, agent_id, context)

        assert "entry_hash" in result
        assert "root_hash" in result
        assert "signature" in result
        assert result["merkle_index"] == 0

        # Verify it was actually stored
        assert len(system.audit_chain) == 1
        entry = system.audit_chain[0]
        assert entry.data["decision"] == decision
        assert entry.data["agent_id"] == agent_id

    def test_tsa_integration_mocked(self, config):
        from unittest.mock import MagicMock, patch

        config["tsa"]["enabled"] = True
        config["require_tsa"] = True

        with patch("core.time_attester.TimeAttester") as mock_attester:
            mock_instance = MagicMock()
            mock_attester.return_value = mock_instance
            mock_instance.get_timestamp.return_value.to_dict.return_value = {"token": "fake"}

            system = TBPFullAuditSystem(config)
            # Override just in case init didn't catch it due to mock timing
            system.time_attester = mock_instance

            decision = {"test": "data"}
            result = system.log_decision(decision, "agent-1", {})

            assert result["tsa_token"] == {"token": "fake"}
            assert mock_instance.get_timestamp.called
