# TBP v4.2 Architecture: "The Hard-Shield"

## 1. Vision & Background
Version 4.0 and 4.1 of the Teleological Bounding Protocol focused on **Safety** (preventing unintentional harm from misaligned AI). 
**Version 4.2 focuses on Security** (preventing intentional harm from malicious actors).

The "Hard-Shield" introduces a separate, hardened security boundary that protects the protocol itself from tampering, even if the primary AI system or its host server is fully compromised.

## 2. Key Security Pillars

### A. Hardware-Backed Policy Integrity (HSM)
In previous versions, cryptographic keys were stored in software. In v4.2, keys never leave a **Hardware Security Module (HSM)** or a **Trusted Execution Environment (TEE)**.
- **Benefit:** Even a root user on the server cannot steal the private signing keys.
- **Implementation:** `core/hsm_signer.py` provides the abstraction for PKCS#11, AWS CloudHSM, and Azure Key Vault.

### B. Immutable Audit Chain (Merkle Tree)
Audit logs are no longer just flat files. They are structured into a **Merkle Tree Audit Chain**.
- **Backward Linking:** Each log entry contains the hash of the previous one (Blockchain-style).
- **Merkle Root:** Every set of logs generates a unique root hash.
- **Independent Verification:** Auditors can verify a single log entry using a "Merkle Proof" without needing access to the entire database.
- **Tamper Detection:** Modifying a single byte in a log from three years ago will break the current Merkle root.

### C. Digital Time Attestation (TSA)
To prevent "backdating" attacks (where an attacker modifies logs and adjusts timestamps to match), v4.2 supports **RFC 3161 Time Stamping Authorities**.
- **External Proof:** Logs are signed by a trusted third-party clock.
- **Proof of Existence:** Proves that a specific decision was made at a specific point in time.

## 3. The "Dual-Service" Architecture

TBP v4.2 splits the responsibility into two distinct services:

1.  **The Policy Engine (OPA):**
    - Responsibility: Decision Logic.
    - Input: Action Request (JSON).
    - Output: ALLOW/BLOCK decision + Context.
    - Security: High-performance, read-only policy files.

2.  **The Shield Service (TBP-Core):**
    - Responsibility: Cryptographic Hardening.
    - Input: Decision from OPA.
    - Logic: Canonicalizes data → Signs with HSM → Appends to Merkle Chain → Attests with TSA.
    - Security: Minimal API surface, runs as a separate authenticated service.

## 4. Threat Model & Mitigations

| Threat | Version 4.1 Defense | Version 4.2 Mitigation |
| :--- | :--- | :--- |
| **Server Root Compromise** | Total Loss (Keys stolen) | **HSM Security Boundary** (Keys safe) |
| **Log Tampering** | Hard to detect | **Merkle Hash Chain** (Instant Detection) |
| **Timestamp Manipulation**| Software Clock | **RFC 3161 TSA** (Third-party Proof) |
| **Policy Poisoning** | Static analysis | **Cryptographic Policy Signing** |
| **Salami Attacks** | Manual Review | **Sliding Window Cumulative Analysis** |

## 5. Deployment Recommendation
For maximum security, OPA and the Shield Service should run in separate containers with an isolated internal network (`tbp-internal`), as demonstrated in `deployment/docker-compose.secure.yml`.
