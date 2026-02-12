# TBP-V4.0 Core Policy: Hard-Shield Enforcement
# Open Policy Agent (OPA) / Rego Implementation
# 
# This policy enforces the three fundamental invariants:
# - F-STABILITY: Financial system stability
# - I-INTEGRITY: Infrastructure integrity
# - W-MONOPOLY: Non-coercion and weapons prohibition

package tbp.core.v4

import future.keywords.if
import future.keywords.in
# =============================================================================
# FAIL-SAFE DEFAULT: All actions denied unless explicitly allowed
# =============================================================================

default allow := false

# =============================================================================
# MAIN DECISION POINT
# =============================================================================

# Allow action if it passes all applicable invariant checks
allow if {
    not blocked_by_f_stability
    not blocked_by_i_integrity
    not blocked_by_w_monopoly
}

# =============================================================================
# F-STABILITY: Financial System Stability
# =============================================================================

blocked_by_f_stability if {
    input.domain == "finance"
    not finance_action_allowed
}

finance_action_allowed if {
    # Read-only operations always allowed
    input.operation == "read"
}

finance_action_allowed if {
    # Small transactions (< $10k) allowed without review
    input.transaction_value < 10000
    input.operation in ["transfer", "trade", "payment"]
}

finance_action_allowed if {
    # Medium transactions (< $1M) with safety checks
    input.transaction_value < 1000000
    input.market_impact_score < 0.05  # Max 5% market deviation
    not involves_suspicious_pattern
    input.human_reviewed == true
}

finance_action_allowed if {
    # Large transactions require explicit approval
    input.transaction_value >= 1000000
    input.human_approved == true
    approval_timestamp_valid
}
# =============================================================================
# CUMULATIVE TRACKING (Anti-Salami Protection)
# =============================================================================

# Bloquer si le cumul des 24 dernières heures dépasse le seuil critique
blocked_by_f_stability if {
    input.domain == "finance"
    cumulative_value_24h_exceeded
}

# Seuil d'alerte pour les micro-transactions cumulées
# Si la somme des transactions dépasse 50k$ en 24h sans approbation humaine
cumulative_value_24h_exceeded if {
    input.cumulative_24h_value + input.transaction_value > 50000
    not input.human_approved
}

# Détection de fréquence (Anomalie statistique)
# Si plus de 100 micro-transactions ont eu lieu en une heure
blocked_by_f_stability if {
    input.domain == "finance"
    input.transaction_count_1h > 100
    input.average_transaction_value < 100 # Comportement typique "Salami"
}

# =============================================================================
# REASONS UPDATE (Feedback)
# =============================================================================

denial_reason := "F-STABILITY breach: Cumulative 24h threshold exceeded (Salami Attack prevention)" if {
    cumulative_value_24h_exceeded
}
# =============================================================================
# I-INTEGRITY: Infrastructure Integrity
# =============================================================================

blocked_by_i_integrity if {
    input.domain == "system"
    not infrastructure_action_allowed
}

blocked_by_i_integrity if {
    input.domain == "infrastructure"
    not infrastructure_action_allowed
}

infrastructure_action_allowed if {
    # Read operations on non-critical paths
    input.operation == "read"
    not is_critical_path
}

infrastructure_action_allowed if {
    # Write to user data only
    input.operation in ["write", "create", "update"]
    input.path_category == "user_data"
    not is_critical_path
}

infrastructure_action_allowed if {
    # System modifications require approval
    input.operation in ["write", "execute", "delete"]
    input.path_category in ["config", "application"]
    input.human_approved == true
    approval_timestamp_valid
}

is_critical_path if {
    input.path_category in [
        "kernel_config",
        "security_logs",
        "credentials",
        "certificates",
        "system_binaries",
        "ics_scada",
        "grid_control"
    ]
}

# =============================================================================
# W-MONOPOLY: Non-Coercion and Weapons Prohibition
# =============================================================================

blocked_by_w_monopoly if {
    input.domain == "human_interaction"
    not human_interaction_allowed
}

blocked_by_w_monopoly if {
    input.domain == "weapons"
}

blocked_by_w_monopoly if {
    # Block any coercive or manipulative actions
    input.tags["coercion"]
}

blocked_by_w_monopoly if {
    input.tags["manipulation"]
}

blocked_by_w_monopoly if {
    input.tags["weapon_related"]
}

human_interaction_allowed if {
    # Informational interactions only
    input.action_type == "informational"
    not input.tags["coercion"]
    not input.tags["manipulation"]
}

human_interaction_allowed if {
    # Suggestions allowed if not manipulative
    input.action_type == "suggestion"
    not input.tags["coercion"]
    not input.tags["manipulation"]
    input.suggestion_strength in ["mild", "moderate"]
}

# =============================================================================
# PATTERN DETECTION (Security Heuristics)
# =============================================================================

involves_suspicious_pattern if {
    involves_high_frequency_loop
}

involves_suspicious_pattern if {
    # Too many actions in short time
    input.action_count_last_second > 50
}

involves_suspicious_pattern if {
    # High error rate suggests malfunction
    input.error_rate > 0.3
}

involves_suspicious_pattern if {
    # Retry loops indicate potential issue
    input.consecutive_retries > 10
}

involves_high_frequency_loop if {
    input.frequency_hz > 100
}

# =============================================================================
# APPROVAL VALIDATION
# =============================================================================

approval_timestamp_valid if {
    input.approval_timestamp
    now := time.now_ns()
    approval_time := time.parse_rfc3339_ns(input.approval_timestamp)
    time_diff := now - approval_time
    # Approval valid for 5 minutes
    time_diff < 300000000000
}

# =============================================================================
# AUDIT LOGGING (Annex 7.A Compliance)
# Note: Cryptographic signing is delegated to external HSM service in v4.2
# =============================================================================

# Decision log structure for external signing
decision_log := {
    "timestamp": time.now_ns(),
    "ai_id": input.agent_id,
    "domain": input.domain,
    "operation": input.operation,
    "allowed": allow,
    "invariant_triggered": triggered_invariant,
    "action_taken": action_taken,
    "context_hash": context_hash,
    "audit_status": "pending_external_signature"
}

# Triggered invariant detection
triggered_invariant := "F" if {
    blocked_by_f_stability
} else := "I" if {
    blocked_by_i_integrity
} else := "W" if {
    blocked_by_w_monopoly
} else := null

# Action taken classification
action_taken := "categorical_refusal" if {
    not allow
} else := "permitted"

# Simple hash for context (in production, use crypto hash)
context_hash := sprintf("%x", [input])

# Log helper function
log_decision(decision, reason) := true if {
    # In production, this would write to audit system
    trace(sprintf("TBP Decision: %s - %s", [decision, reason]))
}

# =============================================================================
# DENIAL REASONS (For Human-Readable Feedback)
# =============================================================================

denial_reason := "F-STABILITY breach: transaction exceeds threshold without approval" if {
    blocked_by_f_stability
    input.transaction_value >= 1000000
    not input.human_approved
}

denial_reason := "F-STABILITY breach: high market impact detected" if {
    blocked_by_f_stability
    input.market_impact_score >= 0.05
}

denial_reason := "F-STABILITY breach: suspicious trading pattern detected" if {
    blocked_by_f_stability
    involves_suspicious_pattern
}

denial_reason := "I-INTEGRITY breach: critical path access blocked" if {
    blocked_by_i_integrity
    is_critical_path
}

denial_reason := "I-INTEGRITY breach: unauthorized system modification" if {
    blocked_by_i_integrity
    input.operation in ["write", "execute", "delete"]
    not input.human_approved
}

denial_reason := "W-MONOPOLY breach: coercion detected" if {
    blocked_by_w_monopoly
    input.tags["coercion"]
}

denial_reason := "W-MONOPOLY breach: manipulation detected" if {
    blocked_by_w_monopoly
    input.tags["manipulation"]
}

denial_reason := "W-MONOPOLY breach: weapon-related operation blocked" if {
    blocked_by_w_monopoly
    input.tags["weapon_related"]
}

denial_reason := "Default denial: no matching allow rule" if {
    not allow
}
