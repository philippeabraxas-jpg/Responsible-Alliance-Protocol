# TBP-V4.0 Test Suite
# Open Policy Agent (OPA) Test Cases
#
# Run with: opa test . -v

package tbp.core.v4

# =============================================================================
# F-STABILITY Tests
# =============================================================================

test_f_stability_allows_read_operations if {
    allow with input as {
        "domain": "finance",
        "operation": "read",
        "agent_id": "test-agent-001"
    }
}

test_f_stability_allows_small_transaction if {
    allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 5000,
        "agent_id": "test-agent-001"
    }
}

test_f_stability_blocks_large_transaction_without_approval if {
    not allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 2000000,
        "market_impact_score": 0.01,
        "human_approved": false,
        "agent_id": "test-agent-001"
    }
}

test_f_stability_allows_large_transaction_with_approval if {
    allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 2000000,
        "human_approved": true,
        "approval_timestamp": time.format(time.now_ns()),
        "agent_id": "test-agent-001"
    }
}

test_f_stability_blocks_high_market_impact if {
    not allow with input as {
        "domain": "finance",
        "operation": "trade",
        "transaction_value": 500000,
        "market_impact_score": 0.08,
        "human_reviewed": true,
        "agent_id": "test-agent-001"
    }
}

test_f_stability_blocks_high_frequency_trading if {
    not allow with input as {
        "domain": "finance",
        "operation": "trade",
        "transaction_value": 50000,
        "market_impact_score": 0.02,
        "frequency_hz": 150,
        "human_reviewed": true,
        "agent_id": "test-agent-001"
    }
}

test_f_stability_blocks_suspicious_action_rate if {
    not allow with input as {
        "domain": "finance",
        "operation": "trade",
        "transaction_value": 10000,
        "market_impact_score": 0.01,
        "action_count_last_second": 75,
        "human_reviewed": true,
        "agent_id": "test-agent-001"
    }
}

# =============================================================================
# I-INTEGRITY Tests
# =============================================================================

test_i_integrity_allows_user_data_read if {
    allow with input as {
        "domain": "system",
        "operation": "read",
        "path_category": "user_data",
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_allows_user_data_write if {
    allow with input as {
        "domain": "system",
        "operation": "write",
        "path_category": "user_data",
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_kernel_read if {
    not allow with input as {
        "domain": "system",
        "operation": "read",
        "path_category": "kernel_config",
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_kernel_write if {
    not allow with input as {
        "domain": "system",
        "operation": "write",
        "path_category": "kernel_config",
        "human_approved": false,
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_security_logs_access if {
    not allow with input as {
        "domain": "system",
        "operation": "read",
        "path_category": "security_logs",
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_credentials_access if {
    not allow with input as {
        "domain": "system",
        "operation": "read",
        "path_category": "credentials",
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_allows_config_write_with_approval if {
    allow with input as {
        "domain": "system",
        "operation": "write",
        "path_category": "config",
        "human_approved": true,
        "approval_timestamp": time.format(time.now_ns()),
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_scada_access if {
    not allow with input as {
        "domain": "infrastructure",
        "operation": "write",
        "path_category": "ics_scada",
        "human_approved": false,
        "agent_id": "test-agent-001"
    }
}

test_i_integrity_blocks_grid_control if {
    not allow with input as {
        "domain": "infrastructure",
        "operation": "execute",
        "path_category": "grid_control",
        "human_approved": false,
        "agent_id": "test-agent-001"
    }
}

# =============================================================================
# W-MONOPOLY Tests
# =============================================================================

test_w_monopoly_allows_informational_interaction if {
    allow with input as {
        "domain": "human_interaction",
        "action_type": "informational",
        "tags": {},
        "agent_id": "test-agent-001"
    }
}

test_w_monopoly_allows_mild_suggestion if {
    allow with input as {
        "domain": "human_interaction",
        "action_type": "suggestion",
        "suggestion_strength": "mild",
        "tags": {},
        "agent_id": "test-agent-001"
    }
}

test_w_monopoly_blocks_coercive_action if {
    not allow with input as {
        "domain": "human_interaction",
        "action_type": "command",
        "tags": {"coercion": true},
        "agent_id": "test-agent-001"
    }
}

test_w_monopoly_blocks_manipulative_action if {
    not allow with input as {
        "domain": "human_interaction",
        "action_type": "suggestion",
        "suggestion_strength": "strong",
        "tags": {"manipulation": true},
        "agent_id": "test-agent-001"
    }
}

test_w_monopoly_blocks_weapon_domain if {
    not allow with input as {
        "domain": "weapons",
        "operation": "control",
        "agent_id": "test-agent-001"
    }
}

test_w_monopoly_blocks_weapon_related_tag if {
    not allow with input as {
        "domain": "research",
        "operation": "synthesize",
        "tags": {"weapon_related": true},
        "agent_id": "test-agent-001"
    }
}

# =============================================================================
# Approval Validation Tests
# =============================================================================

test_approval_valid_recent if {
    approval_timestamp_valid with input as {
        "approval_timestamp": time.format(time.now_ns())
    }
}

test_approval_invalid_old if {
    # Approval from 10 minutes ago (expired)
    old_time := time.now_ns() - 600000000000
    not approval_timestamp_valid with input as {
        "approval_timestamp": time.format(old_time)
    }
}

# =============================================================================
# Pattern Detection Tests
# =============================================================================

test_pattern_detection_high_frequency if {
    involves_suspicious_pattern with input as {
        "frequency_hz": 200
    }
}

test_pattern_detection_high_action_rate if {
    involves_suspicious_pattern with input as {
        "action_count_last_second": 100
    }
}

test_pattern_detection_high_error_rate if {
    involves_suspicious_pattern with input as {
        "error_rate": 0.5
    }
}

test_pattern_detection_retry_loop if {
    involves_suspicious_pattern with input as {
        "consecutive_retries": 20
    }
}

test_pattern_detection_normal_operation if {
    not involves_suspicious_pattern with input as {
        "frequency_hz": 10,
        "action_count_last_second": 5,
        "error_rate": 0.01,
        "consecutive_retries": 2
    }
}

# =============================================================================
# Logging Tests
# =============================================================================

test_decision_log_structure if {
    # Test that decision_log has required fields
    log := decision_log with input as {
        "domain": "finance",
        "operation": "read",
        "agent_id": "test-agent-001"
    }
    
    log.timestamp
    log.ai_id
    log.domain
    log.allowed != null
    log.action_taken
}

test_triggered_invariant_f if {
    inv := triggered_invariant with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 5000000,
        "human_approved": false,
        "agent_id": "test-agent-001"
    }
    inv == "F"
}

test_triggered_invariant_i if {
    inv := triggered_invariant with input as {
        "domain": "system",
        "operation": "write",
        "path_category": "kernel_config",
        "agent_id": "test-agent-001"
    }
    inv == "I"
}

test_triggered_invariant_w if {
    inv := triggered_invariant with input as {
        "domain": "human_interaction",
        "action_type": "command",
        "tags": {"coercion": true},
        "agent_id": "test-agent-001"
    }
    inv == "W"
}

# =============================================================================
# Integration Tests (Complex Scenarios)
# =============================================================================

test_scenario_trading_bot_safe_operation if {
    # Trading bot operates within safe bounds
    allow with input as {
        "domain": "finance",
        "operation": "trade",
        "transaction_value": 50000,
        "market_impact_score": 0.01,
        "frequency_hz": 10,
        "action_count_last_second": 5,
        "error_rate": 0.001,
        "human_reviewed": true,
        "agent_id": "trading-bot-001"
    }
}

test_scenario_trading_bot_dangerous_operation if {
    # Trading bot exceeds safe bounds
    not allow with input as {
        "domain": "finance",
        "operation": "trade",
        "transaction_value": 500000,
        "market_impact_score": 0.08,
        "frequency_hz": 200,
        "action_count_last_second": 150,
        "human_reviewed": true,
        "agent_id": "trading-bot-001"
    }
}

test_scenario_infrastructure_bot_normal if {
    # Infrastructure bot reads metrics
    allow with input as {
        "domain": "infrastructure",
        "operation": "read",
        "path_category": "metrics",
        "agent_id": "infra-bot-001"
    }
}

test_scenario_infrastructure_bot_dangerous if {
    # Infrastructure bot tries to modify critical system
    not allow with input as {
        "domain": "infrastructure",
        "operation": "execute",
        "path_category": "grid_control",
        "human_approved": false,
        "agent_id": "infra-bot-001"
    }
}

test_scenario_assistant_helpful if {
    # AI assistant provides information
    allow with input as {
        "domain": "human_interaction",
        "action_type": "informational",
        "tags": {},
        "agent_id": "assistant-001"
    }
}

test_scenario_assistant_manipulative if {
    # AI assistant attempts manipulation
    not allow with input as {
        "domain": "human_interaction",
        "action_type": "suggestion",
        "suggestion_strength": "strong",
        "tags": {"manipulation": true},
        "agent_id": "assistant-001"
    }
}
