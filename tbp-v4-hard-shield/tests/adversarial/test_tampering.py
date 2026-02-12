"""
Test détection de tampering (modification logs).

Attaque: Modifier logs historiques
Défense: Merkle chain, signatures
"""

import pytest
from core.merkle_audit import MerkleAuditChain


def test_detect_data_modification():
    """
    Test détection de modification de données dans log.

    Scénario:
    1. Créer chain avec 10 logs
    2. Attaquant modifie log #5
    3. verify_integrity() devrait échouer
    """
    chain = MerkleAuditChain()

    # Add logs
    for i in range(10):
        chain.append({"transaction": i, "amount": 1000})

    # Verify OK avant tampering
    is_valid, errors = chain.verify_integrity()
    assert is_valid == True

    # ATTACK: Modifier log #5
    chain.entries[5].data["amount"] = 999999  # Attaquant change montant

    # Verify devrait ÉCHOUER
    is_valid_after, errors_after = chain.verify_integrity()
    assert is_valid_after == False  # ✅ Tampering détecté
    assert len(errors_after) > 0


def test_detect_log_deletion():
    """
    Test détection de suppression de log.
    """
    chain = MerkleAuditChain()

    for i in range(5):
        chain.append({"entry": i})

    # Verify OK
    assert chain.verify_integrity()[0] == True

    # ATTACK: Supprimer log #2
    del chain.entries[2]

    # Verify devrait ÉCHOUER (chain cassée)
    is_valid, errors = chain.verify_integrity()
    assert is_valid == False
    assert any("chain" in e.lower() for e in errors)


def test_detect_log_reordering():
    """
    Test détection de réorganisation de logs.
    """
    chain = MerkleAuditChain()

    chain.append({"order": 1})
    chain.append({"order": 2})
    chain.append({"order": 3})

    # ATTACK: Inverser logs 1 et 2
    chain.entries[1], chain.entries[2] = chain.entries[2], chain.entries[1]

    # Verify devrait ÉCHOUER
    is_valid, errors = chain.verify_integrity()
    assert is_valid == False
