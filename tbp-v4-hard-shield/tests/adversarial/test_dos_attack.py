"""
Test défense contre DoS (Denial of Service).

Attaque: Flood TBP avec 1M requêtes/sec
Défense: Rate limiting, priority queues
"""

import pytest
import concurrent.futures

def test_rate_limiting_blocks_flood():
    """
    Test que rate limiting bloque flood.
    
    Scénario:
    1. Envoyer 10,000 requêtes très rapidement
    2. TBP devrait rate-limit
    3. Vérifier que certaines sont bloquées (HTTP 429)
    """
    # TODO: Implémenter
    # 1. Flood endpoint avec requests
    # 2. Compter combien sont bloquées
    # Expected: Au moins 50% bloquées
    
    pytest.skip("TODO: Implement DoS test")


def test_priority_queue_protects_critical():
    """
    Test que opérations critiques passent pendant DoS.
    """
    # TODO: Flood avec low-priority, vérifier critical passe
    pytest.skip("TODO: Implement priority test")
