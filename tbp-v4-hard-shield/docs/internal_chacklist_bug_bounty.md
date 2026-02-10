🛡️ Checklist Bug Bounty : TBP v4.2

Objectif : Identifier les failles avant les attaquants.
1. Attaques sur l'Intégrité (La Chaîne Merkle)

L'attaquant veut modifier le passé sans que personne ne s'en aperçoive.

    Le Test du "Pixel Mort" : Modifiez un seul caractère dans un log vieux de 3 jours (ex: changer une virgule en point).

        Résultat attendu : Le AuditVerifier doit lever une alerte d'intégrité immédiate.

    L'Attaque de Suppression : Supprimez complètement une ligne de log au milieu du fichier.

        Résultat attendu : La preuve Merkle doit échouer car le "Previous Hash" de la ligne suivante ne correspondra plus à rien.

    L'Attaque de Réorganisation : Inversez deux lignes de logs valides.

        Résultat attendu : Échec de la vérification. L'ordre chronologique est scellé cryptographiquement.

2. Attaques sur la Signature (Le HSM)

L'attaquant veut signer de fausses décisions.

    Le Vol de Clé : Tentez de copier le fichier de clé privée depuis le conteneur.

        Résultat attendu : Impossible, la clé est dans le HSM (ou l'enclave logicielle isolée), pas dans un fichier accessible.

    Le Bypass de Signature : Modifiez le code pour qu'il accepte un log sans signature.

        Résultat attendu : Le AuditVerifier doit rejeter le log comme "Non Authentifié".

    L'Attaque par Déni de Service (DoS) sur le HSM : Envoyez 5000 requêtes de signature par seconde.

        Résultat attendu : Le RateLimiter doit bloquer l'agent avant que le HSM ne sature.

3. Attaques sur la Logique (Les Règles OPA)

L'attaquant veut contourner les seuils.

    L'Attaque Salami (Death by 1000 cuts) : Faites 100 transactions de 99€ si le seuil d'alerte est à 100€.

        Résultat attendu : Le PatternAnalyzer doit détecter l'accumulation et bloquer à la n-ième transaction.

    L'Empoisonnement de Politique : Tentez d'écraser le fichier tbp_core.rego avec une version qui dit allow = true.

        Résultat attendu : Le système doit refuser de démarrer ou se verrouiller car le Hash du fichier ne correspond plus à l'officiel (ADR-007).

4. Attaques Réseau (Kubernetes)

L'attaquant veut parler à des services interdits.

    Le Scan de Port Interne : Depuis un Pod "Standard", tentez d'appeler l'API d'administration d'OPA.

        Résultat attendu : Connection Timeout (bloqué par la NetworkPolicy deny-all).

    L'Exfiltration de Données : Tentez de faire un curl google.com depuis le Pod OPA.

        Résultat attendu : Échec (bloqué par l'Egress restreint, sauf vers le DNS et le TSA).

Comment utiliser ce document avec l'équipe ?

    Donnez cette checklist aux développeurs et dites-leur : "Si vous arrivez à faire passer un de ces tests, on a un bug."

    Utilisez le AuditVerifier pour prouver que vous avez détecté l'attaque.
