# Contributing to TBP v4.2 "Shield-Hardening"

Thank you for helping us build a safer future. Version 4.2 is a security-critical project. Every line of code is a potential vulnerability. Please follow these guidelines strictly.

## 1. Security First Principles

- **Never Roll Your Own Crypto:** Always use established libraries like `cryptography` (pyca) or `asn1crypto`.
- **Fail Closed:** If a security check (signature verify, HSM connection) fails, the system must DENY by default.
- **Stateless Logic:** Wherever possible, keep verification logic stateless to avoid side-channel attacks.
- **Deterministic Hashing:** Always use `json.dumps(data, sort_keys=True, separators=(',', ':'))` for hashing to ensure cross-platform consistency.

## 2. Directory Standards

- `core/`: Cryptographic primitives. High-audit zone.
- `policy_engine/`: Rego files and OPA configuration.
- `audit_tools/`: Independent verification scripts.
- `integrations/`: Shims for third-party tools (LangChain, OpenAI, etc.).

## 3. Development Workflow

1.  **Read the Specs:** Study `docs/ARCHITECTURE_V4.2.md` before writing code.
2.  **Environment Setup:**
    - Use Python 3.9+.
    - Install `requirements-test.txt`.
    - Set `TBP_PRODUCTION=false` for local development (enables software HSM fallback).
3.  **Run Tests:**
    - `pytest tests/unit/` (Unit tests)
    - `opa test policy_engine/` (Policy tests)
4.  **Security Review:**
    - All PRs affecting `core/` or `policy_engine/` require a mandatory security review.

## 4. Coding Style for Security

- **Type Hinting:** Mandatory for all new functions.
- **Logging:** Never log private keys, PINs, or sensitive payload data. Use `logger.info()` for process events and `logger.error()` for security failures.
- **Error Handling:** Use specific exceptions (e.g., `HSMSignerError`) rather than generic `Exception`.

## 5. Branching Policy

- Feature branches: `feat/your-feature`
- Bug fixes: `fix/the-bug`
- **Critical Security Patches:** `hotfix/security-issue`

---
*The Responsible Alliance Protocol is a collective effort. Your contributions help ensure that AI remains a tool for stability and prosperity.*
