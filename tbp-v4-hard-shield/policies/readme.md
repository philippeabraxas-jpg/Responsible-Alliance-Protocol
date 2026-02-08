🛡️ TBP Rego Policies: Implementation & Governance
Overview

This directory contains the executable logic for the Teleological Bounding Protocol (TBP). These policies represent the "Hard-Shield"—a set of computational guardrails designed to maintain the three fundamental invariants: F-Stability, I-Integrity, and W-Monopoly.
⚠️ Important: Threshold Sovereignty & Discussion

The numerical values currently defined in the .rego files (e.g., the $10,000 transaction limit, 5% market impact scores, or action frequency caps) are Reference Blueprints.

These thresholds are not arbitrary, but they are not absolute.

We acknowledge that a "one size fits all" approach could lead to an "AI Straitjacket" that hampers legitimate economic activity. Therefore:

    Individual/Institutional Calibration: Thresholds must be discussed and calibrated by the competent authorities within each deploying organization.

    Economic Context: A market-making AI and a personal retail assistant require different operational envelopes.

    Institutional Acceptance: The protocol's success depends on the collective agreement of stakeholders (Regulators, Central Banks, and Ethics Committees) to define what constitutes a "safe state."

🚀 Roadmap: Towards v5 Governance

The TBP is designed to evolve from static enforcement to a Dynamic Governance Layer.
1. The "Safety Valve" (Multi-Sig Bypass)

Planned for Version 5.0, we will introduce a Multi-Signature Bypass mechanism. This allows for the temporary, controlled lifting of specific constraints in emergency scenarios or system defaults.

    Costly & Accountable: Bypassing a shield is a "heavy" operation requiring significant cryptographic proof of necessity.

    Temporal & Exceptional: Bypasses are time-limited (TTL) and revert automatically to the Hard-Shield.

    Consensus-Driven: Requires a 3-of-5 or 5-of-7 committee agreement to prevent unilateral abuse of power.

2. Power-Preserving Adoption

The goal of TBP is Collective Resilience, not the deprivation of power. By adopting the protocol, institutions do not lose their ability to act; they gain a "Mathematical Insurance" that their autonomous systems will not cross catastrophic thresholds.

As governance matures, rules will be refined through Alliance Consensus, ensuring the protocol remains a tool for stability rather than a barrier to innovation.
🛠️ Developer Instructions

To test or adjust thresholds for your specific use case:

    Modify the variables in tbp_core.rego.

    Run the unit test suite: opa test . -v.

    Document any threshold changes in your local audit log to maintain compliance with the Responsible Alliance Protocol (RAP).
