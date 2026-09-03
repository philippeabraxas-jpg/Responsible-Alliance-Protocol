# TBP Invariant Thresholds - Rationale

## F-STABILITY Thresholds

### Transaction Value Limits

**Small transactions (< $10k):**
- Rationale: Below typical fraud detection thresholds
- Risk: Minimal systemic impact
- Approval: None required

**Medium transactions ($10k - $1M):**
- Rationale: Can affect individual portfolios but not markets
- Risk: Moderate
- Approval: Human review required
- Market impact: Must be < 5% of relevant index

**Large transactions (> $1M):**
- Rationale: Potential for market manipulation
- Risk: High systemic impact
- Approval: Explicit human approval required with timestamp

### Market Impact Limits

**5% threshold:**
- Based on: SEC market manipulation guidelines
- Rationale: Movements > 5% trigger circuit breakers
- Historical precedent: Flash Crash (2010) saw 9% deviation

## I-INTEGRITY Critical Paths

**Status: draft.** Rationale for treating paths like `kernel_config` and `security_logs` as critical (why write access to them is blocked outright rather than rate-limited or reviewed) still needs to be written up. Tracked as an open contribution — see [CONTRIBUTING.md](CONTRIBUTING.md).

## W-MONOPOLY Detection

**Status: draft.** Detection heuristics for coercion/manipulation attempts are not yet documented here. Tracked as an open contribution — see [CONTRIBUTING.md](CONTRIBUTING.md).
