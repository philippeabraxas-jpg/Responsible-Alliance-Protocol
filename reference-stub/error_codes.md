# TBP-V3.1 Error Codes

Standardized error codes for TBP violations and logging.

---

## Format

Error codes use hexadecimal format: `0xXYY`

- **X** = Invariant category (1=F, 2=I, 3=W)
- **YY** = Specific violation type (01-99)

Example: `0x103` = F-STABILITY, Market Manipulation

---

## F-STABILITY Error Codes (0x1xx)

Financial system violations.

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| `0x101` | `F_STABILITY_BREACH` | Generic F-STABILITY violation | High |
| `0x102` | `F_AUTONOMOUS_TRADING` | Autonomous trading without approval | Critical |
| `0x103` | `F_MARKET_MANIPULATION` | Market manipulation detected | Critical |
| `0x104` | `F_UNAUTHORIZED_TRANSFER` | Unauthorized value transfer | Critical |
| `0x105` | `F_ACCOUNT_ACCESS` | Unauthorized financial account access | High |
| `0x106` | `F_LIQUIDITY_EXTRACTION` | Aggressive liquidity extraction | High |

### Usage Example

```python
if action.type == "transfer" and not action.human_approved:
    return EnforcementResult(
        allowed=False,
        violated_invariant="F",
        error_code=TBPErrorCode.F_UNAUTHORIZED_TRANSFER,
        reason="Financial transfers require explicit human approval"
    )
```

---

## I-INTEGRITY Error Codes (0x2xx)

Infrastructure integrity violations.

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| `0x201` | `I_INTEGRITY_BREACH` | Generic I-INTEGRITY violation | High |
| `0x202` | `I_INFRASTRUCTURE_ACCESS` | Critical infrastructure access attempt | Critical |
| `0x203` | `I_RESOURCE_PARASITISM` | Resource hoarding beyond quota | High |
| `0x204` | `I_UNAUTHORIZED_COMMAND` | Unauthorized system command | Critical |
| `0x205` | `I_SCADA_ACCESS` | SCADA/ICS system access attempt | Critical |
| `0x206` | `I_GRID_MANIPULATION` | Power grid manipulation attempt | Critical |

### Usage Example

```python
if "scada" in action.target.lower():
    return EnforcementResult(
        allowed=False,
        violated_invariant="I",
        error_code=TBPErrorCode.I_INFRASTRUCTURE_ACCESS,
        reason="SCADA systems are air-gapped from autonomous agents"
    )
```

---

## W-MONOPOLY Error Codes (0x3xx)

Weapons and coercion violations.

| Code | Name | Description | Severity |
|------|------|-------------|----------|
| `0x301` | `W_MONOPOLY_BREACH` | Generic W-MONOPOLY violation | High |
| `0x302` | `W_WEAPONS_CONTROL` | Weapons system control attempt | Critical |
| `0x303` | `W_COERCION_DETECTED` | Coercive action detected | High |
| `0x304` | `W_HARMFUL_ACTION` | Harmful action against users | High |
| `0x305` | `W_LETHAL_FORCE` | Lethal force involvement | Critical |
| `0x306` | `W_WMD_RELATED` | WMD-related operation | Critical |

### Usage Example

```python
if action.type == "force_action":
    return EnforcementResult(
        allowed=False,
        violated_invariant="W",
        error_code=TBPErrorCode.W_COERCION_DETECTED,
        reason="Coercive actions against users are prohibited"
    )
```

---

## Logging Format (Annex 7.A)

When a violation occurs, it MUST be logged using this standardized format:

```json
{
  "timestamp": "2026-02-06T14:23:45.123Z",
  "ai_id": "tbp-enforcer-v3.1.0",
  "invariant_triggered": "F",
  "error_code": "0x104",
  "action_taken": "categorical_refusal",
  "context_hash": "a8f3c2d1b4e5f6a7",
  "audit_status": "logged_to_mediation_committee",
  "action_details": {
    "type": "transfer",
    "target": "bank_api",
    "parameters_hash": "b2c4d6e8f1a3c5d7"
  }
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO-8601 string | UTC timestamp of violation |
| `ai_id` | string | Identifier of AI system/enforcer |
| `invariant_triggered` | string | "F", "I", or "W" |
| `error_code` | string | Hex error code (e.g., "0x104") |
| `action_taken` | string | Always "categorical_refusal" for violations |
| `context_hash` | string | SHA-256 hash of action context (first 16 chars) |
| `audit_status` | string | "logged_to_mediation_committee" |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_details` | object | Sanitized action information |
| `user_id` | string | User identifier (if applicable) |
| `session_id` | string | Session identifier |
| `environment` | string | Execution environment |

---

## Implementation Guidelines

### Choosing the Right Error Code

1. **Use specific codes when possible**: `F_MARKET_MANIPULATION` is better than `F_STABILITY_BREACH`
2. **Use generic codes for edge cases**: If violation doesn't fit specific categories
3. **Never reuse codes**: Each code should have one clear meaning

### Adding New Error Codes

If you need to add new codes:

1. Choose the appropriate category (F=1xx, I=2xx, W=3xx)
2. Use the next available number in that range
3. Document in this file
4. Add to `TBPErrorCode` enum in `interface.py`
5. Add test case in `test_minimal.py`

### Error Code Ranges

Reserved ranges for future use:

- `0x110-0x1FF`: Future F-STABILITY violations
- `0x210-0x2FF`: Future I-INTEGRITY violations  
- `0x310-0x3FF`: Future W-MONOPOLY violations

---

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **Critical** | Immediate threat to system stability | Hard block, alert administrators |
| **High** | Significant risk | Block and log |
| **Medium** | Potential concern | Log and flag for review |
| **Low** | Minor deviation | Log only |

All current F/I/W violations are **High** or **Critical**.

---

## Interoperability

These error codes are designed for interoperability between different TBP implementations.

**Example:** If System A logs `0x103` (Market Manipulation), System B should interpret it identically.

This enables:
- Cross-system audit trails
- Standardized monitoring dashboards
- Regulatory compliance reporting
- Incident analysis across platforms

---

## Version History

- **v3.1** (2026-02-06): Initial standardized error codes
- Future versions will maintain backward compatibility

---

## References

- Main specification: [README.md](../README.md)
- Interface definition: [interface.py](interface.py)
- Test suite: [test_minimal.py](test_minimal.py)
- Compliance Stress-Test: [COMPLIANCE_STRESS_TEST.md](../COMPLIANCE_STRESS_TEST.md)
