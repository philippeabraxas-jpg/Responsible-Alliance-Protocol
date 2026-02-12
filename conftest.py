import pytest

def pytest_addoption(parser):
    """Ajoute les options de ligne de commande personnalisées."""
    parser.addoption(
        "--run-network-tests",
        action="store_true",
        default=False,
        help="Lancer les tests nécessitant une connexion réseau (TSA)"
    )

def pytest_configure(config):
    """Configure les marqueurs pytest."""
    config.addinivalue_line(
        "markers",
        "network: tests nécessitant une connexion internet"
    )
    config.addinivalue_line(
        "markers",
        "slow: tests lents"
    )

def pytest_collection_modifyitems(config, items):
    """Modifie la collection de tests selon les options."""
    if config.getoption("--run-network-tests"):
        # Si --run-network-tests est passé, on ne saute rien
        return
    
    skip_network = pytest.mark.skip(reason="Besoin de --run-network-tests pour tester le réseau")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_network)
