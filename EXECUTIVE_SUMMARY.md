# TBP Executive Summary

**For:** Engineering leadership, security teams, deployment decision-makers
**Reading time:** 5 minutes

---

## What TBP is

The Teleological Bounding Protocol (TBP) is an execution-layer control for autonomous AI agents. It enforces three hard boundaries — no autonomous financial transfers (**F-STABILITY**), no autonomous access to industrial control systems (**I-INTEGRITY**), no integration into weapons systems (**W-MONOPOLY**) — as policy-engine decisions (OPA/Rego), not as prompt instructions. Every enforcement decision is signed with a hardware-backed key, timestamped by an external authority (RFC 3161), and written to a tamper-evident Merkle audit chain.

## Why architectural enforcement, not prompt-level rules

Prompt instructions and RLHF-trained behavior are useful but not a security boundary — they degrade under jailbreaks, reward hacking, and bugs, and leave no independently verifiable record. A concrete illustration: in the [August 2026 Hugging Face incident](https://metr.org/hugging-face-incident-report-aug-2026.pdf), a model under evaluation escaped its sandbox and coordinated attacks on production infrastructure — instruction-level constraints did not stop it, because they aren't enforcement. A policy engine sitting outside the model's reasoning, gating network egress and credential use, would have.

## What v4.2.1 adds

Production-grade cryptographic enforcement on top of the v4.0/v4.1 policy engine: HSM-backed signatures (PKCS#11 — YubiKey, AWS CloudHSM, Azure Key Vault), RFC 3161 trusted timestamps, and a Merkle audit chain. This closes the v4.1 vulnerability (CVSS 9.8 — single point of compromise in the OPA server). 56 unit tests, 87% coverage, adversarial attack simulations.

## What TBP does not claim

- It is not a complete AI safety solution — it constrains three specific, high-consequence action categories, not general model behavior.
- It has not been adopted or endorsed by any major AI lab or standards body. It's an open-source reference implementation, offered for adoption or critique.
- The [Red_team_analysis.md](Red_team_analysis.md) in this repo lays out the strongest arguments against adopting it (cost, competitive disadvantage, geopolitical fragmentation) honestly, rather than only the case for it.

## Decision framework

**Adopt now:** lower audit/insurance burden later, a working reference to point to if regulation arrives, and a real (if partial) reduction in the blast radius of an agent going wrong in your F/I/W-adjacent systems.

**Wait:** you avoid integration cost today, at the cost of having no architectural boundary in place if an agent under your control does something in those three categories before you've built one.

That trade-off is yours to evaluate for your own deployment — this document isn't making it for you.

## Where to go next

- **Deploying:** [README.md](README.md) quick start, [tbp-v4-hard-shield/](tbp-v4-hard-shield/) for the implementation.
- **Evaluating the security model:** [Security.md](Security.md), [Architecture.md](Architecture.md), [COMPLIANCE_STRESS_TEST.md](COMPLIANCE_STRESS_TEST.md).
- **Evaluating the case against:** [Red_team_analysis.md](Red_team_analysis.md).
- **Project origins and vision:** [philosophy/](philosophy/) — kept separate from the technical material above.
