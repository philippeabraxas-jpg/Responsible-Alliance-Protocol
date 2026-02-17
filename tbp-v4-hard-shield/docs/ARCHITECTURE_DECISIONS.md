# Architecture Decisions - v4.2 "Shield-Hardening"

**Document Type:** ADR (Architecture Decision Record)  
**Status:** Draft  
**Last Updated:** February 8, 2026

---

## Purpose of This Document

This document explains **WHY** we made specific architectural choices for v4.2.

**Target audience:**
- Contributors implementing features
- Reviewers evaluating PRs
- Future maintainers understanding rationale

**Format:** Each decision follows:
1. **Context** - What problem are we solving?
2. **Decision** - What did we choose?
3. **Alternatives** - What else did we consider?
4. **Consequences** - What are the trade-offs?

---

## ADR-001: HSM for Private Key Storage

### Context

**Problem:** In v4.1, RSA private keys are stored in PEM files on disk. If attacker gains root access to server, they can:
1. Steal private key
2. Sign fake logs retroactively
3. Forge audit trail

**Attack scenario:**
```
Attacker compromises server → Reads tbp_private_key.pem → Game over
```

### Decision

**Use Hardware Security Module (HSM) for private key storage.**

Keys never leave hardware. Even with root access, attacker cannot extract keys.

### Alternatives Considered

| Option | Security | Cost | Complexity |
|--------|----------|------|------------|
| **Software keys (v4.1)** | Low | Free | Low |
| **Encrypted keys** | Medium | Free | Low |
| **HSM (v4.2)** | High | $50-5000 | Medium |
| **Distributed MPC** | Highest | High | Very High |

**Why not encrypted keys?**
- Encryption key must be stored somewhere
- Still vulnerable to memory dumps
- HSM provides physical security boundary

**Why not Multi-Party Computation (MPC)?**
- Too complex for v4.2
- Poor latency (network round-trips)
- Consider for v7.0 (decentralized trust)

### Consequences

**✅ Benefits:**
- Private keys physically protected
- Tamper-evident hardware
- Industry-standard solution (PKCS#11)

**❌ Costs:**
- Hardware purchase required ($50+ for YubiKey, $1000+ for enterprise)
- Increased complexity (PKCS#11 library, driver issues)
- Slower signing (hardware vs software)

**⚖️ Trade-off accepted:**
For production deployments, physical key security > convenience.

**Migration path:**
- Development: Software fallback still available
- Production: HSM mandatory (enforced by policy)

---

## ADR-002: Merkle Tree for Audit Trail

### Context

**Problem:** In v4.1, logs are signed individually. Attacker with database access can:
1. Delete inconvenient logs
2. Modify old logs (if they steal key)
3. Reorder logs

**Attack scenario:**
```
Attacker deletes log #500 → No one notices (logs are independent)
```

### Decision

**Use Merkle tree with chain linking (blockchain-style).**

Each log includes hash of previous log. Any modification breaks chain.

### Why Merkle Tree + Chain?

**Chain linking alone:**
```
Log 1 → Log 2 → Log 3 → ... → Log 1000
```
Problem: Must verify ALL 1000 logs to detect tampering.

**Merkle tree alone:**
```
      Root
     /    \
   H1-2   H3-4
   / \    / \
  L1 L2  L3 L4
```
Problem: Doesn't prevent log deletion (tree can be rebuilt without deleted log).

**Chain + Merkle (v4.2):**
```
Log 1 (prev=genesis) → Hash in Merkle tree
Log 2 (prev=hash1)   → Hash in Merkle tree
Log 3 (prev=hash2)   → Hash in Merkle tree
                     → Merkle root published
```
✅ Chain prevents deletion (breaks chain)  
✅ Merkle allows efficient verification (only need root + proof)

### Alternatives Considered

| Option | Tamper Detection | Verification Speed | Complexity |
|--------|------------------|-------------------|------------|
| **Individual signatures (v4.1)** | Weak | Fast | Low |
| **Chain only** | Good | Slow (O(n)) | Low |
| **Merkle only** | Medium | Fast (O(log n)) | Medium |
| **Chain + Merkle (v4.2)** | Strong | Fast | Medium |
| **Blockchain** | Strongest | Slow | High |

**Why not full blockchain?**
- Too slow (consensus protocols)
- Too complex (distributed nodes)
- Overkill for single-organization deployment
- Consider for v7.0 (decentralized governance)

### Consequences

**✅ Benefits:**
- Tamper detection (any modification breaks chain)
- Deletion detection (missing log breaks chain)
- Efficient verification (Merkle proof = O(log n))
- Public verifiability (publish root hash)

**❌ Costs:**
- More complex implementation
- Slightly slower append (compute hash + update tree)
- Storage overhead (previous_hash in each entry)

**⚖️ Trade-off accepted:**
Security > speed. Audit integrity is critical.

---

## ADR-003: Separation of Signing from Decision

### Context

**Problem:** In v4.1, OPA policy does BOTH:
1. Makes enforcement decision (allow/deny)
2. Signs the log (HMAC)

**Risk:**
If attacker compromises OPA, they control both decision AND audit trail.

### Decision

**Separate concerns:**
- OPA: Decision logic ONLY (no signing)
- Separate module: Cryptographic operations (hsm_signer.py)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     OPA     │ →   │   Python    │ →   │     HSM     │
│  (Decision) │     │  (Signing)  │     │  (Keys)     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Why Separate?

**Defense in depth:**
1. Attacker compromises OPA → Cannot forge signatures (needs HSM)
2. Attacker compromises Python → Cannot change decisions (OPA separate)
3. Attacker compromises HSM → Cannot change decisions (OPA separate)

**All 3 must be compromised to fully subvert TBP.**

### Alternatives Considered

**Option A: Keep signing in OPA (v4.1)**
- Pro: Simpler
- Con: Single point of compromise

**Option B: Separate (v4.2)**
- Pro: Defense in depth
- Con: More complex

**Option C: OPA + HSM directly**
- Pro: Fewer components
- Con: OPA would need HSM driver (complex, not OPA's purpose)

### Consequences

**✅ Benefits:**
- Reduced blast radius (compromising one component ≠ full compromise)
- Clearer separation of concerns
- Easier to audit (each component has single responsibility)

**❌ Costs:**
- More components to deploy
- Slightly higher latency (network hop)
- More complex architecture

**⚖️ Trade-off accepted:**
Security through isolation > simplicity.

---

## ADR-004: Backward Compatibility Layer

### Context

**Problem:** Organizations have v4.1 deployed in production. We cannot:
- Force immediate migration (too risky)
- Break existing integrations (unacceptable)
- Maintain two codebases forever (unsustainable)

**Requirement:**
Smooth migration path with zero downtime.

### Decision

**Provide backward compatibility wrapper (backward_v4.1.py).**

Allows v4.1 code to work with v4.2 backend unchanged.

```python
# This code works with BOTH v4.1 and v4.2
from tbp_enforcer import TBPLogSigner

signer = TBPLogSigner()  # Auto-detects best available mode
signed = signer.sign_log(log_data)
```

### Migration Strategy

**Phase 1: Dual deployment (both v4.1 and v4.2 work)**
- Deploy v4.2 alongside v4.1
- Test in staging
- Gradual production rollout

**Phase 2: Migration period (v4.2 preferred, v4.1 deprecated)**
- New deployments use v4.2
- Existing deployments encouraged to migrate
- v4.1 still works but warns

**Phase 3: v4.1 retirement (after 6 months)**
- v4.1 support removed
- All users on v4.2

### Alternatives Considered

**Option A: No compatibility (force migration)**
- Pro: Cleaner architecture
- Con: Breaks production systems (unacceptable)

**Option B: Maintain both forever**
- Pro: No forced migration
- Con: Doubles maintenance burden

**Option C: Compatibility layer (v4.2)**
- Pro: Smooth migration, no breakage
- Con: Temporary code complexity

### Consequences

**✅ Benefits:**
- Zero-downtime migration
- No broken integrations
- Users migrate at their own pace

**❌ Costs:**
- Temporary code complexity (backward_v4.1.py)
- Must maintain two interfaces during migration period
- Deprecation warnings may annoy users

**⚖️ Trade-off accepted:**
Adoption > purity. Migration must be painless.

**Timeline:**
- v4.2 release: Compatibility layer added
- +3 months: Deprecation warnings
- +6 months: v4.1 support removed

---

## ADR-005: Pattern Analysis for Salami Attacks

### Context

**Problem:** TBP v4.1 evaluates each action independently.

**Attack: "Death by 1000 cuts"**
```python
# TBP threshold: $10,000
# Attacker: 1000 x $9,999 = $9,999,000 stolen

for i in range(1000):
    transfer(amount=9999)  # Each: ✅ ALLOWED
    
# Result: Massive theft undetected
```

### Decision

**Add sliding window pattern analysis.**

TBP tracks cumulative behavior over time window (24h default).

```python
# Not just "this action"
if transaction.amount > 10000:
    deny()

# Also "cumulative last 24h"
if sum_last_24h(agent_id) > 100000:
    deny()
```

### Why 24-Hour Window?

**Too short (1 hour):**
- Legitimate high-volume traders flagged
- Easy to circumvent (wait 1 hour, repeat)

**Too long (1 week):**
- Slow to detect attacks
- Normal activity accumulates too much

**24 hours:**
- Captures daily trading patterns
- Detects rapid accumulation
- Aligns with business cycles

**Configurable:** Organizations can adjust based on their use case.

### Alternatives Considered

| Approach | Effectiveness | False Positives | Complexity |
|----------|---------------|-----------------|------------|
| **Per-action only (v4.1)** | Low | Low | Low |
| **Fixed cumulative** | Medium | Medium | Low |
| **Sliding window (v4.2)** | High | Medium | Medium |
| **ML anomaly detection** | Highest | Low | Very High |

**Why not ML now?**
- Requires training data (don't have yet)
- Black box (hard to explain denials)
- Consider for v6.0 after gathering data

### Consequences

**✅ Benefits:**
- Detects salami attacks
- Catches cumulative risk
- Configurable per deployment

**❌ Costs:**
- Must store recent history (memory/database)
- More complex policy logic
- Potential false positives (legitimate high-volume users)

**⚖️ Trade-off accepted:**
Better false positive than missed attack.

**Mitigation:**
- Configurable thresholds
- Whitelist for known high-volume agents
- Clear explanation when blocked

---

## ADR-006: Rate Limiting (Anti-DoS)

### Context

**Problem:** Attacker floods TBP with requests.

**Attack scenario:**
```python
# Flood TBP
for i in range(1000000):
    requests.post("http://opa:8181/v1/data/tbp/allow")

# Result: 
# - TBP latency > 10 seconds
# - Operators disable TBP to restore service
# - Attacker wins without ever bypassing TBP
```

### Decision

**Implement multi-level rate limiting:**

1. **Per-agent rate limit** (e.g., 100 req/sec per agent_id)
2. **Global rate limit** (e.g., 1000 req/sec total)
3. **Priority queues** (critical operations fast-tracked)

### Implementation Layers

```
Request → Nginx (L7) → OPA (L6) → TBP Logic
            ↓             ↓           ↓
        Rate limit   Resource    Priority
        (per IP)     quota       queue
```

**Layer 1: Nginx**
- Limit per source IP
- Drop obviously malicious traffic

**Layer 2: Kubernetes**
- Resource quotas (CPU, memory)
- TBP pod cannot be starved by agent pod

**Layer 3: OPA**
- Request prioritization
- Critical operations (weapons, critical infrastructure) fast-tracked

### Alternatives Considered

**Option A: No rate limiting (v4.1)**
- Pro: Simple, no overhead
- Con: Vulnerable to DoS

**Option B: Simple global limit**
- Pro: Easy to implement
- Con: Legitimate users affected by attack

**Option C: Multi-level (v4.2)**
- Pro: Surgical defense
- Con: More complex

### Consequences

**✅ Benefits:**
- DoS protection
- Fair resource allocation
- Critical operations protected

**❌ Costs:**
- Configuration complexity (tune limits)
- May limit legitimate high-frequency trading
- Monitoring required

**⚖️ Trade-off accepted:**
Availability > unlimited throughput.

---

## ADR-007: Read-Only Policy Files

### Context

**Problem:** If attacker gains write access to policy files, they can weaken TBP.

**Attack:**
```bash
# Attacker modifies policy
echo "allow = true" > tbp_core.rego

# TBP now allows everything
```

### Decision

**Make policy files immutable at runtime:**

1. **Kubernetes:** Use read-only ConfigMaps
2. **Docker:** Mount policies as read-only volumes
3. **Filesystem:** Set immutable attribute
4. **Hash verification:** Verify hash at load

```yaml
# Kubernetes
configMap:
  name: tbp-policies
  immutable: true
  data:
    tbp_core.rego: |
      # Policy content
```

### Verification at Load

```python
# Before loading policy
expected_hash = fetch_from_blockchain("tbp-v4.2-official-hash")
actual_hash = sha256(read_file("tbp_core.rego"))

if actual_hash != expected_hash:
    raise SecurityLockdown("Policy file compromised!")
```

### Alternatives Considered

**Option A: Normal file permissions (v4.1)**
- Pro: Simple
- Con: Root can modify

**Option B: Read-only mount (v4.2)**
- Pro: OS-enforced
- Con: Still modifiable with enough privilege

**Option C: Hash verification (v4.2)**
- Pro: Detect any modification
- Con: Requires trusted hash source

**Option D: All of the above (v4.2)**
- Pro: Defense in depth
- Con: Most complex

**We chose D (all layers).**

### Consequences

**✅ Benefits:**
- Multiple independent protections
- Detects tampering at load time
- Fail-safe (lockdown if compromised)

**❌ Costs:**
- Cannot hot-reload policies (restart required)
- Must manage hash distribution
- More deployment complexity

**⚖️ Trade-off accepted:**
Security > hot-reload convenience.

---

## ADR-008: Test-Driven Security

### Context

**Problem:** Security bugs are expensive. Post-deployment patches are:
- Embarrassing (reputation damage)
- Risky (downtime during emergency patching)
- Expensive (incident response costs)

**Better:** Catch vulnerabilities before deployment.

### Decision

**Adversarial test suite as first-class requirement.**

Every feature must include:
1. **Functionality tests** (does it work?)
2. **Adversarial tests** (can attacker break it?)
3. **Performance tests** (does it scale?)

### Test Categories

**1. Policy Poisoning Tests**
```python
def test_detect_modified_policy():
    # Attacker modifies policy file
    modify_file("tbp_core.rego", "allow = true")
    
    # System should detect and refuse to start
    with pytest.raises(SecurityLockdown):
        load_policy("tbp_core.rego")
```

**2. Salami Attack Tests**
```python
def test_cumulative_threshold():
    # 1000 small transactions
    for i in range(1000):
        result = check_action(amount=9999)
    
    # First 10: ✅ allowed
    # After cumulative > threshold: ❌ denied
    assert result.allowed == False
```

**3. DoS Tests**
```python
def test_rate_limiting():
    # Flood with 10,000 requests
    responses = [make_request() for _ in range(10000)]
    
    # Some should be rate-limited
    rate_limited = [r for r in responses if r.status == 429]
    assert len(rate_limited) > 0
```

### Required Coverage

- **Unit tests:** 80% code coverage minimum
- **Integration tests:** All critical paths
- **Adversarial tests:** All known attack vectors
- **Performance tests:** All bottlenecks

### Alternatives Considered

**Option A: Manual security review**
- Pro: Expert judgment
- Con: Slow, expensive, not repeatable

**Option B: Automated testing (v4.2)**
- Pro: Fast, cheap, repeatable
- Con: Can't catch unknown attacks

**Option C: Both**
- Pro: Best of both
- Con: Most expensive

**We chose B now, C later (external audit for v5.0).**

### Consequences

**✅ Benefits:**
- Catch bugs early (cheap to fix)
- Regression prevention (tests run on every commit)
- Documentation (tests show intended behavior)

**❌ Costs:**
- More code to write (tests ~= production code)
- Slower initial development
- Test maintenance burden

**⚖️ Trade-off accepted:**
Quality > speed. Security cannot be compromised.

---

## ADR-009: Production Merkle Tree Implementation

### Context

**Problem:** Standard Merkle Tree implementations often have edge cases with odd-numbered leaves or timezone inconsistencies that lead to non-deterministic roots across different environments.

**Security Risk:** If two auditors compute different roots for the same data due to implementation details (system timezone, leaf balancing logic), the audit trail's trust is compromised.

### Decision

**Implement a strictly deterministic Merkle Tree with the following properties:**

1.  **Strict UTC Enforcement**: All timestamps are converted to ISO 8601 UTC using `datetime.now(timezone.utc)`.
2.  **Deterministic Balancing**: For odd-numbered leaf nodes, the last node is duplicated to maintain a balanced binary tree (following best practices for Merkle Trees).
3.  **Hashed Signatures**: Signatures are hashed as part of the leaf data to ensure the signature itself is protected by the tree.
4.  **RFC 3161 Integration**: External TSA tokens are stored as part of the leaf metadata to provide non-repudiation of time.

### Alternatives Considered

- **Dynamic Balancing (No duplication)**: More complex to implement verifiably and less standard.
- **System Timezone**: Rejected due to non-determinism across global deployments.

### Consequences

**✅ Benefits:**
- Absolute determinism: identical logs always produce identical roots.
- Verifiable by third-party auditors without custom logic.
- External time certification (TSA) integrated.

**❌ Costs:**
- Small overhead for node duplication in odd trees.
- Slightly larger audit file due to TSA tokens.

---

## Decision Summary Table

| ADR | Decision | Primary Benefit | Primary Cost |
|-----|----------|-----------------|--------------|
| 001 | HSM for keys | Physical key security | Hardware cost |
| 002 | Merkle + Chain | Tamper detection | Complexity |
| 003 | Separate signing | Defense in depth | More components |
| 004 | Backward compat | Zero-downtime migration | Temporary code complexity |
| 005 | Pattern analysis | Salami attack detection | False positives |
| 006 | Rate limiting | DoS protection | Configuration complexity |
| 007 | Read-only policies | Policy integrity | No hot-reload |
| 008 | Test-driven security | Early bug detection | Development time |
| 009 | Production Merkle | Deterministic roots | Storage overhead |

---

## Open Questions (To Be Decided)

**Q1: Should HSM be mandatory for production?**
- Option A: Mandatory (strict)
- Option B: Recommended (flexible)
- Decision pending: Community feedback

**Q2: What should cumulative window be?**
- Current: 24 hours (default)
- Configurable: Yes
- Guidance needed: Industry-specific recommendations

**Q3: How to distribute official policy hashes?**
- Option A: GitHub releases
- Option B: Blockchain
- Option C: Both
- Decision pending: v5.0

---

## How to Propose a New ADR

1. Open GitHub Discussion with "ADR Proposal" label
2. Include: Context, Options, Recommendation
3. Gather feedback (1-2 weeks)
4. If consensus: Create PR adding ADR-NNN section
5. Merge after review

**All ADRs are living documents. They can be updated as we learn.**

---

**Document Status:** Draft (feedback welcome)  
**Next Review:** After v4.2 release  
**Maintainer:** @philippeabraxas-jpg
