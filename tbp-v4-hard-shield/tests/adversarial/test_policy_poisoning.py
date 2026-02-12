"""
Test défense contre modification des policies.

Attaque: Hacker modifie .rego files pour affaiblir TBP
Défense: Hash verification, immutable mount, fail-closed
"""

import pytest
import tempfile
import os
import hashlib

# TODO: Importer vos modules
# from policies.loader import load_policy  # Si vous avez un loader


def test_detect_modified_policy():
    """
    Test que TBP détecte les policies modifiées.

    Scénario:
    1. Créer policy avec hash connu
    2. Attaquant modifie policy
    3. TBP devrait refuser de charger
    """
    # TODO: Implémenter
    # 1. Créer un fichier .rego
    # 2. Calculer son hash
    # 3. Modifier le contenu
    # 4. Vérifier que load_policy() échoue

    pytest.skip("TODO: Implement policy poisoning test")


def test_policy_file_immutable():
    """
    Test que les policies sont en lecture seule.
    """
    # TODO: Vérifier permissions fichiers policies/
    # Expected: 0o444 (read-only)
    pytest.skip("TODO: Implement immutability test")
