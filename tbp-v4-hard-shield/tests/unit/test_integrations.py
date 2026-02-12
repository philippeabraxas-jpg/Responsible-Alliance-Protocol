import pytest
from unittest.mock import MagicMock, patch
import json

# Skip if dependencies are missing
pytest.importorskip("langchain")

from integrations.langchain_v4_2 import TBPEnforcer, TBPEnforcementError, TBPTradingTool
from integrations.backward_v4_1 import TBPLogSigner, MigrationHelper


class TestLangChainIntegration:
    @pytest.fixture
    def enforcer(self, tmp_path):
        config = {
            "hsm": {"hsm_type": "software"},
            "storage_path": str(tmp_path / "langchain_audit.json"),
        }
        return TBPEnforcer(audit_config=config)

    def test_check_action_allowed(self, enforcer):
        with patch("requests.post") as mock_post:
            # Mock OPA allow
            mock_allow = MagicMock()
            mock_allow.json.return_value = {"result": True}
            mock_allow.status_code = 200

            # Mock OPA log
            mock_log = MagicMock()
            mock_log.json.return_value = {"result": {"allowed": True}}
            mock_log.status_code = 200

            mock_post.side_effect = [mock_allow, mock_log]

            result = enforcer.check_action("finance", "trade", amount=100)
            assert result["allowed"] is True
            assert "audit_proof" in result

    def test_check_action_blocked(self, enforcer):
        with patch("requests.post") as mock_post:
            mock_allow = MagicMock()
            mock_allow.json.return_value = {"result": False}
            mock_post.return_value = mock_allow

            with pytest.raises(TBPEnforcementError):
                enforcer.check_action("finance", "trade", amount=1000000)


class TestBackwardCompatibility:
    def test_sign_log_v42_mode(self, tmp_path):
        signer = TBPLogSigner(storage_path=str(tmp_path / "legacy_audit.json"))
        assert signer.mode == "v4.2-hsm"

        log_data = {"event": "legacy_op", "user": "alice"}
        result = signer.sign_log(log_data)

        assert result["version"] == "4.2-compat"
        assert "merkle_root" in result
        assert result["audit_index"] == 0

    def test_migration_helper(self, tmp_path):
        signer = TBPLogSigner(storage_path=str(tmp_path / "migrate_audit.json"))
        helper = MigrationHelper(signer)

        old_logs = [
            {"timestamp": "2026-01-01T10:00:00Z", "data": "op1"},
            {"timestamp": "2026-01-01T10:05:00Z", "data": "op2"},
        ]

        new_logs = helper.migrate_file(old_logs)
        assert len(new_logs) == 2
        assert len(signer.chain) == 2
        assert new_logs[0]["audit_index"] == 0
        assert new_logs[1]["audit_index"] == 1
