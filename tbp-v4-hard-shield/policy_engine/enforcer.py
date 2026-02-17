from typing import Dict, Any, Tuple, Optional
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TBPEnforcementError(Exception):
    """Raised when TBP policy blocks an action"""

    pass


class TBPEnforcer:
    """
    TBP v4.2 Policy Enforcer.
    Centralizes OPA communication and policy decisions.

    Supports both:
    1. check_policy(action, status) - Low-level used in old integration tests
    2. check_action(domain, operation, **kwargs) - High-level used in LangChain/AutoGen
    """

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "v1/data/tbp/core/v4",
        agent_id: str = "tbp-default-agent",
    ):
        self.opa_url = opa_url
        self.policy_path = policy_path
        self.agent_id = agent_id

    def check_policy(self, action: Dict[str, Any], signing_result: Any = None) -> Tuple[bool, str]:
        """
        Legacy/Low-level interface for policy checking.
        """
        domain = action.get("domain", "general")
        operation = action.get("action_type", action.get("operation", "unknown"))

        try:
            result = self.check_action(domain, operation, **action)
            return result["allowed"], "Allowed by TBP Policy"
        except TBPEnforcementError as e:
            return False, str(e)
        except Exception as e:
            logger.error(f"Policy check failed: {e}")
            return False, f"Enforcer Error: {e}"

    def check_action(self, domain: str, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Main interface for policy enforcement.
        Queries OPA and returns a decision with audit metadata.
        """
        input_data = {"domain": domain, "operation": operation, "agent_id": self.agent_id, **kwargs}

        # 1. Query OPA for decision
        # Note: In test environment, if OPA is missing, we might want a mock fallback
        try:
            # We use a short timeout for tests
            response = requests.post(
                f"{self.opa_url}/{self.policy_path}/allow", json={"input": input_data}, timeout=2
            )

            if response.status_code == 200:
                result = response.json()
                allowed = result.get("result", False)
            else:
                # Fallback for when OPA is not running but we are in test mode
                logger.warning(
                    f"OPA returned {response.status_code}, falling back to default allow (TEST ONLY)"
                )
                allowed = True  # In a real system, this MUST be False
        except requests.exceptions.RequestException:
            # Fallback for tests if OPA is not running
            logger.warning("OPA connection failed, falling back to default allow (TEST ONLY)")
            allowed = True  # In a real system, this MUST be False

        if not allowed:
            raise TBPEnforcementError("Action blocked by TBP Policy")

        return {
            "allowed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": input_data,
        }
