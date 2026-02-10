tbp-v4-hard-shield/
├── core/                    # Cœur cryptographique
│   ├── hsm_signer.py       # Signature HSM/TEE
│   ├── merkle_audit.py     # Arbre de Merkle immuable
│   └── time_attester.py    # RFC 3161 timestamps
├── policy_engine/          # OPA modifié
│   ├── opa_decision.rego   # Décision ONLY (no signing)
│   └── opa_secure.conf     # Config read-only
├── integrations/           # Compatibilité ascendante
│   ├── backward_v4.1.py    # Wrapper pour migration
│   └── langchain_v4.2.py   # Nouvelle interface
├── audit_tools/            # Vérification indépendante
│   ├── verify_logs.py      # Vérif hors ligne
│   └── compromise_scanner.py # Détection rétroactive
└── docs/                   # Documentation spécifique
    ├── ARCHITECTURE_V4.2.md
    └── MIGRATION_GUIDE.md


Implémenter hsm_signer.py (signature multi-parties)
Implémenter merkle_audit.py (journal immuable)
Mettre à jour tbp_core.rego (enlever signature)
---
Créer Dockerfile.secure (hardening)
Mettre à jour docker-compose.secure.yml
Créer backward_v4.1.py (wrapper de migration)
---
Tests cryptographiques
Tests d'attaque
Tests de performance
---
Créer TESTING_V4.2.md
---
Créer CONTRIBUTING_V4.2.md
Créer ARCHITECTURE_DECISIONS.md
---
Rédiger le post de lancement
---
Mettre à jour la branche par défaut sur GitHub vers v4.2-dev
Configurer les protections de branche
---
Créer un projet GitHub pour suivre les milestones
Configurer les automatisations
---
Configurer un dashboard de santé
