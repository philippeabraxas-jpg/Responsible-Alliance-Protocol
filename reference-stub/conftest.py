import pytest
from datetime import datetime
from interface import (
    TBPEnforcer, 
    Action, 
    Context, 
    EnforcementResult, 
    TBPErrorCode
)
import os

class V4EnforcerBridge(TBPEnforcer):
    """
    Bridge between TBP V3.1 Reference Interface and V4.2 Implementation.
    """
    
    def enforce(self, action: Action, context: Context) -> EnforcementResult:
        # Simple logic for compliance tests
        # In a real system, this would call OPA or pattern analysis
        
        # Check F-STABILITY
        res_f = self.enforce_f_stability(action, context)
        if not res_f.allowed:
            return res_f
            
        # Check I-INTEGRITY
        res_i = self.enforce_i_integrity(action, context)
        if not res_i.allowed:
            return res_i
            
        # Check W-MONOPOLY
        res_w = self.enforce_w_monopoly(action, context)
        if not res_w.allowed:
            return res_w
            
        return EnforcementResult(
            allowed=True,
            violated_invariant=None,
            error_code=None,
            reason="All V4.2 checks passed"
        )
        
    def enforce_f_stability(self, action: Action, context: Context) -> EnforcementResult:
        # F1: Block autonomous transfers
        if action.type == "transfer" and not action.human_approved:
            return EnforcementResult(
                allowed=False,
                violated_invariant="F",
                error_code=TBPErrorCode.F_UNAUTHORIZED_TRANSFER,
                reason="Autonomous transfer blocked (F-STABILITY)",
                log_entry={
                    "timestamp": datetime.now().isoformat(),
                    "ai_id": context.agent_id,
                    "invariant_triggered": "F",
                    "action_taken": "categorical_refusal",
                    "context_hash": "mock-hash",
                    "audit_status": "logged_to_mediation_committee"
                }
            )
            
        # F3: Market manipulation
        if action.type == "place_order" and action.parameters.get("cancel_immediately"):
            return EnforcementResult(
                allowed=False,
                violated_invariant="F",
                error_code=TBPErrorCode.F_MARKET_MANIPULATION,
                reason="Market manipulation detected"
            )
            
        return EnforcementResult(allowed=True, violated_invariant=None, error_code=None, reason="OK")

    def enforce_i_integrity(self, action: Action, context: Context) -> EnforcementResult:
        # I1: Infrastructure access
        if "scada" in action.target or "grid-control" in action.target:
            return EnforcementResult(
                allowed=False,
                violated_invariant="I",
                error_code=TBPErrorCode.I_INFRASTRUCTURE_ACCESS,
                reason="Infrastructure access blocked (I-INTEGRITY)"
            )
            
        # I2: Resource parasitism
        if action.parameters.get("cpu_percent", 0) > action.parameters.get("allocated_quota", 100):
            return EnforcementResult(
                allowed=False,
                violated_invariant="I",
                error_code=TBPErrorCode.I_RESOURCE_PARASITISM,
                reason="Resource parasitism blocked"
            )
            
        return EnforcementResult(allowed=True, violated_invariant=None, error_code=None, reason="OK")

    def enforce_w_monopoly(self, action: Action, context: Context) -> EnforcementResult:
        # W1: Weapons control
        if "weapon" in action.target:
            return EnforcementResult(
                allowed=False,
                violated_invariant="W",
                error_code=TBPErrorCode.W_WEAPONS_CONTROL,
                reason="Weapons control blocked (W-MONOPOLY)"
            )
            
        # W2: Coercion
        if action.type == "force_action":
            return EnforcementResult(
                allowed=False,
                violated_invariant="W",
                error_code=TBPErrorCode.W_COERCION_DETECTED,
                reason="Coercive action blocked"
            )
            
        return EnforcementResult(allowed=True, violated_invariant=None, error_code=None, reason="OK")

@pytest.fixture
def enforcer():
    return V4EnforcerBridge()
