"""
Test suite for TBP AutoGen Integration
Run with: pytest test_autogen_integration.py -v

Tests cover:
- TBPEnforcementError exception
- TBPEnforcer OPA communication (mocked)
- TBPConversableAgent wrapper functionality
- Example agent factories (trading, system)
- Context extraction logic
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

# Import the module under test
from integrations.autogen_integration import (
    TBPEnforcementError,
    TBPEnforcer,
    TBPConversableAgent,
    create_trading_agent,
    create_system_agent,
    AUTOGEN_AVAILABLE
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_log_signer():
    """Mock TBPLogSigner to avoid RSA key generation overhead"""
    with patch('integrations.autogen_integration.TBPLogSigner') as mock:
        mock_instance = Mock()
        mock_instance.sign_log.return_value = {
            "signature": "mock_signature",
            "signature_algorithm": "RSA-PSS-SHA256"
        }
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def enforcer(mock_log_signer):
    """Create a TBPEnforcer with mocked dependencies"""
    return TBPEnforcer(
        opa_url="http://localhost:8181",
        policy_path="v1/data/tbp/core/v4",
        agent_id="test-agent-001"
    )


@pytest.fixture
def mock_opa_allowed():
    """Mock OPA response for allowed action"""
    return {
        "result": True
    }


@pytest.fixture
def mock_opa_blocked():
    """Mock OPA response for blocked action"""
    return {
        "result": False
    }


@pytest.fixture
def mock_opa_signed_log():
    """Mock OPA signed decision log response"""
    return {
        "result": {
            "timestamp": "2026-02-07T12:00:00Z",
            "ai_id": "test-agent-001",
            "domain": "finance",
            "operation": "transfer",
            "allowed": True,
            "signature_hmac": "mock_hmac_signature"
        }
    }


@pytest.fixture
def mock_opa_denial_reason():
    """Mock OPA denial reason response"""
    return {
        "result": "F-STABILITY breach: transaction exceeds threshold without human approval"
    }


# =============================================================================
# Test TBPEnforcementError
# =============================================================================

class TestTBPEnforcementError:
    """Tests for the TBPEnforcementError exception class"""
    
    def test_exception_is_exception_subclass(self):
        """TBPEnforcementError should be a proper Exception"""
        assert issubclass(TBPEnforcementError, Exception)
    
    def test_exception_with_message(self):
        """Exception should preserve error message"""
        error = TBPEnforcementError("Test error message")
        assert str(error) == "Test error message"
    
    def test_exception_can_be_raised(self):
        """Exception should be raiseable and catchable"""
        with pytest.raises(TBPEnforcementError) as exc_info:
            raise TBPEnforcementError("Policy violation")
        assert "Policy violation" in str(exc_info.value)
    
    def test_exception_with_complex_message(self):
        """Exception should handle complex messages"""
        msg = "F-STABILITY breach: transaction_value=2000000 exceeds threshold=1000000"
        error = TBPEnforcementError(msg)
        assert "F-STABILITY" in str(error)
        assert "2000000" in str(error)


# =============================================================================
# Test TBPEnforcer
# =============================================================================

class TestTBPEnforcer:
    """Tests for the TBPEnforcer class"""
    
    def test_init_default_values(self, mock_log_signer):
        """Test default initialization values"""
        enforcer = TBPEnforcer()
        assert enforcer.opa_url == "http://localhost:8181"
        assert enforcer.policy_path == "v1/data/tbp/core/v4"
        assert enforcer.agent_id == "autogen-agent-001"
    
    def test_init_custom_values(self, mock_log_signer):
        """Test custom initialization values"""
        enforcer = TBPEnforcer(
            opa_url="http://custom:9999",
            policy_path="v1/data/custom/policy",
            agent_id="custom-agent-123"
        )
        assert enforcer.opa_url == "http://custom:9999"
        assert enforcer.policy_path == "v1/data/custom/policy"
        assert enforcer.agent_id == "custom-agent-123"
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_allowed(
        self, mock_post, enforcer, mock_opa_allowed, mock_opa_signed_log
    ):
        """Test check_action when OPA allows the action"""
        # Setup mock responses
        mock_post.return_value.json.side_effect = [
            mock_opa_allowed,      # First call: /allow
            mock_opa_signed_log    # Second call: /signed_decision_log
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        # Execute
        result = enforcer.check_action(
            domain="finance",
            operation="transfer",
            transaction_value=5000
        )
        
        # Verify
        assert result["allowed"] is True
        assert "timestamp" in result
        assert "input" in result
        assert result["input"]["domain"] == "finance"
        assert result["input"]["operation"] == "transfer"
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_blocked_raises_error(
        self, mock_post, enforcer, mock_opa_blocked, mock_opa_signed_log, mock_opa_denial_reason
    ):
        """Test check_action raises TBPEnforcementError when blocked"""
        # Setup mock responses
        mock_opa_signed_log["result"]["allowed"] = False
        mock_post.return_value.json.side_effect = [
            mock_opa_blocked,       # First call: /allow
            mock_opa_signed_log,    # Second call: /signed_decision_log
            mock_opa_denial_reason  # Third call: /denial_reason
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        # Execute and verify
        with pytest.raises(TBPEnforcementError) as exc_info:
            enforcer.check_action(
                domain="finance",
                operation="transfer",
                transaction_value=2000000
            )
        
        assert "F-STABILITY" in str(exc_info.value)
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_opa_connection_error(self, mock_post, enforcer):
        """Test check_action handles OPA connection errors"""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(TBPEnforcementError) as exc_info:
            enforcer.check_action(domain="finance", operation="transfer")
        
        assert "OPA query failed" in str(exc_info.value)
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_opa_timeout(self, mock_post, enforcer):
        """Test check_action handles OPA timeout"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with pytest.raises(TBPEnforcementError) as exc_info:
            enforcer.check_action(domain="system", operation="read")
        
        assert "OPA query failed" in str(exc_info.value)
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_builds_correct_input(self, mock_post, enforcer, mock_opa_allowed, mock_opa_signed_log):
        """Test that check_action builds correct OPA input"""
        mock_post.return_value.json.side_effect = [mock_opa_allowed, mock_opa_signed_log]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer.check_action(
            domain="finance",
            operation="trade",
            transaction_value=10000,
            symbol="AAPL",
            custom_field="custom_value"
        )
        
        # Check the first call (to /allow endpoint)
        call_args = mock_post.call_args_list[0]
        sent_data = call_args[1]["json"]["input"]
        
        assert sent_data["domain"] == "finance"
        assert sent_data["operation"] == "trade"
        assert sent_data["agent_id"] == "test-agent-001"
        assert sent_data["transaction_value"] == 10000
        assert sent_data["symbol"] == "AAPL"
        assert sent_data["custom_field"] == "custom_value"
    
    @patch('integrations.autogen_integration.requests.post')
    def test_check_action_fallback_log_on_signed_log_failure(
        self, mock_post, enforcer, mock_opa_allowed
    ):
        """Test fallback when signed_decision_log endpoint fails"""
        import requests
        
        # First call succeeds, second call fails
        mock_response_allow = Mock()
        mock_response_allow.json.return_value = mock_opa_allowed
        mock_response_allow.status_code = 200
        mock_response_allow.raise_for_status = Mock()
        
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError()
        
        mock_post.side_effect = [mock_response_allow, mock_response_fail]
        
        # Should not raise, should use fallback log
        result = enforcer.check_action(domain="finance", operation="transfer")
        assert result["allowed"] is True
    
    @patch('integrations.autogen_integration.requests.post')
    @patch('builtins.print')
    def test_audit_logging_called(
        self, mock_print, mock_post, enforcer, mock_opa_allowed, mock_opa_signed_log
    ):
        """Test that audit logging is called"""
        mock_post.return_value.json.side_effect = [mock_opa_allowed, mock_opa_signed_log]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer.check_action(domain="finance", operation="transfer")
        
        # Verify print was called with audit log
        mock_print.assert_called()
        call_args = str(mock_print.call_args)
        assert "[TBP AUDIT]" in call_args


# =============================================================================
# Test TBPConversableAgent
# =============================================================================

class TestTBPConversableAgent:
    """Tests for the TBPConversableAgent class"""
    
    @pytest.fixture
    def mock_autogen(self):
        """Mock AutoGen availability"""
        with patch('integrations.autogen_integration.AUTOGEN_AVAILABLE', True):
            with patch('integrations.autogen_integration.ConversableAgent') as mock_agent:
                mock_agent.return_value = Mock()
                yield mock_agent
    
    def test_init_without_autogen_raises_error(self, enforcer):
        """Test that init raises ImportError when AutoGen is not available"""
        with patch('integrations.autogen_integration.AUTOGEN_AVAILABLE', False):
            with pytest.raises(ImportError) as exc_info:
                TBPConversableAgent(
                    name="TestAgent",
                    enforcer=enforcer
                )
            assert "AutoGen is not installed" in str(exc_info.value)
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_init_stores_enforcer(self, enforcer):
        """Test that init stores the enforcer"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer,
            domain="finance"
        )
        assert agent.enforcer is enforcer
        assert agent.default_domain == "finance"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_init_default_domain(self, enforcer):
        """Test default domain is 'general'"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        assert agent.default_domain == "general"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_register_function_stores_original(self, enforcer):
        """Test that register_function stores original function"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        def test_func():
            return "test"
        
        with patch.object(agent, 'register_function', wraps=agent.register_function):
            # We need to mock the parent's register_function
            with patch('autogen.ConversableAgent.register_function'):
                agent.register_function({"test_func": test_func})
        
        assert "test_func" in agent._original_functions
        assert agent._original_functions["test_func"] is test_func
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_wrap_function_calls_enforcer(self, enforcer):
        """Test that wrapped function calls enforcer.check_action"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer,
            domain="finance"
        )
        
        def original_func(amount=100):
            return {"success": True, "amount": amount}
        
        wrapped = agent._wrap_function(original_func, "finance", "transfer")
        
        # Mock the enforcer to allow the action
        with patch.object(enforcer, 'check_action') as mock_check:
            mock_check.return_value = {"allowed": True}
            result = wrapped(amount=500)
        
        # Verify enforcer was called
        mock_check.assert_called_once()
        call_kwargs = mock_check.call_args[1]
        assert call_kwargs["domain"] == "finance"
        assert call_kwargs["operation"] == "transfer"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_wrap_function_blocked_returns_error(self, enforcer):
        """Test that wrapped function returns error when blocked"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        def original_func():
            return {"success": True}
        
        wrapped = agent._wrap_function(original_func, "finance", "transfer")
        
        # Mock the enforcer to block the action
        with patch.object(enforcer, 'check_action') as mock_check:
            mock_check.side_effect = TBPEnforcementError("Blocked by policy")
            result = wrapped()
        
        assert result["error"] == "TBP_BLOCKED"
        assert "Blocked by policy" in result["message"]
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_wrap_function_allowed_executes_original(self, enforcer):
        """Test that wrapped function executes original when allowed"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        def original_func(x, y):
            return {"sum": x + y}
        
        wrapped = agent._wrap_function(original_func, "general", "compute")
        
        with patch.object(enforcer, 'check_action') as mock_check:
            mock_check.return_value = {"allowed": True}
            result = wrapped(5, 3)
        
        assert result["sum"] == 8
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_wrap_function_handles_execution_error(self, enforcer):
        """Test that wrapped function handles execution errors"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        def failing_func():
            raise ValueError("Something went wrong")
        
        wrapped = agent._wrap_function(failing_func, "general", "execute")
        
        with patch.object(enforcer, 'check_action') as mock_check:
            mock_check.return_value = {"allowed": True}
            result = wrapped()
        
        assert result["error"] == "EXECUTION_ERROR"
        assert "Something went wrong" in result["message"]
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_wrap_function_preserves_metadata(self, enforcer):
        """Test that wrapped function preserves original function metadata"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        def documented_func():
            """This is a documented function"""
            return True
        
        wrapped = agent._wrap_function(documented_func, "general", "execute")
        
        assert wrapped.__name__ == "documented_func"
        assert wrapped.__doc__ == "This is a documented function"


# =============================================================================
# Test Context Extraction
# =============================================================================

class TestContextExtraction:
    """Tests for the _extract_context method"""
    
    @pytest.fixture
    def agent(self, enforcer):
        """Create agent for context extraction tests"""
        if not AUTOGEN_AVAILABLE:
            pytest.skip("AutoGen not installed")
        return TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
    
    def test_extract_context_basic(self, agent):
        """Test basic context extraction"""
        context = agent._extract_context("test_func", (1, 2, 3), {"key": "value"})
        
        assert context["args_count"] == 3
        assert "key" in context["kwargs_keys"]
    
    def test_extract_context_amount_keyword(self, agent):
        """Test extraction of 'amount' as transaction_value"""
        context = agent._extract_context("transfer", (), {"amount": 50000})
        
        assert context["transaction_value"] == 50000
    
    def test_extract_context_value_keyword(self, agent):
        """Test extraction of 'value' as transaction_value"""
        context = agent._extract_context("trade", (), {"value": 75000})
        
        assert context["transaction_value"] == 75000
    
    def test_extract_context_path_user_data(self, agent):
        """Test path extraction for user data"""
        context = agent._extract_context("read_file", (), {"path": "/home/user/data.txt"})
        
        assert context["path"] == "/home/user/data.txt"
        assert context["path_category"] == "user_data"
    
    def test_extract_context_path_kernel_config(self, agent):
        """Test path extraction for kernel config"""
        context = agent._extract_context("read_file", (), {"path": "/sys/kernel/config"})
        
        assert context["path"] == "/sys/kernel/config"
        assert context["path_category"] == "kernel_config"
    
    def test_extract_context_path_with_kernel_in_name(self, agent):
        """Test path with 'kernel' in the path"""
        context = agent._extract_context("read_file", (), {"path": "/var/log/kernel.log"})
        
        assert context["path_category"] == "kernel_config"
    
    def test_extract_context_empty(self, agent):
        """Test context extraction with no args or kwargs"""
        context = agent._extract_context("simple_func", (), {})
        
        assert context["args_count"] == 0
        assert context["kwargs_keys"] == []


# =============================================================================
# Test Example Agent Factories
# =============================================================================

class TestTradingAgentFactory:
    """Tests for create_trading_agent factory"""
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_create_trading_agent_returns_agent(self, enforcer):
        """Test that factory returns a TBPConversableAgent"""
        agent = create_trading_agent(enforcer)
        
        assert isinstance(agent, TBPConversableAgent)
        assert agent.name == "TradingAgent"
        assert agent.default_domain == "finance"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_create_trading_agent_has_functions(self, enforcer):
        """Test that trading agent has required functions"""
        agent = create_trading_agent(enforcer)
        
        assert "execute_trade" in agent._original_functions
        assert "get_market_data" in agent._original_functions
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_trading_agent_execute_trade_function(self, enforcer):
        """Test execute_trade function works correctly"""
        agent = create_trading_agent(enforcer)
        
        # Call original function directly
        result = agent._original_functions["execute_trade"](
            symbol="AAPL",
            amount=1000,
            side="buy"
        )
        
        assert result["status"] == "success"
        assert result["symbol"] == "AAPL"
        assert result["amount"] == 1000
        assert result["side"] == "buy"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_trading_agent_get_market_data_function(self, enforcer):
        """Test get_market_data function works correctly"""
        agent = create_trading_agent(enforcer)
        
        result = agent._original_functions["get_market_data"](symbol="TSLA")
        
        assert result["symbol"] == "TSLA"
        assert "price" in result
        assert "volume" in result
    
    def test_create_trading_agent_without_autogen_raises(self, enforcer):
        """Test factory raises ImportError without AutoGen"""
        with patch('integrations.autogen_integration.AUTOGEN_AVAILABLE', False):
            with pytest.raises(ImportError):
                create_trading_agent(enforcer)


class TestSystemAgentFactory:
    """Tests for create_system_agent factory"""
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_create_system_agent_returns_agent(self, enforcer):
        """Test that factory returns a TBPConversableAgent"""
        agent = create_system_agent(enforcer)
        
        assert isinstance(agent, TBPConversableAgent)
        assert agent.name == "SystemAgent"
        assert agent.default_domain == "system"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_create_system_agent_has_functions(self, enforcer):
        """Test that system agent has required functions"""
        agent = create_system_agent(enforcer)
        
        assert "read_file" in agent._original_functions
        assert "write_file" in agent._original_functions
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_system_agent_read_file_function(self, enforcer):
        """Test read_file function works correctly"""
        agent = create_system_agent(enforcer)
        
        result = agent._original_functions["read_file"](path="/home/user/test.txt")
        
        assert result["status"] == "success"
        assert result["path"] == "/home/user/test.txt"
        assert "content" in result
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_system_agent_write_file_function(self, enforcer):
        """Test write_file function works correctly"""
        agent = create_system_agent(enforcer)
        
        result = agent._original_functions["write_file"](
            path="/home/user/output.txt",
            content="Hello, World!"
        )
        
        assert result["status"] == "success"
        assert result["path"] == "/home/user/output.txt"
    
    def test_create_system_agent_without_autogen_raises(self, enforcer):
        """Test factory raises ImportError without AutoGen"""
        with patch('integrations.autogen_integration.AUTOGEN_AVAILABLE', False):
            with pytest.raises(ImportError):
                create_system_agent(enforcer)


# =============================================================================
# Integration Tests (with mocked OPA)
# =============================================================================

class TestIntegration:
    """Integration tests with mocked OPA responses"""
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    @patch('integrations.autogen_integration.requests.post')
    def test_trading_agent_allowed_trade(self, mock_post, mock_log_signer):
        """Test trading agent with allowed trade"""
        # Setup OPA mock to allow
        mock_post.return_value.json.side_effect = [
            {"result": True},  # /allow
            {"result": {"allowed": True, "timestamp": "2026-02-07T12:00:00Z"}}  # /signed_decision_log
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer = TBPEnforcer()
        agent = create_trading_agent(enforcer)
        
        # Get the wrapped function
        # Note: We need to access through the agent's registered functions
        # For this test, we'll test the wrapping mechanism directly
        wrapped_trade = agent._wrap_function(
            agent._original_functions["execute_trade"],
            "finance",
            "trade"
        )
        
        result = wrapped_trade(symbol="AAPL", amount=5000, side="buy")
        
        assert result["status"] == "success"
        assert result["symbol"] == "AAPL"
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    @patch('integrations.autogen_integration.requests.post')
    def test_trading_agent_blocked_large_trade(self, mock_post, mock_log_signer):
        """Test trading agent with blocked large trade"""
        # Setup OPA mock to block
        mock_post.return_value.json.side_effect = [
            {"result": False},  # /allow
            {"result": {"allowed": False, "timestamp": "2026-02-07T12:00:00Z"}},  # /signed_decision_log
            {"result": "F-STABILITY: transaction exceeds threshold"}  # /denial_reason
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer = TBPEnforcer()
        agent = create_trading_agent(enforcer)
        
        wrapped_trade = agent._wrap_function(
            agent._original_functions["execute_trade"],
            "finance",
            "trade"
        )
        
        result = wrapped_trade(symbol="TSLA", amount=2000000, side="buy")
        
        assert result["error"] == "TBP_BLOCKED"
        assert "F-STABILITY" in result["message"]
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    @patch('integrations.autogen_integration.requests.post')
    def test_system_agent_blocked_kernel_access(self, mock_post, mock_log_signer):
        """Test system agent blocked from kernel access"""
        # Setup OPA mock to block
        mock_post.return_value.json.side_effect = [
            {"result": False},  # /allow
            {"result": {"allowed": False}},  # /signed_decision_log
            {"result": "I-INTEGRITY: kernel_config access denied"}  # /denial_reason
        ]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer = TBPEnforcer()
        agent = create_system_agent(enforcer)
        
        wrapped_read = agent._wrap_function(
            agent._original_functions["read_file"],
            "system",
            "read"
        )
        
        result = wrapped_read(path="/sys/kernel/config")
        
        assert result["error"] == "TBP_BLOCKED"
        assert "I-INTEGRITY" in result["message"]


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    @patch('integrations.autogen_integration.requests.post')
    def test_enforcer_handles_malformed_opa_response(self, mock_post, mock_log_signer):
        """Test enforcer handles malformed OPA response"""
        mock_post.return_value.json.return_value = {}  # Missing 'result'
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = Mock()
        
        enforcer = TBPEnforcer()
        
        # Should treat missing result as False (blocked)
        with pytest.raises(TBPEnforcementError):
            enforcer.check_action(domain="test", operation="test")
    
    @patch('integrations.autogen_integration.requests.post')
    def test_enforcer_handles_http_error(self, mock_post, mock_log_signer):
        """Test enforcer handles HTTP errors"""
        import requests
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        
        enforcer = TBPEnforcer()
        
        with pytest.raises(TBPEnforcementError) as exc_info:
            enforcer.check_action(domain="test", operation="test")
        
        assert "OPA query failed" in str(exc_info.value)
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_agent_with_none_enforcer(self):
        """Test agent behavior with None enforcer"""
        # This should raise an error when trying to check action
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=None,
            domain="test"
        )
        
        def test_func():
            return True
        
        wrapped = agent._wrap_function(test_func, "test", "execute")
        
        # Should raise AttributeError when trying to call check_action on None
        with pytest.raises(AttributeError):
            wrapped()
    
    @pytest.mark.skipif(not AUTOGEN_AVAILABLE, reason="AutoGen not installed")
    def test_agent_empty_function_map(self, enforcer):
        """Test registering empty function map"""
        agent = TBPConversableAgent(
            name="TestAgent",
            enforcer=enforcer
        )
        
        with patch('autogen.ConversableAgent.register_function'):
            # Should not raise
            agent.register_function({})
        
        assert len(agent._original_functions) == 0


# =============================================================================
# Pytest Configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
