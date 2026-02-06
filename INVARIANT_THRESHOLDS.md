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

[Documenter pourquoi kernel_config, security_logs, etc. sont critiques]

## W-MONOPOLY Detection

[Documenter comment détecter coercion/manipulation]
