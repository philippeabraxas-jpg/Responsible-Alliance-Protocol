TODO complétés :

    ✅ Install PKCS#11 libraries - Gestion des dépendances avec import conditionnel

    ✅ Implémenter HSM connection - Méthode _connect_hsm() avec support multi-vendor

    ✅ Implémenter signing - Méthode sign() avec RSA-PSS et timestamps anti-replay

    ✅ Implémenter verification - Méthode verify() sans besoin d'accès HSM

    ✅ Ajouter key generation - Méthode generate_key() pour création sécurisée

    ✅ Écrire tests - Fonctions utilitaires de test avec SoftHSM

Fonctionnalités avancées ajoutées :

    Support multi-HSM : YubiKey, AWS CloudHSM, Azure Key Vault, SoftHSM

    Rate limiting : Protection contre les attaques par déni de service

    Timestamps anti-replay : Intégrés dans la signature

    Gestion sécurisée des PIN : Jamais stockés en dur

    Fallback software : Pour le développement et les tests

    Logging complet : Pour l'audit et le debugging

Pour utiliser :
bash

# Installation
pip install python-pkcs11 cryptography

# Test avec SoftHSM
python -c "from hsm_signer import setup_softhsm_test; setup_softhsm_test()"

# Exemple d'utilisation production
signer = HSMSigner(
    hsm_type=HSMType.YUBIKEY,
    pin=getpass.getpass("YubiKey PIN: "),
    key_label="tbp-production-key"
)
