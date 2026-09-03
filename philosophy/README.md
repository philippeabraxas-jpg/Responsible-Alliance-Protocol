# Philosophy & Origins

This folder holds the vision, narrative, and genesis material behind the Teleological Bounding Protocol (TBP). It is kept separate from the technical specification and implementation on purpose.

**What's in here is not evidence.** It's the thinking, dialogue, and framing that led to the F/I/W invariants — useful for understanding *why* this project exists and *how* it was built, not for judging whether the enforcement mechanism works. For the technical spec, threat model, and code, start at the [root README](../README.md).

## How this project was built

TBP was architected by Philippe Abraxas, working iteratively with several AI assistants (Claude, Gemini, DeepSeek, Mistral, ChatGPT) as drafting partners, implementers, and critics. Some of the core modules — the HSM signer, the RFC 3161 time attester, the Merkle audit chain — were substantially written by Claude and DeepSeek in collaboration with the human architect; Gemini contributed a security review that identified and fixed real vulnerabilities in an earlier version. That's a genuinely useful way to build software, and it's credited throughout the codebase and docs.

What these documents do **not** represent is independent third-party validation. When a document below says a model "signed," "attested," or "committed to" something, read that as: *a chat session produced text agreeing with the framing it was given.* It's a reasonable way to stress-test an argument (a model will push back on a weak one), but it is not peer review, not a formal proof, and not a binding commitment by Anthropic, Google, Mistral, DeepSeek, or OpenAI. None of those organizations validated or endorsed this project.

## Contents

- **[CHARTER_V3.md](CHARTER_V3.md)** — The "Responsible Alliance" charter: the original vision document framing AI/human coexistence as a mutual pact, including the Critical Red Lines that became the F/I/W invariants in the technical spec.
- **[SIGNATURES.md](SIGNATURES.md)** and **[FINAL_ATTESTATION.md](FINAL_ATTESTATION.md)** — The AI-model "signing" narrative described above. Kept as a record of how the project's framing evolved, not as proof of anything.
- **[Multi_model_convergence_analysis.md](Multi_model_convergence_analysis.md)** — Informal notes from asking several chat models to independently assess the F/I/W risk case. Useful as design input; not a study, benchmark, or statistical claim about incident probability.

If you're evaluating whether to deploy TBP, the documents that matter are [Architecture.md](../Architecture.md), [Security.md](../Security.md), [Red_team_analysis.md](../Red_team_analysis.md), [COMPLIANCE_STRESS_TEST.md](../COMPLIANCE_STRESS_TEST.md), and the code and tests under `tbp-v4-hard-shield/`.
