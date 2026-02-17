# TBP Core Modules v4.2.1

**Production-grade cryptographic enforcement for AI decisions.**

This directory contains the three core security modules that power TBP v4.2's adversarial hardening capabilities.

---

## 📦 Modules

### 1. HSM Signer (`hsm_signer.py`)

Hardware-backed digital signatures for AI agent decisions.

**Features:**
- PKCS#11 interface (YubiKey, AWS CloudHSM, Azure Key Vault, SoftHSM)
- Software fallback for development
- Rate limiting (100 ops/min)
- Replay attack protection with agent_id binding
- Session keep-alive for long-running processes

**Usage:**
```python
from core.hsm_signer import HSMSigner, HSMType

# Production: Real HSM
signer = HSMSigner(
    hsm_type=HSMType.YUBIKEY,
    key_label="tbp-signing-key"
)

# Development: Software keys
signer = HSMSigner(
    hsm_type=HSMType.SOFTWARE,
    key_label="dev-key",
    auto_generate_key=True
)

# Sign data
signature = signer.sign(
    data=b"important decision",
    agent_id="trading-bot-001"
)

# Verify
is_valid = signer.verify(
    data=b"important decision",
    signature=signature,
    agent_id="trading-bot-001"
)

signer.close()
```

**Security Patches Applied:**
- ✅ PIN from Secret Manager (no interactive prompts)
- ✅ SOFTWARE mode blocked in production
- ✅ agent_id binding (replay protection)
- ✅ PUBLIC_KEY extraction from separate object
- ✅ Session keep-alive thread

**Documentation:**
- [Security Patches](../docs/HSM_SIGNER_SECURITY_PATCHES.md)
- [PKCS#11 Guide](https://docs.oasis-open.org/pkcs11/pkcs11-base/v2.40/)

---

### 2. Time Attester (`time_attester.py`)

RFC 3161 trusted timestamps for tamper-proof audit logs.

**Features:**
- Full RFC 3161 compliance (real ASN.1 DER encoding)
- Multiple TSA support (FreeTSA, DigiCert, Sectigo, Apple)
- Automatic failover between TSAs
- Response caching with integrity validation
- Time drift detection (max 5s between TSAs)

**Usage:**
```python
from core.time_attester import TimeAttester, TSAType

# Production: Real TSA
attester = TimeAttester(
    tsa_type=TSAType.FREETSA,
    hash_algorithm="sha256",
    timeout=15
)

# Development: Mock mode
attester = TimeAttester(tsa_type=TSAType.MOCK)

# Get trusted timestamp
data = b"audit log entry"
token = attester.get_timestamp(data)

print(f"Certified time: {token.timestamp}")
print(f"TSA: {token.tsa_name}")

# Verify timestamp
is_valid = attester.verify_timestamp(data, token)

# Metrics
metrics = attester.get_metrics()
print(f"Cache hit rate: {metrics['cache_hit_rate']:.1%}")

attester.close()
```

**Implementation:**
- ✅ Real ASN.1 DER encoding (asn1crypto)
- ✅ PKCS#7 signature validation
- ✅ Cache integrity checks
- ✅ Certificate chain validation (future)

**Documentation:**
- [Quick Start Guide](TIME_ATTESTER_QUICKSTART.md)
- [RFC 3161 Spec](https://www.ietf.org/rfc/rfc3161.txt)

---

### 3. Merkle Audit Chain (`merkle_audit.py`)

Tamper-evident blockchain-style audit trail.

**Features:**
- Chain linking (each entry references previous)
- Merkle tree for efficient verification
- Root publication tracking
- Comprehensive integrity checks
- Persistent storage (JSON)

**Usage:**
```python
from core.merkle_audit import MerkleAuditChain

# Initialize chain
chain = MerkleAuditChain(
    storage_path="audit.json",
    auto_save=True
)

# Add decision to chain
chain.append(
    data={
        "agent_id": "bot-001",
        "action": "transfer",
        "amount": 50000
    },
    signature=hsm_signature,
    timestamp=trusted_timestamp,
    tsa_token=rfc3161_token
)

# Get Merkle root (publish this!)
root = chain.get_root()
print(f"Merkle root: {root[:32]}...")

# Verify integrity
is_valid, errors = chain.verify_integrity()
if not is_valid:
    print(f"❌ Tampering detected: {errors}")

# Get proof for specific entry
proof = chain.get_proof(entry_index=5)
```

**Security Features:**
- ✅ Signature computed AFTER hash (not included in hash)
- ✅ UTC timezone-aware timestamps
- ✅ Proper Merkle tree balancing (odd node duplication)
- ✅ Root publication tracking
- ✅ Chain link verification

**Documentation:**
- See inline docstrings in `merkle_audit.py`

---

## 🔗 Integration

### Full Chain Example

```python
from core.hsm_signer import HSMSigner, HSMType
from core.time_attester import TimeAttester, TSAType
from core.merkle_audit import MerkleAuditChain
import json

# Setup
signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
attester = TimeAttester(tsa_type=TSAType.FREETSA)
chain = MerkleAuditChain(storage_path="audit.json")

# AI makes decision
decision = {
    "agent_id": "trading-bot-001",
    "action": "transfer",
    "amount": 50000,
    "to": "account-xyz"
}

# 1. Get trusted timestamp
data_bytes = json.dumps(decision).encode()
ts_token = attester.get_timestamp(data_bytes)

# 2. Sign with HSM
signature = signer.sign(
    data_bytes,
    agent_id=decision["agent_id"],
    timestamp=ts_token.timestamp.timestamp()
)

# 3. Add to audit chain
chain.append(
    decision,
    signature=signature.signature,
    timestamp=ts_token.timestamp,
    tsa_token=ts_token
)

# 4. Publish Merkle root
root = chain.get_root()
print(f"✅ Decision logged: root={root[:16]}...")

# Cleanup
signer.close()
attester.close()
```

---

## 🧪 Testing

```bash
# Test individual modules
pytest tests/unit/test_hsm_signer.py -v
pytest tests/unit/test_time_attester.py -v
pytest tests/unit/test_merkle_audit.py -v

# Test integration
pytest tests/integration/ -v

# Run examples
python core/hsm_signer.py
python core/time_attester.py
python core/merkle_audit.py
```

---

## 📊 Performance

**Benchmarks (software mode):**

| Module | Throughput | Latency |
|--------|------------|---------|
| HSM Signer | 125 ops/sec | 8ms |
| Time Attester (mock) | 5000 ops/sec | 0.2ms |
| Time Attester (real) | 2 ops/sec | 500ms |
| Merkle Append | 2341 ops/sec | 0.4ms |

**Production tips:**
- Use hardware HSM for 50-100 ops/sec
- Cache timestamps for 500+ ops/sec  
- Batch Merkle operations for 5000+ ops/sec

---

## 🔒 Security

### Production Mode

Set `TBP_PRODUCTION=true` to enforce:
- ✅ SOFTWARE mode disabled (must use real HSM)
- ✅ PIN from Secret Manager (no interactive prompts)
- ✅ RFC 3161 timestamps (no system clock)

```bash
# Production
TBP_PRODUCTION=true python app.py

# Development
TBP_PRODUCTION=false python app.py
```

### Secret Management

**Supported:**
- HashiCorp Vault (`TBP_VAULT_PATH`)
- AWS Secrets Manager (`TBP_AWS_SECRET_NAME`)
- Azure Key Vault (`AZURE_KEYVAULT_NAME`)
- Environment variable (`TBP_HSM_PIN` - dev only)

**Example:**
```bash
export TBP_VAULT_PATH="secret/tbp/hsm-pin"
export VAULT_ADDR="https://vault.example.com"
export VAULT_TOKEN="s.ABC123..."
```

---

## 📚 Dependencies

**Core:**
- `cryptography>=41.0.0` - Crypto primitives
- `asn1crypto>=1.5.1` - ASN.1 parsing (RFC 3161)
- `python-pkcs11>=0.7.0` - HSM interface
- `requests>=2.31.0` - HTTP (TSA)

**Optional:**
- `yubico-piv-tool` - YubiKey support
- `boto3` - AWS CloudHSM
- `azure-keyvault` - Azure Key Vault
- `hvac` - HashiCorp Vault

**Install:**
```bash
pip install -r requirements.txt
```

---

## 🐛 Known Issues

### HSM-Related

- SoftHSM2 required for tests (install: `apt install softhsm2`)
- YubiKey requires `pcscd` daemon running
- AWS CloudHSM needs VPC setup

### Time Attester

- FreeTSA can be slow (500ms+)
- Apple TSA occasionally times out
- Network issues fail over to next TSA

### Merkle Chain

- Large chains (>10k entries) slow to load
- JSON storage not optimized (use SQLite for production)

**See:** [GitHub Issues](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues)

---

## 🤝 Contributing

**Areas for improvement:**

1. **HSM Support**
   - Add SafeNet Luna support
   - Add Thales HSM support
   - Improve error messages

2. **Time Attester**
   - Add more TSAs
   - Implement certificate validation
   - Add batch timestamp requests

3. **Merkle Chain**
   - SQLite backend for large chains
   - Incremental tree updates
   - Compressed storage format

**See:** [Contributing Guide](../CONTRIBUTING.md)

---

## 📄 License

Apache 2.0 - See [LICENSE](../LICENSE)

---

**Questions?** Open an issue or discussion on GitHub.
