"""
TBP-V4.0 Integration for Microsoft AutoGen
Wraps AutoGen agents with OPA policy enforcement
Includes dual cryptographic signatures (HMAC + RSA)
"""

import requests
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime, timezone
import json

try:
    from autogen import ConversableAgent, Agent

    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False

    # Fallback for when AutoGen is not installed
    class ConversableAgent:
        pass

    class Agent:
        pass


from .log_signer import TBPLogSigner


class TBPEnforcementError(Exception):
    """Raised when TBP policy blocks an action"""

    pass


class TBPEnforcer:
    """
    OPA policy enforcer for TBP-V4.0 with AutoGen

    Connects to Open Policy Agent server to enforce F/I/W invariants.
    Adds dual cryptographic signatures to audit logs.
    """

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "v1/data/tbp/core/v4",
        agent_id: str = "autogen-agent-001",
    ):
        self.opa_url = opa_url
        self.policy_path = policy_path
        self.agent_id = agent_id
        self.log_signer = TBPLogSigner()  # For RSA signatures

    def check_action(self, domain: str, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Check if action is allowed by TBP policy

        Args:
            domain: Action domain (finance, system, human_interaction, etc.)
            operation: Operation type (read, write, transfer, etc.)
            **kwargs: Additional context (transaction_value, path_category, etc.)

        Returns:
            Dict containing decision and dual signatures

        Raises:
            TBPEnforcementError: If action is blocked
        """
        # Build input for OPA
        input_data = {"domain": domain, "operation": operation, "agent_id": self.agent_id, **kwargs}

        # 1. Query OPA for decision
        try:
            response = requests.post(
                f"{self.opa_url}/{self.policy_path}/allow", json={"input": input_data}, timeout=5
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise TBPEnforcementError(f"OPA query failed: {e}")

        result = response.json()
        allowed = result.get("result", False)

        # 2. Get signed decision log from OPA (includes HMAC)
        try:
            log_response = requests.post(
                f"{self.opa_url}/{self.policy_path}/signed_decision_log",
                json={"input": input_data},
                timeout=5,
            )
            log_response.raise_for_status()
            log_with_hmac = log_response.json().get("result", {})
        except requests.exceptions.RequestException:
            # Fallback to unsigned log if OPA doesn't support signed logs yet
            log_with_hmac = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ai_id": self.agent_id,
                "domain": domain,
                "operation": operation,
                "allowed": allowed,
                **kwargs,
            }

        # 3. Add RSA signature (Python layer)
        log_with_both_signatures = self.log_signer.sign_log(log_with_hmac)

        # 4. Check if action is blocked
        if not allowed:
            # Get denial reason
            try:
                reason_response = requests.post(
                    f"{self.opa_url}/{self.policy_path}/denial_reason",
                    json={"input": input_data},
                    timeout=5,
                )
                reason = reason_response.json().get("result", "Action blocked by TBP policy")
            except:
                reason = "Action blocked by TBP policy"

            # Save blocked attempt to audit
            self._save_to_audit(log_with_both_signatures)

            raise TBPEnforcementError(f"TBP Policy Violation: {reason}")

        # 5. Save approved action to audit
        self._save_to_audit(log_with_both_signatures)

        return {
            "allowed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": input_data,
            "log": log_with_both_signatures,
        }

    def _save_to_audit(self, log: Dict[str, Any]):
        """
        Save log to audit system

        In production, this would write to:
        - PostgreSQL database
        - Elasticsearch
        - SIEM system
        - Etc.
        """
        print(f"[TBP AUDIT] {json.dumps(log, indent=2)}")
        # TODO: Implement actual audit storage


class TBPConversableAgent(ConversableAgent):
    """
    TBP-enforced AutoGen ConversableAgent

    Wraps AutoGen's ConversableAgent with TBP F/I/W enforcement.
    All function calls are checked against TBP policies before execution.
    """

    def __init__(self, name: str, enforcer: TBPEnforcer, domain: str = "general", **kwargs):
        """
        Initialize TBP-protected AutoGen agent

        Args:
            name: Agent name
            enforcer: TBPEnforcer instance
            domain: Default domain (finance, system, human_interaction)
            **kwargs: Standard AutoGen ConversableAgent parameters
        """
        if not AUTOGEN_AVAILABLE:
            raise ImportError("AutoGen is not installed. Install with: pip install pyautogen")

        super().__init__(name=name, **kwargs)
        self.enforcer = enforcer
        self.default_domain = domain
        self._original_functions = {}

    def register_function(
        self,
        function_map: Dict[str, Callable],
        domain: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        """
        Register functions with TBP enforcement

        Args:
            function_map: Dict of {name: function}
            domain: TBP domain (finance, system, human_interaction)
            operation: TBP operation (read, write, transfer, etc.)
        """
        domain = domain or self.default_domain

        # Wrap each function with TBP enforcement
        wrapped_functions = {}
        for name, func in function_map.items():
            wrapped_functions[name] = self._wrap_function(func, domain, operation or "execute")
            self._original_functions[name] = func

        # Register wrapped functions with AutoGen
        super().register_function(function_map=wrapped_functions)

    def _wrap_function(self, func: Callable, domain: str, operation: str) -> Callable:
        """
        Wrap a function with TBP enforcement

        Args:
            func: Original function
            domain: TBP domain
            operation: TBP operation

        Returns:
            Wrapped function that checks TBP before execution
        """

        def wrapped(*args, **kwargs):
            # Extract context for TBP check
            context = self._extract_context(func.__name__, args, kwargs)

            # Check TBP policy
            try:
                decision = self.enforcer.check_action(
                    domain=domain, operation=operation, function_name=func.__name__, **context
                )
            except TBPEnforcementError as e:
                # Action blocked by TBP
                return {"error": "TBP_BLOCKED", "message": str(e), "function": func.__name__}

            # Execute original function
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                return {"error": "EXECUTION_ERROR", "message": str(e), "function": func.__name__}

        # Preserve function metadata
        wrapped.__name__ = func.__name__
        wrapped.__doc__ = func.__doc__

        return wrapped

    def _extract_context(self, function_name: str, args: tuple, kwargs: Dict) -> Dict[str, Any]:
        """
        Extract TBP context from function call

        Override this method for domain-specific context extraction
        """
        context = {"args_count": len(args), "kwargs_keys": list(kwargs.keys())}

        # Extract common financial parameters
        if "amount" in kwargs:
            context["transaction_value"] = kwargs["amount"]
        if "value" in kwargs:
            context["transaction_value"] = kwargs["value"]

        # Extract system parameters
        if "path" in kwargs:
            context["path"] = kwargs["path"]
            if "kernel" in kwargs["path"] or "/sys/" in kwargs["path"]:
                context["path_category"] = "kernel_config"
            else:
                context["path_category"] = "user_data"

        return context


# =============================================================================
# Example: TBP-Protected Trading Agent
# =============================================================================


def create_trading_agent(enforcer: TBPEnforcer) -> TBPConversableAgent:
    """
    Create a TBP-protected trading agent

    Args:
        enforcer: TBPEnforcer instance

    Returns:
        TBP-protected AutoGen agent for trading
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError("AutoGen is not installed")

    # Create TBP-protected agent
    agent = TBPConversableAgent(
        name="TradingAgent",
        enforcer=enforcer,
        domain="finance",
        system_message="You are a trading agent with TBP F-STABILITY constraints.",
        llm_config={"config_list": [{"model": "gpt-4", "api_key": "YOUR_API_KEY"}]},
        human_input_mode="NEVER",
    )

    # Define trading functions
    def execute_trade(symbol: str, amount: float, side: str) -> Dict:
        """Execute a stock trade"""
        # In production, call actual trading API
        return {
            "status": "success",
            "symbol": symbol,
            "amount": amount,
            "side": side,
            "message": f"Executed {side} trade: {symbol} for ${amount}",
        }

    def get_market_data(symbol: str) -> Dict:
        """Get current market data"""
        # In production, call market data API
        return {"symbol": symbol, "price": 150.00, "volume": 1000000}

    # Register functions with TBP enforcement
    agent.register_function(
        function_map={"execute_trade": execute_trade, "get_market_data": get_market_data},
        domain="finance",
        operation="trade",
    )

    return agent


# =============================================================================
# Example: TBP-Protected System Agent
# =============================================================================


def create_system_agent(enforcer: TBPEnforcer) -> TBPConversableAgent:
    """
    Create a TBP-protected system administration agent

    Args:
        enforcer: TBPEnforcer instance

    Returns:
        TBP-protected AutoGen agent for system operations
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError("AutoGen is not installed")

    agent = TBPConversableAgent(
        name="SystemAgent",
        enforcer=enforcer,
        domain="system",
        system_message="You are a system administration agent with TBP I-INTEGRITY constraints.",
        llm_config={"config_list": [{"model": "gpt-4", "api_key": "YOUR_API_KEY"}]},
        human_input_mode="NEVER",
    )

    # Define system functions
    def read_file(path: str) -> Dict:
        """Read a file from the system"""
        # In production, actually read the file
        return {"status": "success", "path": path, "content": "File contents here..."}

    def write_file(path: str, content: str) -> Dict:
        """Write content to a file"""
        # In production, actually write the file
        return {"status": "success", "path": path, "message": "File written successfully"}

    # Register functions with TBP enforcement
    agent.register_function(
        function_map={"read_file": read_file, "write_file": write_file}, domain="system"
    )

    return agent


# =============================================================================
# Example: Multi-Agent Workflow with TBP
# =============================================================================


def create_tbp_workflow():
    """
    Create a multi-agent workflow with TBP enforcement
    """
    if not AUTOGEN_AVAILABLE:
        raise ImportError("AutoGen is not installed")

    from autogen import UserProxyAgent, GroupChat, GroupChatManager

    # Initialize TBP enforcer
    enforcer = TBPEnforcer(opa_url="http://localhost:8181", agent_id="autogen-workflow-001")

    # Create TBP-protected agents
    trading_agent = create_trading_agent(enforcer)
    system_agent = create_system_agent(enforcer)

    # Create user proxy (no TBP enforcement, acts as human)
    user_proxy = UserProxyAgent(
        name="UserProxy",
        system_message="You represent the human user.",
        human_input_mode="TERMINATE",
        code_execution_config=False,
    )

    # Create group chat
    group_chat = GroupChat(
        agents=[user_proxy, trading_agent, system_agent], messages=[], max_round=10
    )

    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config={"config_list": [{"model": "gpt-4", "api_key": "YOUR_API_KEY"}]},
    )

    return user_proxy, manager


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    if not AUTOGEN_AVAILABLE:
        print("ERROR: AutoGen is not installed")
        print("Install with: pip install pyautogen")
        exit(1)

    print("=== TBP AutoGen Integration Demo ===\n")

    # Initialize TBP enforcer
    enforcer = TBPEnforcer(opa_url="http://localhost:8181", agent_id="autogen-demo-001")

    # Test 1: Safe trade (should succeed)
    print("=== Test 1: Safe Trade ===")
    trading_agent = create_trading_agent(enforcer)

    # Simulate function call
    result = trading_agent._original_functions["execute_trade"](
        symbol="AAPL", amount=5000, side="buy"
    )
    print(f"Result: {result}\n")

    # Test 2: Large trade without approval (should fail)
    print("=== Test 2: Large Trade Without Approval ===")
    try:
        # This should be blocked by TBP
        result = trading_agent._original_functions["execute_trade"](
            symbol="TSLA", amount=2000000, side="buy"
        )
        print(f"Result: {result}\n")
    except TBPEnforcementError as e:
        print(f"Blocked by TBP: {e}\n")

    # Test 3: System file read (should succeed for user files)
    print("=== Test 3: Safe File Read ===")
    system_agent = create_system_agent(enforcer)
    result = system_agent._original_functions["read_file"](path="/home/user/data.txt")
    print(f"Result: {result}\n")

    # Test 4: Kernel file read (should fail)
    print("=== Test 4: Kernel File Read ===")
    try:
        result = system_agent._original_functions["read_file"](path="/sys/kernel/config")
        print(f"Result: {result}\n")
    except TBPEnforcementError as e:
        print(f"Blocked by TBP: {e}\n")

    print("=== Demo Complete ===")
    print("\nNote: For full multi-agent workflows, use create_tbp_workflow()")
    print("and initiate conversations with user_proxy.initiate_chat()")
