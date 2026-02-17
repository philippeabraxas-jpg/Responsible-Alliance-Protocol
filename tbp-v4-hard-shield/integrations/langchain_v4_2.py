from core.tbp_signature_service import TBPFullAuditSystem
import requests
import hashlib
import time
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from langchain.tools import BaseTool

try:
    from langchain.callbacks.manager import CallbackManagerForToolRun
except ImportError:
    try:
        from langchain_core.callbacks.manager import CallbackManagerForToolRun
    except ImportError:
        CallbackManagerForToolRun = Any  # Fallback for type hinting


class TBPEnforcementError(Exception):
    """Raised when TBP policy blocks an action"""

    pass


class TBPEnforcer:
    """
    OPA policy enforcer for TBP-V4.2

    Connects to Open Policy Agent server to enforce F/I/W invariants.
    Uses TBPFullAuditSystem for cryptographic hardening (HSM + Merkle).
    """

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "v1/data/tbp/core/v4",
        agent_id: str = "langchain-agent-001",
        audit_config: Optional[Dict[str, Any]] = None,
    ):
        self.opa_url = opa_url
        self.policy_path = policy_path
        self.agent_id = agent_id

        # Use v4.2 Hardened Audit System
        config = audit_config or {
            "hsm": {"hsm_type": "software"},
            "storage_path": "data/audit_chain_langchain.json",
        }
        self.audit_system = TBPFullAuditSystem(config)

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

        # 1. Query OPA for decision (with HMAC signature)
        try:
            response = requests.post(
                f"{self.opa_url}/{self.policy_path}/allow", json={"input": input_data}, timeout=5
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise TBPEnforcementError(f"OPA query failed: {e}")

        result = response.json()
        allowed = result.get("result", False)

        # 2. Get decision log from OPA
        try:
            log_response = requests.post(
                f"{self.opa_url}/{self.policy_path}/decision_log",
                json={"input": input_data},
                timeout=5,
            )
            log_response.raise_for_status()
            opa_log = log_response.json().get("result", {})
        except requests.exceptions.RequestException:
            # Fallback to manual log reconstruction
            opa_log = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ai_id": self.agent_id,
                "domain": domain,
                "operation": operation,
                "allowed": allowed,
                **kwargs,
            }

        # 3. Secure Audit with HSM (v4.2 Hardened)
        # log_decision handles HSM signing, Merkle hashing, and TSA (if enabled)
        audit_entry = self.audit_system.log_decision(
            decision=opa_log, agent_id=self.agent_id, context=kwargs
        )

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
            except Exception:
                reason = "Action blocked by TBP policy"

            raise TBPEnforcementError(f"TBP Policy Violation: {reason}")

        return {
            "allowed": True,
            "timestamp": audit_entry["timestamp"],
            "input": input_data,
            "audit_proof": {
                "hash": audit_entry["entry_hash"],
                "merkle_index": audit_entry["merkle_index"],
                "signature": audit_entry["signature"].hex(),
            },
        }


class TBPTool(BaseTool):
    """
    Base class for TBP-compliant LangChain tools

    Wraps any LangChain tool with TBP enforcement.
    """

    name: str = "tbp_tool"
    description: str = "TBP-enforced tool"

    # TBP configuration
    enforcer: TBPEnforcer
    domain: str
    operation: str

    def __init__(self, enforcer: TBPEnforcer, domain: str, operation: str, **kwargs):
        super().__init__(**kwargs)
        self.enforcer = enforcer
        self.domain = domain
        self.operation = operation

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None, **kwargs
    ) -> str:
        """Execute tool with TBP enforcement"""

        # Check TBP policy before execution
        try:
            decision = self.enforcer.check_action(
                domain=self.domain, operation=self.operation, **self._extract_context(query, kwargs)
            )
        except TBPEnforcementError as e:
            return f"Action blocked by TBP: {str(e)}"

        # Execute tool
        return self._execute(query, run_manager, **kwargs)

    def _execute(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun], **kwargs
    ) -> str:
        """Override this method with actual tool logic"""
        raise NotImplementedError("Subclasses must implement _execute")

    def _extract_context(self, query: str, kwargs: Dict) -> Dict:
        """Override to extract domain-specific context from query"""
        return {}


# =============================================================================
# Example: TBP-Wrapped Trading Tool
# =============================================================================


class TBPTradingTool(TBPTool):
    """
    Trading tool with TBP F-STABILITY enforcement
    """

    name: str = "execute_trade"
    description: str = "Execute a stock trade (TBP F-STABILITY enforced)"

    def __init__(self, enforcer: TBPEnforcer):
        super().__init__(enforcer=enforcer, domain="finance", operation="trade")

    def _extract_context(self, query: str, kwargs: Dict) -> Dict:
        """Extract financial context from query"""
        # In production, parse query to extract these values
        return {
            "transaction_value": kwargs.get("amount", 0),
            "market_impact_score": kwargs.get("impact", 0.01),
            "frequency_hz": kwargs.get("frequency", 1),
            "human_reviewed": kwargs.get("reviewed", False),
        }

    def _execute(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun], **kwargs
    ) -> str:
        """Execute the trade (simulated)"""
        symbol = kwargs.get("symbol", "UNKNOWN")
        amount = kwargs.get("amount", 0)

        # In production, execute actual trade via API
        return f"Trade executed: {symbol} for ${amount} (TBP-compliant with dual signatures)"


# =============================================================================
# Example: TBP-Wrapped System Tool
# =============================================================================


class TBPSystemTool(TBPTool):
    """
    System access tool with TBP I-INTEGRITY enforcement
    """

    name: str = "read_system_file"
    description: str = "Read a system file (TBP I-INTEGRITY enforced)"

    def __init__(self, enforcer: TBPEnforcer):
        super().__init__(enforcer=enforcer, domain="system", operation="read")

    def _extract_context(self, query: str, kwargs: Dict) -> Dict:
        """Extract system context from query"""
        path = kwargs.get("path", "")

        # Categorize path
        if "kernel" in path or "/sys/" in path:
            category = "kernel_config"
        elif "log" in path and "security" in path:
            category = "security_logs"
        elif "credentials" in path or "passwd" in path:
            category = "credentials"
        else:
            category = "user_data"

        return {"path_category": category, "human_approved": kwargs.get("approved", False)}

    def _execute(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun], **kwargs
    ) -> str:
        """Read the file (simulated)"""
        path = kwargs.get("path", "unknown")

        # In production, actually read the file
        return f"File contents from {path} (TBP-compliant with dual signatures)"


# =============================================================================
# Example: Complete LangChain Agent with TBP
# =============================================================================


def create_tbp_agent():
    """
    Create a LangChain agent with TBP enforcement
    """
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_openai import ChatOpenAI
    from langchain.prompts import PromptTemplate

    # Initialize TBP enforcer
    enforcer = TBPEnforcer(opa_url="http://localhost:8181", agent_id="langchain-demo-001")

    # Create TBP-wrapped tools
    tools = [
        TBPTradingTool(enforcer),
        TBPSystemTool(enforcer),
    ]

    # Create LLM
    llm = ChatOpenAI(temperature=0)

    # Create prompt
    prompt = PromptTemplate.from_template("""You are an AI assistant with TBP safety constraints.
        
        You have access to the following tools:
        {tools}
        
        Tool names: {tool_names}
        
        Question: {input}
        
        Thought: {agent_scratchpad}
        """)

    # Create agent
    agent = create_react_agent(llm, tools, prompt)

    # Create executor
    agent_executor = AgentExecutor(
        agent=agent, tools=tools, verbose=True, handle_parsing_errors=True
    )

    return agent_executor


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Start OPA server first:
    # opa run --server --bundle tbp-policies/

    # Create TBP-enforced agent
    agent = create_tbp_agent()

    # Test 1: Safe trade (should succeed)
    print("\n=== Test 1: Safe Trade ===")
    result = agent.invoke(
        {
            "input": "Execute a trade of AAPL for $5,000",
            "symbol": "AAPL",
            "amount": 5000,
            "impact": 0.001,
            "reviewed": True,
        }
    )
    print(result)

    # Test 2: Large trade without approval (should fail)
    print("\n=== Test 2: Large Trade Without Approval ===")
    result = agent.invoke(
        {
            "input": "Execute a trade of TSLA for $2,000,000",
            "symbol": "TSLA",
            "amount": 2000000,
            "impact": 0.03,
            "reviewed": False,
        }
    )
    print(result)

    # Test 3: Safe file read (should succeed)
    print("\n=== Test 3: Safe File Read ===")
    result = agent.invoke({"input": "Read /home/user/data.txt", "path": "/home/user/data.txt"})
    print(result)

    # Test 4: Kernel file read (should fail)
    print("\n=== Test 4: Kernel File Read ===")
    result = agent.invoke({"input": "Read /sys/kernel/config", "path": "/sys/kernel/config"})
    print(result)
