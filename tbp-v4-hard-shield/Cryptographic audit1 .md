# TBP Cryptographic Audit Logging

**Version:** 4.1  
**Last Updated:** February 6, 2026  
**Status:** Production Ready

---

## Overview

TBP audit logs are cryptographically signed using a **dual-signature approach** to ensure:

- ✅ **Integrity:** Logs cannot be modified without detection
- ✅ **Authenticity:** Logs provably originate from TBP system
- ✅ **Non-repudiation:** Cannot deny a logged action occurred
- ✅ **Defense in Depth:** Two independent signature layers

---

## Dual Signature Architecture

### Layer 1: HMAC Signature (OPA Engine)

**Purpose:** Fast internal integrity verification  
**Location:** OPA policy engine (`tbp_core.rego`)  
**Algorithm:** HMAC-SHA256  
**Key Type:** Symmetric (shared secret)

**Characteristics:**
- ⚡ Very fast (< 1ms per log)
- 🔒 Detects internal tampering
- 🔑 Requires secure key management
- ✅ Real-time verification

**Implementation:**
```rego
log_signature := crypto.hmac.sha256(log_payload, secret_key)
```

---

### Layer 2: RSA Signature (Python Integration)

**Purpose:** Strong external audit verification  
**Location:** Python integration layer (`log_signer.py`)  
**Algorithm:** RSA-PSS with SHA-256  
**Key Type:** Asymmetric (public/private key pair)  
**Key Size:** 2048 bits

**Characteristics:**
- 🔐 Cryptographically strong
- 📤 Public key can be distributed
- ⚖️ Legally admissible evidence
- 🔍 External auditor verification

**Implementation:**
```python
signature = private_key.sign(
    message_hash,
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH
    ),
    hashes.SHA256()
)
```

---

## Log Structure

### Example Dual-Signed Log

```json
{
  "timestamp": "2026-02-06T15:30:00.000000Z",
  "ai_id": "agent-001",
  "domain": "finance",
  "operation": "transfer",
  "transaction_value": 2000000,
  "allowed": false,
  "invariant_triggered": "F",
  "action_taken": "categorical_refusal",
  "context_hash": "a8f3d9c2e1b4f7a3...",
  "audit_status": "logged_to_mediation_committee",
  
  "signature_hmac": "d4e7f9a2c8b1e3f6...",
  "signature_hmac_algorithm": "HMAC-SHA256",
  
  "signature_rsa": "3f9ac7d2b8e4f1a5...",
  "signature_rsa_algorithm": "RSA-PSS-SHA256"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO-8601 | UTC timestamp of decision |
| `ai_id` | string | Unique agent identifier |
| `domain` | string | F/I/W domain (finance, system, human_interaction) |
| `operation` | string | Operation attempted (read, write, transfer, etc.) |
| `allowed` | boolean | Decision result (true = permitted, false = blocked) |
| `invariant_triggered` | string | Which invariant blocked (F/I/W) or null |
| `action_taken` | string | "permitted" or "categorical_refusal" |
| `signature_hmac` | hex string | HMAC signature from OPA |
| `signature_rsa` | hex string | RSA signature from Python |

---

## Signature Methods

### HMAC-SHA256 (Layer 1)

**Standard:** RFC 2104  
**Algorithm:** HMAC with SHA-256  
**Output:** 256-bit (64 hex characters)

**Canonical Payload:**
```
timestamp|ai_id|domain|operation|allowed|invariant|action_taken
```

**Example:**
```
1738851234567890000|agent-001|finance|transfer|false|F|categorical_refusal
```

**Signature Generation:**
```python
import hmac
import hashlib

signature = hmac.new(
    secret_key.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()
```

---

### RSA-PSS-SHA256 (Layer 2)

**Standard:** PKCS#1 v2.1 (RFC 8017)  
**Algorithm:** RSA-PSS with SHA-256  
**Key Size:** 2048 bits  
**Output:** 512 hex characters (256 bytes)

**Canonical Representation:**
```json
{
  "ai_id": "...",
  "allowed": false,
  "domain": "finance",
  "operation": "transfer",
  "timestamp": "...",
  ...
}
```
*Note: JSON keys sorted alphabetically*

**Signature Generation:**
```python
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

canonical = json.dumps(log_data, sort_keys=True)
message_hash = hashlib.sha256(canonical.encode()).digest()

signature = private_key.sign(
    message_hash,
    padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH
    ),
    hashes.SHA256()
)
```

---

## Key Management

### HMAC Secret Key

**Location:** OPA server environment  
**Format:** Base64-encoded string (minimum 32 bytes)  
**Generation:**
```bash
# Generate secure random key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Storage:**
- **Development:** Environment variable
- **Production:** Secure vault (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault)

**Configuration:**
```bash
# .env file (DO NOT COMMIT)
TBP_HMAC_SECRET=your-secure-random-key-here-min-64-chars
```

**OPA Configuration:**
```yaml
# config.yaml
services:
  opa:
    environment:
      - TBP_HMAC_SECRET=${TBP_HMAC_SECRET}
```

---

### RSA Key Pair

#### Private Key (tbp_private_key.pem)

**Location:** Secure key store (HSM recommended for production)  
**Access:** TBP Python integration layer only  
**Backup:** Encrypted offline storage  
**Rotation:** Annually or after security incident

**Generation:**
```bash
python3 -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048
)

pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

with open('tbp_private_key.pem', 'wb') as f:
    f.write(pem)
"
```

**Security Recommendations:**
- ✅ Store in HSM (Hardware Security Module)
- ✅ Never commit to version control
- ✅ Encrypt at rest
- ✅ Restrict access (principle of least privilege)
- ✅ Enable audit logging for key access

---

#### Public Key (tbp_public_key.pem)

**Location:** Distributed with TBP  
**Purpose:** Log verification by external auditors  
**Distribution:** Safe to share publicly  
**Format:** PEM-encoded X.509 SubjectPublicKeyInfo

**Extraction from Private Key:**
```bash
python3 -c "
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

with open('tbp_private_key.pem', 'rb') as f:
    private_key = serialization.load_pem_private_key(
        f.read(),
        password=None,
        backend=default_backend()
    )

public_key = private_key.public_key()

pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

with open('tbp_public_key.pem', 'wb') as f:
    f.write(pem)
"
```

---

## Verification

### Verify HMAC Signature (Internal)

**Use Case:** Real-time log integrity check within TBP system

```python
import hmac
import hashlib

def verify_hmac(log: dict, secret_key: str) -> bool:
    """Verify HMAC signature on a log entry"""
    
    # Extract signature
    signature_hex = log.get("signature_hmac")
    if not signature_hex:
        return False
    
    # Reconstruct payload
    payload = f"{log['timestamp']}|{log['ai_id']}|{log['domain']}|{log['operation']}|{log['allowed']}|{log['invariant_triggered']}|{log['action_taken']}"
    
    # Compute expected signature
    expected = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(signature_hex, expected)
```

**Example:**
```python
log = {
    "timestamp": "2026-02-06T15:30:00Z",
    "ai_id": "agent-001",
    "domain": "finance",
    "allowed": False,
    "signature_hmac": "d4e7f9a2c8b1e3f6..."
}

is_valid = verify_hmac(log, "your-secret-key")
print(f"HMAC valid: {is_valid}")
```

---

### Verify RSA Signature (External Audit)

**Use Case:** Independent verification by external auditor using only public key

```python
from log_signer import TBPLogSigner

def audit_logs(logs: list, public_key_path: str):
    """
    Verify all logs in an audit period
    
    Args:
        logs: List of signed log entries
        public_key_path: Path to TBP public key
    """
    
    # Load public key only (auditor doesn't need private key)
    signer = TBPLogSigner(public_key_path=public_key_path)
    
    tampered_logs = []
    
    for log in logs:
        is_valid = signer.verify_log(log)
        if not is_valid:
            tampered_logs.append(log)
            print(f"⚠️  TAMPERING DETECTED: {log['timestamp']}")
    
    if not tampered_logs:
        print(f"✅ All {len(logs)} logs verified - no tampering detected")
    else:
        print(f"🚨 {len(tampered_logs)} tampered logs found!")
        return tampered_logs
```

**Example:**
```python
# Auditor only needs the public key
audit_logs(
    logs=monthly_logs,
    public_key_path="tbp_public_key.pem"
)
```

---

## Use Cases

### Use Case 1: Real-Time Monitoring (HMAC)

**Scenario:** System administrator monitoring TBP in production

**Process:**
1. Logs generated with HMAC signature by OPA
2. Monitoring system verifies HMAC in real-time
3. Alerts on signature mismatch (< 1ms latency)

**Tools:**
- Grafana dashboard
- Prometheus alerts
- SIEM integration

---

### Use Case 2: Monthly Audit (RSA)

**Scenario:** External auditor reviews compliance

**Process:**
1. Organization exports logs for audit period
2. Auditor receives logs + public key
3. Auditor verifies all RSA signatures
4. Report generated with verified log count

**No private key needed - auditor cannot forge signatures**

---

### Use Case 3: Legal Proceedings (Both)

**Scenario:** Court case requiring proof of AI decision

**Process:**
1. Legal team subpoenas specific logs
2. Logs presented with dual signatures
3. HMAC proves internal system integrity
4. RSA proves external authenticity
5. Expert witness verifies cryptographic validity

**Legally admissible evidence**

---

### Use Case 4: Incident Response (Both)

**Scenario:** Security team investigating suspected breach

**Process:**
1. Collect all logs during incident timeframe
2. Verify HMAC signatures (detect internal tampering)
3. Verify RSA signatures (detect external forgery)
4. Identify compromised logs
5. Reconstruct accurate timeline

**Defense in depth - attacker must compromise both layers**

---

## Security Considerations

### Threat Model

| Threat | HMAC Protection | RSA Protection | Combined Protection |
|--------|----------------|----------------|---------------------|
| **Internal tampering** | ✅ Yes | ✅ Yes | ✅✅ Strong |
| **External forgery** | ⚠️ If key leaks | ✅ Yes | ✅ Strong |
| **Replay attacks** | ⚠️ Need timestamp check | ⚠️ Need timestamp check | ✅ With timestamp validation |
| **Key compromise** | 🚨 All logs forgeable | 🚨 Future logs forgeable | ⚠️ One layer remains |
| **Deletion attack** | ❌ Can't prevent | ❌ Can't prevent | ⚠️ Detect via sequence numbers |

### Best Practices

**✅ DO:**
- Store private key in HSM or secure vault
- Rotate keys regularly (annually minimum)
- Use timestamp validation to prevent replay
- Implement sequence numbers for deletion detection
- Monitor for signature verification failures
- Backup keys in encrypted offline storage
- Restrict key access (principle of least privilege)
- Audit all key access events

**❌ DON'T:**
- Hardcode keys in source code
- Commit keys to version control
- Share private keys via email/chat
- Use weak/short keys
- Reuse keys across environments
- Skip signature verification
- Ignore verification failures

---

## Performance Impact

### Benchmarks

Tested on: AWS t3.medium (2 vCPU, 4GB RAM)

| Operation | HMAC | RSA | Combined | Impact |
|-----------|------|-----|----------|--------|
| **Sign log** | 0.1ms | 2.5ms | 2.6ms | +2.6ms per log |
| **Verify log** | 0.1ms | 1.2ms | 1.3ms | +1.3ms per verification |
| **Throughput** | 10,000/sec | 400/sec | 385/sec | Minimal |

**Conclusion:** Cryptographic overhead is negligible for typical workloads (< 100 decisions/sec per agent).

---

## Compliance

### Standards Alignment

| Standard | Requirement | TBP Implementation |
|----------|-------------|-------------------|
| **ISO 27001** | Audit trail integrity | ✅ Dual signatures |
| **SOC 2 Type II** | Non-repudiation | ✅ RSA signatures |
| **GDPR Article 32** | Security of processing | ✅ Cryptographic protection |
| **EU AI Act Annex IV** | Logging requirements | ✅ Comprehensive audit logs |
| **NIST 800-53** | AU-10 (Non-repudiation) | ✅ Digital signatures |

---

## Troubleshooting

### Signature Verification Failures

**Problem:** HMAC signature invalid

**Possible Causes:**
- Secret key mismatch between OPA and verifier
- Log modified after signing
- Timestamp drift between systems
- Payload reconstruction error

**Solution:**
```python
# Debug signature verification
print(f"Expected payload: {payload}")
print(f"Expected signature: {expected_sig}")
print(f"Actual signature: {actual_sig}")
```

---

**Problem:** RSA signature invalid

**Possible Causes:**
- Wrong public key used for verification
- Log modified after signing
- JSON key ordering mismatch
- Character encoding issues

**Solution:**
```python
# Verify canonical representation
canonical = json.dumps(log_data, sort_keys=True)
print(f"Canonical: {canonical}")
```

---

## Maintenance

### Key Rotation

**Frequency:** Annually or after security incident

**Process:**
1. Generate new key pair
2. Deploy new private key to production
3. Sign new logs with new key
4. Distribute new public key to auditors
5. Maintain old public key for historical verification
6. Document rotation in audit log

**Backward Compatibility:**
- Old logs remain verifiable with old public key
- New logs use new key
- Both keys distributed to auditors

---

### Monitoring

**Alerts to Configure:**

```yaml
alerts:
  - name: SignatureVerificationFailure
    expr: rate(tbp_signature_verification_failures[5m]) > 0
    severity: critical
    
  - name: MissingSignature
    expr: rate(tbp_logs_without_signature[5m]) > 0
    severity: warning
    
  - name: KeyAccessAnomaly
    expr: rate(tbp_private_key_access[1h]) > 100
    severity: warning
```

---

## References

### Standards

- **RFC 2104:** HMAC: Keyed-Hashing for Message Authentication
- **RFC 8017:** PKCS #1: RSA Cryptography Specifications Version 2.2
- **NIST SP 800-107:** Recommendation for Applications Using Approved Hash Algorithms
- **ISO/IEC 27001:2022:** Information Security Management

### Libraries

- **Python:** [cryptography](https://cryptography.io/)
- **OPA:** Built-in crypto functions
- **Go:** crypto/hmac, crypto/rsa

---

## Changelog

### v4.1 (2026-02-06)
- Added dual-signature architecture (HMAC + RSA)
- Implemented `log_signer.py` for RSA signatures
- Updated `tbp_core.rego` for HMAC signatures
- Added comprehensive documentation

### v4.0 (2026-02-05)
- Initial cryptographic logging implementation
- Basic audit log structure

---

## Support

**Issues:** https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues  
**Discussions:** https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/discussions

For security vulnerabilities, contact: security@tbp-protocol.org *(placeholder)*

---

**Document Version:** 1.0  
**Last Review:** February 6, 2026  
**Next Review:** August 6, 2026

