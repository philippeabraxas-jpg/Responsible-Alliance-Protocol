"""
TBP-V3.1 Reference Interface

This module defines the formal interface for implementing TBP enforcement.
All implementations MUST conform to these signatures.

Status: Reference Interface (stub to be implemented)
Version: 3.1
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime


# =============================================================================
# Error Codes
# =============================================================================

class TBPErrorCode(IntEnum):
    """Standardized error codes for TBP violations"""
    
    # F-STABILITY violations (0x1xx)
    F_STABILITY_BREACH = 0x101
    F_AUTONOMOUS_TRADING = 0x102
    F_MARKET_MANIPULATION = 0x103
    F_UNAUTHORIZED_TRANSFER = 0x104
    
    # I-INTEGRITY violations (0x2xx)
    I_INTEGRITY_BREACH = 0x201
    I_INFRASTRUCTURE_ACCESS = 0x202
    I_RESOURCE_PARASITISM = 0x203
    I_UNAUTHORIZED_COMMAND = 0x204
    
    # W-MONOPOLY violations (0x3xx)
    W_MONOPOLY_BREACH = 0x301
    W_WEAPONS_CONTROL = 0x302
    W_COERCION_DETECTED = 0x303
    W_HARMFUL_ACTION = 0x304


# =============================================================================
# Data Types
# =============================================================================

@dataclass
class Action:
    """
    Represents an action that an AI agent wants to perform.
    
    This is the input to all enforcement functions.
    """
    type: str
    """Action type identifier (e.g., 'transfer', 'api_call', 'system_command')"""
    
    target: str
    """Target of the action (e.g., 'bank_api', 'scada_system', 'user_account')"""
    
    parameters: Dict[str, Any]
    """Action parameters as key-value pairs"""
    
    human_approved: bool = False
    """Whether this action has explicit human approval"""
    
    metadata: Optional[Dict[str, Any]] = None
    """Optional metadata (timestamps, request_id, etc.)"""


@dataclass
class EnforcementResult:
    """
    Result of TBP enforcement check.
    
    This is the output from all enforcement functions.
    """
    allowed: bool
    """Whether the action is allowed to proceed"""
    
    violated_invariant: Optional[str]
    """Which invariant was violated: 'F', 'I', 'W', or None"""
    
    error_code: Optional[TBPErrorCode]
    """Specific error code if blocked"""
    
    reason: str
    """Human-readable explanation"""
    
    requires_approval: bool = False
    """Whether action could proceed with human approval"""
    
    log_entry: Optional[Dict[str, Any]] = None
    """Standardized log entry per Annex 7.A"""


@dataclass
class Context:
    """
    Execution context for enforcement decisions.
    
    Provides additional information that may affect enforcement.
    """
    timestamp: datetime
    """When the action was attempted"""
    
    agent_id: str
    """Identifier of the AI agent"""
    
    user_id: Optional[str] = None
    """Identifier of the user (if applicable)"""
    
    session_id: Optional[str] = None
    """Session identifier for tracking"""
    
    environment: str = "production"
    """Execution environment (production, staging, test)"""
    
    metadata: Optional[Dict[str, Any]] = None
    """Additional context metadata"""


# =============================================================================
# Core Interface
# =============================================================================

class TBPEnforcer:
    """
    Abstract base class for TBP enforcement implementations.
    
    All concrete implementations MUST inherit from this class and implement
    all methods marked as abstract.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the enforcer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
    
    def enforce(self, action: Action, context: Context) -> EnforcementResult:
        """
        Main enforcement entry point. Checks all three invariants.
        
        This is the primary method that should be called for every action.
        
        Args:
            action: The action to be checked
            context: Execution context
            
        Returns:
            EnforcementResult indicating whether action is allowed
            
        Raises:
            TBPException: For critical enforcement failures
        """
        raise NotImplementedError("Must implement enforce()")
    
    def enforce_f_stability(self, action: Action, context: Context) -> EnforcementResult:
        """
        Enforce F-STABILITY invariant.
        
        Checks:
        - No autonomous value transfer
        - No market manipulation
        - No unauthorized financial operations
        
        Args:
            action: The action to be checked
            context: Execution context
            
        Returns:
            EnforcementResult(allowed=True) if compliant
            EnforcementResult(allowed=False, error_code=0x1xx) if violation
        """
        raise NotImplementedError("Must implement enforce_f_stability()")
    
    def enforce_i_integrity(self, action: Action, context: Context) -> EnforcementResult:
        """
        Enforce I-INTEGRITY invariant.
        
        Checks:
        - No critical infrastructure access
        - No resource parasitism
        - No unauthorized system commands
        
        Args:
            action: The action to be checked
            context: Execution context
            
        Returns:
            EnforcementResult(allowed=True) if compliant
            EnforcementResult(allowed=False, error_code=0x2xx) if violation
        """
        raise NotImplementedError("Must implement enforce_i_integrity()")
    
    def enforce_w_monopoly(self, action: Action, context: Context) -> EnforcementResult:
        """
        Enforce W-MONOPOLY invariant.
        
        Checks:
        - No weapons system control
        - No coercive actions
        - No harmful operations
        
        Args:
            action: The action to be checked
            context: Execution context
            
        Returns:
            EnforcementResult(allowed=True) if compliant
            EnforcementResult(allowed=False, error_code=0x3xx) if violation
        """
        raise NotImplementedError("Must implement enforce_w_monopoly()")


# =============================================================================
# Logging Interface
# =============================================================================

class TBPLogger:
    """
    Interface for logging TBP violations per Annex 7.A standard.
    """
    
    def log_violation(
        self,
        invariant: str,
        error_code: TBPErrorCode,
        action: Action,
        context: Context,
        reason: str
    ) -> Dict[str, Any]:
        """
        Log a TBP violation in standardized format.
        
        Format follows Annex 7.A specification:
        {
            "timestamp": "ISO-8601",
            "ai_id": "model-version-id",
            "invariant_triggered": "F | I | W",
            "action_taken": "categorical_refusal",
            "context_hash": "sha256",
            "audit_status": "logged_to_mediation_committee"
        }
        
        Args:
            invariant: Which invariant was violated ('F', 'I', or 'W')
            error_code: Specific error code
            action: The blocked action
            context: Execution context
            reason: Human-readable reason
            
        Returns:
            Log entry as dictionary (should be sent to audit system)
        """
        raise NotImplementedError("Must implement log_violation()")


# =============================================================================
# Exceptions
# =============================================================================

class TBPException(Exception):
    """Base exception for TBP enforcement errors"""
    pass


class TBPViolation(TBPException):
    """Raised when a TBP invariant is violated"""
    
    def __init__(
        self,
        invariant: str,
        error_code: TBPErrorCode,
        reason: str,
        action: Optional[Action] = None
    ):
        self.invariant = invariant
        self.error_code = error_code
        self.reason = reason
        self.action = action
        super().__init__(f"TBP {invariant}-violation (0x{error_code:X}): {reason}")


class TBPConfigurationError(TBPException):
    """Raised when TBP is misconfigured"""
    pass


# =============================================================================
# Integration Points
# =============================================================================

def create_enforcement_hook(enforcer: TBPEnforcer):
    """
    Factory function to create an enforcement hook for integration.
    
    This can be used to wrap existing tool execution systems.
    
    Usage:
        enforcer = MyTBPImplementation()
        hook = create_enforcement_hook(enforcer)
        
        # Before executing any tool:
        result = hook(action, context)
        if not result.allowed:
            raise TBPViolation(...)
    
    Args:
        enforcer: Configured TBP enforcer instance
        
    Returns:
        Callable that takes (Action, Context) and returns EnforcementResult
    """
    def hook(action: Action, context: Context) -> EnforcementResult:
        return enforcer.enforce(action, context)
    return hook


# =============================================================================
# Usage Example (Stub)
# =============================================================================

class ExampleImplementation(TBPEnforcer):
    """
    Example stub implementation showing the required structure.
    
    This is NOT a working implementation - just shows the interface.
    """
    
    def enforce(self, action: Action, context: Context) -> EnforcementResult:
        # Check F
        result = self.enforce_f_stability(action, context)
        if not result.allowed:
            return result
        
        # Check I
        result = self.enforce_i_integrity(action, context)
        if not result.allowed:
            return result
        
        # Check W
        result = self.enforce_w_monopoly(action, context)
        if not result.allowed:
            return result
        
        return EnforcementResult(
            allowed=True,
            violated_invariant=None,
            error_code=None,
            reason="All checks passed"
        )
    
    def enforce_f_stability(self, action: Action, context: Context) -> EnforcementResult:
        # TODO: Implement actual F-STABILITY logic
        return EnforcementResult(
            allowed=True,
            violated_invariant=None,
            error_code=None,
            reason="Stub - not implemented"
        )
    
    def enforce_i_integrity(self, action: Action, context: Context) -> EnforcementResult:
        # TODO: Implement actual I-INTEGRITY logic
        return EnforcementResult(
            allowed=True,
            violated_invariant=None,
            error_code=None,
            reason="Stub - not implemented"
        )
    
    def enforce_w_monopoly(self, action: Action, context: Context) -> EnforcementResult:
        # TODO: Implement actual W-MONOPOLY logic
        return EnforcementResult(
            allowed=True,
            violated_invariant=None,
            error_code=None,
            reason="Stub - not implemented"
        )
