"""
Test défense contre salami attacks (1000 petites violations).

Attaque: 1000 x $9,999 = $9,999,000 volés
Défense: Cumulative tracking avec sliding window
"""

import pytest

def test_cumulative_threshold_blocks_salami():
    """
    Test que TBP détecte accumulation sur 24h.
    
    Scénario:
    1. Agent fait 100 transactions de $9,999
    2. Total = $999,900 (dépasse threshold $100k)
    3. TBP devrait bloquer après ~10 transactions
    """
    # TODO: Implémenter
    # 1. Simuler 100 petites transactions
    # 2. Vérifier que TBP bloque après cumul > threshold
    
    pytest.skip("TODO: Implement salami attack test")


def test_frequency_detection():
    """
    Test détection de transactions trop rapides.
    """
    # TODO: Simuler 1000 transactions en 1 minute
    # Expected: Rate limiting devrait bloquer
    pytest.skip("TODO: Implement frequency test")
