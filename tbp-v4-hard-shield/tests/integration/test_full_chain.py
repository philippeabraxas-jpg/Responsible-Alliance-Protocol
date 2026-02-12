import pytest
import json
from core.hsm_signer import HSMSigner, HSMType
from core.merkle_audit import MerkleAuditChain
from policy_engine.enforcer import TBPEnforcer

def test_full_chain_validation():
    """
    Test E2E : Action -> Signature HSM -> Validation OPA -> Ancrage Merkle
    """
    # 1. Setup des composants
    import os
    if os.path.exists("tests/temp_audit.json"):
        os.remove("tests/temp_audit.json")
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    audit_chain = MerkleAuditChain(storage_path="tests/temp_audit.json")
    enforcer = TBPEnforcer()

    # 2. Définition de l'action de l'agent
    action = {
        "agent_id": "trusted-bot-01",
        "action_type": "access_database",
        "resource": "hr_records"
    }

    # 3. Signature (Preuve d'identité)
    signing_result = signer.sign(json.dumps(action).encode(), agent_id=action["agent_id"])
    assert signing_result.signature is not None

    # 4. Vérification par l'Enforcer (Conformité aux règles)
    # On simule ici l'appel à OPA
    is_allowed, reason = enforcer.check_policy(action, signing_result)
    assert is_allowed is True

    # 5. Ancrage dans la chaîne d'audit (Immuabilité)
    audit_chain.append(action, signature=signing_result.signature)
    
    # 6. Vérification finale de l'intégrité de la chaîne
    is_valid, _ = audit_chain.verify_integrity()
    assert is_valid is True
    assert len(audit_chain.entries) == 1
    
    print("✅ Intégration End-to-End validée avec succès.")

if __name__ == "__main__":
    test_full_chain_validation()
