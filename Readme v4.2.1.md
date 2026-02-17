# Trusted Behavioral Protocol (TBP) v4.2.1 "Shield-Hardening"

[![Version](https://img.shields.io/badge/version-4.2.1-blue.svg)](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/releases)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/actions)
[![Coverage](https://img.shields.io/badge/coverage-87%25-green.svg)](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Production-grade cryptographic enforcement for AI agent decisions.**

TBP v4.2 provides tamper-evident audit trails, hardware-backed signatures, and trusted timestamps to ensure AI agents operate within defined behavioral boundaries—even under adversarial conditions.

---

## 🆕 What's New in v4.2.1

### Core Security Modules (Production-Ready)

1. **🔐 Hardware Security Module (HSM) Integration**
   - Hardware-backed digital signatures
   - PKCS#11 support (YubiKey, AWS CloudHSM, Azure Key Vault)
   - Software fallback for development
   - Replay attack protection with agent_id binding

2. **⏰ RFC 3161 Trusted Timestamps**
   - Cryptographically certified timestamps
   - Multiple TSA support with failover
   - Cache integrity validation
   - Time drift detection

3. **🔗 Merkle Audit Chain**
   - Blockchain-style chain linking
   - Tamper-evident log storage
   - Efficient integrity verification
   - Root publication tracking

### Security Enhancements

- ✅ **10 Gemini security patches** applied
- ✅ **Production mode enforcement** (blocks unsafe configurations)
- ✅ **Signature replay protection** (agent_id binding)
- ✅ **Time manipulation defense** (external timestamps)
- ✅ **Tamper detection** (Merkle proofs)

### Testing & Quality

- ✅ **56 unit tests** (all passing)
- ✅ **87% code coverage**
- ✅ **Adversarial tests** (attack simulations)
- ✅ **Performance benchmarks** (>1000 ops/sec)

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol.git
cd Responsible-Alliance-Protocol/tbp-v4-hard-shield

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "
from core.hsm_signer import HSMSigner
from core.time_attester import TimeAttester
from core.merkle_audit import MerkleAuditChain
print('✅ TBP v4.2.1 installed successfully')
"
```

### Basic Usage

```python
from core.hsm_signer import HSMSigner, HSMType
from core.time_attester import TimeAttester, TSAType
from core.merkle_audit import MerkleAuditChain
import json

# Initialize components
signer = HSMSigner(hsm_type=HSMType.SOFTWARE)  # Use real HSM in production
attester = TimeAttester(tsa_type=TSAType.FREETSA)
chain = MerkleAuditChain(storage_path="audit.json")

# AI agent makes a decision
decision = {
    "agent_id": "trading-bot-001",
    "action": "transfer",
    "amount": 50000,
    "to": "account-xyz",
    "timestamp": "2026-02-13T10:00:00Z"
}

# 1. Get trusted timestamp
data_bytes = json.dumps(decision).encode()
ts_token = attester.get_trusted_timestamp(data_bytes)

# 2. Sign with HSM
signature = signer.sign(
    data_bytes,
    agent_id=decision["agent_id"],
    timestamp=ts_token.timestamp.timestamp()
)

# 3. Add to tamper-evident chain
chain.append(
    decision,
    signature=signature.signature,
    timestamp=ts_token.timestamp,
    tsa_token=ts_token
)

# 4. Publish Merkle root (to blockchain, Twitter, etc.)
root = chain.get_root()
print(f"Merkle root: {root[:32]}...")  # Publish this!

# Later: Verify integrity
is_valid, errors = chain.verify_integrity()
assert is_valid, f"Tampering detected: {errors}"

# Cleanup
signer.close()
attester.close()
```

---

## 📚 Documentation

### Core Modules

- **[HSM Signer](core/hsm_signer.py)** - Hardware-backed signatures ([Security Patches](docs/HSM_SIGNER_SECURITY_PATCHES.md))
- **[Time Attester](core/time_attester.py)** - RFC 3161 timestamps ([Quick Start](core/TIME_ATTESTER_QUICKSTART.md))
- **[Merkle Audit](core/merkle_audit.py)** - Tamper-evident chain

### Architecture & Design

- **[Architecture Decisions](docs/ARCHITECTURE_DECISIONS.md)** - 8 ADRs explaining design choices
- **[Migration Guide](docs/MIGRATION_GUIDE.md)** - How to migrate from v4.1 to v4.2
- **[Testing Guide](docs/TESTING_V4.2.md)** - Comprehensive test documentation

### Integration Examples

- **[LangChain Integration](integrations/langchain_integration.py)** - Use TBP with LangChain agents
- **[AutoGen Integration](integrations/autogen_integration.py)** - Use TBP with AutoGen
- **[FastAPI Middleware](integrations/fastapi_middleware.py)** - REST API enforcement

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent Decision                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Policy Evaluation   │
         │   (OPA Rego Rules)    │
         └───────────┬───────────┘
                     │
                     ▼
              ┌──────────────┐
              │  HSM Signer  │ ◄─── Hardware-backed signature
              └──────┬───────┘
                     │
                     ▼
            ┌────────────────┐
            │ Time Attester  │ ◄─── RFC 3161 certified timestamp
            └────────┬───────┘
                     │
                     ▼
           ┌──────────────────┐
           │  Merkle Chain    │ ◄─── Tamper-evident storage
           └──────────┬───────┘
                      │
                      ▼
            ┌──────────────────┐
            │  Publish Root    │ ◄─── Public verification
            │ (Blockchain/Web) │
            └──────────────────┘
```

---

## 🔒 Security Model

### Threat Model

TBP v4.2 protects against:

- ✅ **Policy Poisoning** - Modified .rego files detected
- ✅ **Salami Attacks** - Cumulative tracking prevents small repeated violations
- ✅ **DoS Attacks** - Rate limiting and priority queues
- ✅ **Log Tampering** - Merkle chain detects modifications
- ✅ **Replay Attacks** - agent_id binding prevents signature reuse
- ✅ **Time Manipulation** - External RFC 3161 timestamps
- ✅ **Controller Usurpation** - Invariants prevent privilege escalation
- ✅ **Surveillance** - Sensor access requires explicit authorization

### Defense in Depth

1. **Policy Layer** (OPA Rego) - Block unauthorized actions
2. **Cryptographic Layer** (HSM) - Unforgeable signatures
3. **Audit Layer** (Merkle) - Tamper detection
4. **Time Layer** (RFC 3161) - Timestamp certification
5. **Publication Layer** - Public root verification

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=core --cov-report=html

# Run adversarial tests only
pytest tests/adversarial/ -v

# Run with real TSA (requires internet)
pytest tests/unit/test_time_attester.py --run-network-tests

# Automated validation
python validate_v42.py
```

**Expected results:**
- ✅ 56+ tests passing
- ✅ 87% coverage
- ✅ 0 critical failures

---

## 📦 Deployment

### Docker Compose (Recommended)

```bash
cd deployment
docker-compose up -d
```

### Kubernetes

```bash
cd deployment/kubernetes
kubectl apply -f namespace.yaml
kubectl apply -f .
```

See **[Deployment Guide](deployment/README.md)** for details.

---

## 🔄 Migration from v4.1

### Backward Compatibility

v4.2 is **100% backward compatible** with v4.1 via the compatibility layer:

```python
from integrations.backward_v4.1 import TBPLogSigner

# Works with both v4.1 and v4.2
signer = TBPLogSigner()  # Auto-detects version
signature = signer.sign(data)
```

### Migration Steps

1. **Week 1:** Deploy v4.2 alongside v4.1 (dual routing)
2. **Week 2:** Route 10% → 50% → 100% traffic to v4.2
3. **Week 3:** Monitor metrics, rollback if issues
4. **Week 4:** Deprecate v4.1

See **[Migration Guide](docs/MIGRATION_GUIDE.md)** for complete instructions.

---

## 🤝 Contributing

We welcome contributions! See:

- **[Contributing Guide](CONTRIBUTING.md)**
- **[Code of Conduct](CODE_OF_CONDUCT.md)**
- **[Open Issues](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues)**

### Priority Areas

- 🔍 **Help Wanted:** Cloud deployment guides ([Issue #7](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues/7))
- 🌍 **Help Wanted:** Translate docs to French/Spanish/Chinese ([Issue #5](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues/5))
- 🤖 **Help Wanted:** AutoGen enforcement implementation

---

## 📈 Roadmap

### v4.2.1 (Current) ✅
- HSM Integration
- RFC 3161 Timestamps
- Merkle Audit Chain
- Production hardening

### v4.3 (Q1 2026)
- Pattern analysis for salami attacks
- Real-time anomaly detection
- Advanced rate limiting

### v5.0 (Q2 2026)
- Governance framework
- Multi-stakeholder policies
- Formal verification
- Compliance automation

---

## 📊 Performance

**Benchmarks (on i7-10th gen, 16GB RAM):**

| Operation | Throughput | Latency |
|-----------|------------|---------|
| HSM Signature (software) | 125 ops/sec | 8ms |
| Timestamp (mock) | 5000 ops/sec | 0.2ms |
| Timestamp (real TSA) | 2 ops/sec | 500ms |
| Merkle append | 2341 ops/sec | 0.4ms |
| Merkle verify | 1850 ops/sec | 0.5ms |

**Production recommendations:**
- Use hardware HSM: 50-100 ops/sec
- Cache timestamps: 500+ ops/sec
- Batch Merkle appends: 5000+ ops/sec

---

## 📄 License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

**Core Contributors:**
- Philippe Abraxas - Architecture & Product
- Claude (Anthropic) - Core modules implementation
- Gemini (Google) - Security review & patches
- Deepseek - Initial HSM implementation
- Caetano - Testing & validation
- Sharayu - Kubernetes deployment

**Security Review:**
- Gemini AI - 10 critical patches identified and fixed
- Community security audits

**Inspiration:**
- [Open Policy Agent](https://www.openpolicyagent.org/)
- [RFC 3161](https://www.ietf.org/rfc/rfc3161.txt) - Time-Stamp Protocol
- [PKCS#11](http://docs.oasis-open.org/pkcs11/pkcs11-base/v2.40/pkcs11-base-v2.40.html)

---

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues)
- **Discussions:** [GitHub Discussions](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/discussions)
- **Security:** [SECURITY.md](SECURITY.md) (responsible disclosure)

---

## 🌟 Star History

If TBP helps your AI safety efforts, please star the repo! ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=philippeabraxas-jpg/Responsible-Alliance-Protocol&type=Date)](https://star-history.com/#philippeabraxas-jpg/Responsible-Alliance-Protocol)

---

**Built with ❤️ for safer AI agents**

*"Trust, but verify. Even for AI."*
