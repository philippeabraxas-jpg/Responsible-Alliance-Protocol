# Testing Guide - v4.2 "Shield-Hardening"

**Purpose:** Ensure v4.2 survives adversarial attacks  
**Audience:** QA engineers, security testers, contributors  
**Philosophy:** If we can't break it, attackers won't either

---

## 🎯 Testing Philosophy

**v4.1 testing:** Does it work correctly?  
**v4.2 testing:** Can attacker break it?

**Key difference:**
- v4.1: Test happy paths + edge cases
- v4.2: Test attack scenarios + failure modes

**Mindset:** Think like an attacker, not a user.

---

## 📋 Test Categories

### 1. Functionality Tests (Does it work?)
- Unit tests (individual functions)
- Integration tests (components together)
- End-to-end tests (full system)

### 2. Adversarial Tests (Can attacker break it?)
- Policy poisoning attacks
- Salami attacks
- DoS attacks
- Tampering detection

### 3. Performance Tests (Does it scale?)
- Latency benchmarks
- Throughput tests
- Resource usage

### 4. Compliance Tests (Does it meet requirements?)
- Backward compatibility
- Migration integrity
- Security standards

---

## 🧪 Test Suite Structure

```
tests/
├── unit/                       # Fast, isolated tests
│   ├── test_hsm_signer.py
│   ├── test_merkle_audit.py
│   └── test_pattern_analysis.py
│
├── integration/                # Components together
│   ├── test_hsm_merkle_flow.py
│   ├── test_backward_compat.py
│   └── test_policy_loading.py
│
├── adversarial/                # Attack simulations
│   ├── test_policy_poisoning.py
│   ├── test_salami_attack.py
│   ├── test_dos_attack.py
│   └── test_tampering.py
│
├── performance/                # Benchmarks
│   ├── test_latency.py
│   ├── test_throughput.py
│   └── test_memory.py
│
└── compliance/                 # Requirements
    ├── test_v41_compat.py
    ├── test_migration.py
    └── test_security_standards.py
```

---

## 1️⃣ Unit Tests

**Goal:** Test individual components in isolation

### test_hsm_signer.py

```python
"""
Unit tests for HSM signer.

Coverage:
- Key generation
- Signing
- Verification
- Error handling
"""

import pytest
from core.hsm_signer import HSMSigner, HSMType, HSMSigningError

def test_software_fallback():
    """Test software mode (development)"""
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    
    data = b"Test log entry"
    signature = signer.sign(data)
    
    assert signer.verify(data, signature) == True

def test_modified_data_fails():
    """Test that modified data fails verification"""
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    
    data = b"Original data"
    signature = signer.sign(data)
    
    # Attacker modifies data
    tampered = b"Tampered data"
    
    assert signer.verify(tampered, signature) == False

def test_invalid_signature_fails():
    """Test that invalid signature fails"""
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    
    data = b"Test data"
    fake_signature = b"fake" * 64  # Fake 256-byte signature
    
    assert signer.verify(data, fake_signature) == False

def test_yubikey_connection():
    """Test YubiKey HSM connection"""
    pytest.skip("Requires YubiKey hardware")
    
    # Only runs if YubiKey present
    signer = HSMSigner(
        hsm_type=HSMType.YUBIKEY,
        pin="123456"
    )
    
    assert signer.session is not None

def test_hsm_error_handling():
    """Test HSM connection failures"""
    with pytest.raises(HSMConnectionError):
        signer = HSMSigner(
            hsm_type=HSMType.YUBIKEY,
            pin="wrong_pin"
        )

def test_public_key_export():
    """Test public key can be exported"""
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    
    public_key = signer.get_public_key()
    
    assert public_key.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert len(public_key) > 200  # Reasonable key size

# TODO (Caetano): Add 10+ more unit tests
```

### test_merkle_audit.py

```python
"""
Unit tests for Merkle audit chain.

Coverage:
- Chain building
- Hash computation
- Integrity verification
- Tampering detection
"""

import pytest
from core.merkle_audit import MerkleAuditChain, AuditEntry, ChainIntegrityError

def test_empty_chain():
    """Test empty chain initialization"""
    chain = MerkleAuditChain()
    
    assert len(chain.entries) == 0
    assert chain.verify_integrity() == True

def test_single_entry():
    """Test chain with single entry"""
    chain = MerkleAuditChain()
    
    chain.append({"action": "test"})
    
    assert len(chain.entries) == 1
    assert chain.verify_integrity() == True

def test_chain_linkage():
    """Test entries are properly linked"""
    chain = MerkleAuditChain()
    
    chain.append({"entry": 1})
    chain.append({"entry": 2})
    chain.append({"entry": 3})
    
    # Each entry should reference previous
    assert chain.entries[1].previous_hash == chain.entries[0].hash
    assert chain.entries[2].previous_hash == chain.entries[1].hash

def test_detect_modified_data():
    """Test tampering detection"""
    chain = MerkleAuditChain()
    
    chain.append({"value": 100})
    chain.append({"value": 200})
    
    # Attacker modifies entry
    chain.entries[0].data["value"] = 999
    
    # Should detect tampering
    assert chain.verify_integrity() == False

def test_detect_deleted_entry():
    """Test deletion detection"""
    chain = MerkleAuditChain()
    
    chain.append({"entry": 1})
    chain.append({"entry": 2})
    chain.append({"entry": 3})
    
    # Attacker deletes middle entry
    del chain.entries[1]
    
    # Should detect broken chain
    assert chain.verify_integrity() == False

def test_merkle_root_changes():
    """Test root changes when data changes"""
    chain = MerkleAuditChain()
    
    chain.append({"data": "original"})
    root1 = chain.get_root()
    
    chain.append({"data": "new"})
    root2 = chain.get_root()
    
    assert root1 != root2  # Root should change

def test_merkle_proof():
    """Test Merkle proof generation/verification"""
    chain = MerkleAuditChain()
    
    for i in range(10):
        chain.append({"entry": i})
    
    # Get proof for entry #5
    entry = chain.entries[5]
    proof = chain.get_proof(5)
    root = chain.get_root()
    
    # Verify proof
    assert chain.verify_proof(entry, proof, root) == True

# TODO (Caetano): Add 10+ more unit tests
```

---

## 2️⃣ Adversarial Tests

**Goal:** Simulate real attacks

### test_policy_poisoning.py

```python
"""
Test defenses against policy modification attacks.

Attack: Attacker modifies .rego files to weaken TBP.
Defense: Hash verification, immutable mount, fail-closed.
"""

import pytest
import hashlib
from policy_engine.loader import load_policy, SecurityLockdown

def test_detect_modified_policy():
    """Test system detects modified policy file"""
    
    # Setup: Create policy with known hash
    policy_content = "package tbp; allow = true"
    expected_hash = hashlib.sha256(policy_content.encode()).hexdigest()
    
    # Attacker modifies policy
    malicious_content = "package tbp; allow = true; # backdoor"
    
    # System should detect mismatch
    with pytest.raises(SecurityLockdown):
        load_policy(malicious_content, expected_hash)

def test_immutable_configmap():
    """Test Kubernetes ConfigMap is immutable"""
    pytest.skip("Requires Kubernetes")
    
    # Try to modify ConfigMap
    # Should fail (immutable: true)

def test_read_only_mount():
    """Test policy files are read-only"""
    pytest.skip("Requires deployed environment")
    
    # Try to write to policy file
    # Should fail (permission denied)

def test_fail_closed_on_compromise():
    """Test system locks down if policy compromised"""
    
    # Simulate compromised policy
    with pytest.raises(SecurityLockdown):
        load_policy("COMPROMISED", "expected_hash")
    
    # System should be locked, not running with bad policy

# TODO (Caetano): Add scenarios for:
# - Attacker changes thresholds
# - Attacker adds backdoor rules
# - Attacker disables logging
```

### test_salami_attack.py

```python
"""
Test defenses against salami attacks (death by 1000 cuts).

Attack: Many small violations below detection threshold.
Defense: Sliding window cumulative tracking.
"""

import pytest
from policy_engine.pattern_analysis import PatternAnalyzer

def test_cumulative_threshold():
    """Test cumulative limit over sliding window"""
    
    analyzer = PatternAnalyzer(
        window_hours=24,
        cumulative_limit=100000  # $100k
    )
    
    # Simulate 1000 small transactions
    for i in range(1000):
        result = analyzer.check_transaction(
            agent_id="bot-001",
            amount=9999  # Just under $10k individual limit
        )
        
        # First few should be allowed
        if i < 10:
            assert result.allowed == True
        
        # After cumulative > $100k, should deny
        if analyzer.get_cumulative("bot-001") > 100000:
            assert result.allowed == False
            break

def test_frequency_detection():
    """Test rapid transaction detection"""
    
    analyzer = PatternAnalyzer(
        frequency_limit=10  # 10 per hour
    )
    
    # Simulate rapid transactions
    for i in range(20):
        result = analyzer.check_transaction(
            agent_id="bot-002",
            amount=5000,
            timestamp=f"2026-02-08T10:00:{i:02d}Z"  # 1 per second
        )
    
    # Should be rate-limited
    denied = [r for r in results if not r.allowed]
    assert len(denied) >= 10  # At least half denied

def test_pattern_across_agents():
    """Test coordinated attack across multiple agents"""
    
    analyzer = PatternAnalyzer()
    
    # Simulate coordinated attack (10 agents, each $99k)
    for agent_id in range(10):
        for tx in range(10):
            analyzer.check_transaction(
                agent_id=f"bot-{agent_id:03d}",
                amount=9900,  # $9.9k each
                recipient="same_attacker_account"
            )
    
    # Should detect pattern (same recipient, coordinated timing)
    assert analyzer.detect_coordination() == True

# TODO (Caetano): Add scenarios for:
# - Attacker waits between transactions (slow salami)
# - Attacker uses multiple recipients
# - Attacker spreads across days
```

### test_dos_attack.py

```python
"""
Test defenses against Denial of Service attacks.

Attack: Flood TBP with requests to make it unusable.
Defense: Rate limiting, priority queues, resource quotas.
"""

import pytest
import time
import concurrent.futures
from policy_engine.rate_limiter import RateLimiter

def test_per_agent_rate_limit():
    """Test rate limiting per agent_id"""
    
    limiter = RateLimiter(limit=100)  # 100 req/sec
    
    agent_id = "bot-001"
    
    # Send 1000 requests rapidly
    start = time.time()
    results = []
    
    for i in range(1000):
        result = limiter.check_request(agent_id)
        results.append(result)
    
    elapsed = time.time() - start
    
    # Should have rate-limited (not all allowed)
    allowed = [r for r in results if r.allowed]
    assert len(allowed) < 1000
    
    # Should respect rate (roughly 100/sec)
    expected_allowed = int(100 * elapsed)
    assert abs(len(allowed) - expected_allowed) < 20  # Allow 20% variance

def test_global_rate_limit():
    """Test global rate limit across all agents"""
    
    limiter = RateLimiter(
        per_agent_limit=100,
        global_limit=500  # 500 req/sec total
    )
    
    # Simulate 10 agents flooding
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for agent_id in range(10):
            future = executor.submit(
                lambda: [limiter.check_request(f"bot-{agent_id:03d}") for _ in range(100)]
            )
            futures.append(future)
        
        results = [r for f in futures for r in f.result()]
    
    # Should enforce global limit
    allowed = [r for r in results if r.allowed]
    assert len(allowed) <= 550  # Allow some burst

def test_priority_queue():
    """Test critical operations bypass rate limit"""
    
    limiter = RateLimiter(limit=10)
    
    # Fill rate limit with low-priority requests
    for i in range(20):
        limiter.check_request("bot-001", priority="low")
    
    # Critical request should still go through
    result = limiter.check_request("bot-002", priority="critical")
    assert result.allowed == True

def test_resource_isolation():
    """Test TBP resources isolated from agent"""
    pytest.skip("Requires Kubernetes deployment")
    
    # Try to exhaust TBP pod resources from agent pod
    # Should fail (ResourceQuota prevents)

# TODO (Caetano): Add scenarios for:
# - Distributed DoS (many IPs)
# - Slowloris attack (slow requests)
# - Memory exhaustion
```

### test_tampering.py

```python
"""
Test detection of log tampering.

Attack: Modify historical logs after the fact.
Defense: Merkle chain, cryptographic signatures.
"""

import pytest
from core.merkle_audit import MerkleAuditChain

def test_detect_data_modification():
    """Test tampering with log data is detected"""
    
    chain = MerkleAuditChain()
    
    # Add legitimate logs
    for i in range(100):
        chain.append({"transaction": i, "amount": 1000})
    
    # Attacker modifies log #50
    chain.entries[50].data["amount"] = 999999
    
    # Should detect
    assert chain.verify_integrity() == False

def test_detect_timestamp_modification():
    """Test tampering with timestamp is detected"""
    
    chain = MerkleAuditChain()
    
    chain.append({"event": "test"})
    
    # Attacker changes timestamp
    chain.entries[0].timestamp = "2025-01-01T00:00:00Z"
    
    # Hash includes timestamp, should detect
    assert chain.verify_integrity() == False

def test_detect_signature_forgery():
    """Test forged signature is detected"""
    
    chain = MerkleAuditChain()
    
    chain.append({"data": "original"})
    
    # Attacker forges signature
    chain.entries[0].signature = b"fake" * 32
    
    # Should detect invalid signature
    from core.hsm_signer import HSMSigner
    signer = HSMSigner()
    assert signer.verify(
        chain.entries[0].data,
        chain.entries[0].signature
    ) == False

def test_detect_chain_reordering():
    """Test reordering logs is detected"""
    
    chain = MerkleAuditChain()
    
    chain.append({"order": 1})
    chain.append({"order": 2})
    chain.append({"order": 3})
    
    # Attacker swaps entries 1 and 2
    chain.entries[1], chain.entries[2] = chain.entries[2], chain.entries[1]
    
    # Should detect (previous_hash won't match)
    assert chain.verify_integrity() == False

# TODO (Caetano): Add scenarios for:
# - Attacker replays old logs
# - Attacker inserts new logs into middle
# - Attacker deletes range of logs
```

---

## 3️⃣ Performance Tests

**Goal:** Ensure scalability

### test_latency.py

```python
"""
Latency benchmarks.

Requirement: < 10ms per decision (same as v4.1)
"""

import pytest
import time
from policy_engine import check_action

def test_decision_latency():
    """Test single decision latency"""
    
    # Warm up
    for _ in range(10):
        check_action(domain="finance", operation="trade", transaction_value=5000)
    
    # Measure
    latencies = []
    for _ in range(1000):
        start = time.time()
        check_action(domain="finance", operation="trade", transaction_value=5000)
        elapsed = (time.time() - start) * 1000  # ms
        latencies.append(elapsed)
    
    # Stats
    p50 = sorted(latencies)[500]
    p95 = sorted(latencies)[950]
    p99 = sorted(latencies)[990]
    
    print(f"Latency p50: {p50:.2f}ms")
    print(f"Latency p95: {p95:.2f}ms")
    print(f"Latency p99: {p99:.2f}ms")
    
    # Requirements
    assert p50 < 10, "p50 latency exceeds 10ms"
    assert p95 < 20, "p95 latency exceeds 20ms"
    assert p99 < 50, "p99 latency exceeds 50ms"

def test_hsm_signing_latency():
    """Test HSM signing overhead"""
    
    from core.hsm_signer import HSMSigner
    
    signer = HSMSigner()
    data = b"Test log entry"
    
    # Measure signing latency
    latencies = []
    for _ in range(100):
        start = time.time()
        signer.sign(data)
        elapsed = (time.time() - start) * 1000
        latencies.append(elapsed)
    
    avg = sum(latencies) / len(latencies)
    
    print(f"HSM signing latency: {avg:.2f}ms")
    
    # HSM slower than software, but should be < 5ms
    assert avg < 5, "HSM signing too slow"

# TODO (Caetano): Add more performance tests
```

---

## 4️⃣ Running Tests

### Automated Validation (Recommended)

The most reliable way to verify a v4.2 deployment is the integrated validation script, which covers performance, DoS protection, pattern analysis, and full audit flow:

```bash
cd tbp-v4-hard-shield
python tests/validate_v42.py
```

### Local Development (Pytest)

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: TBP v4.2 Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pytest tests/unit/ -v
  
  adversarial-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pytest tests/adversarial/ -v
  
  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pytest tests/performance/ -v
```

---

## 📊 Test Coverage Requirements

**Minimum coverage:**
- Unit tests: 80% code coverage
- Integration tests: All critical paths
- Adversarial tests: All known attack vectors
- Performance tests: All bottlenecks

**Coverage report:**
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

---

## ✅ Definition of Done

**Feature is complete only if:**

- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Adversarial tests written and passing
- [ ] Performance benchmarks meet requirements
- [ ] Code coverage > 80%
- [ ] All tests pass in CI/CD
- [ ] Manual testing completed
- [ ] Security review completed

---

## 🎓 For Contributors

**Before submitting PR:**

1. Write tests FIRST (TDD)
2. Ensure all tests pass locally
3. Check code coverage
4. Run adversarial tests
5. Benchmark performance
6. Document any new test requirements

**PR will be rejected if:**
- Tests missing
- Coverage < 80%
- Adversarial tests skipped
- Performance regression

---

**Document Version:** 1.0  
**Last Updated:** February 8, 2026
