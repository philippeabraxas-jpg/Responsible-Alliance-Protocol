"""
TBP v4.2 - Backward Compatibility Wrapper

PURPOSE:
    Allow v4.1 deployments to migrate to v4.2 without breaking changes.
    Provides drop-in replacement for old integrations.

MIGRATION STRATEGY:
    Phase 1: Install v4.2 alongside v4.1 (both work)
    Phase 2: Test v4.2 in staging
    Phase 3: Gradually migrate production traffic
    Phase 4: Deprecate v4.1

WHY THIS MATTERS:
    - Organizations have production systems using v4.1
    - Cannot force immediate migration (too risky)
    - Need smooth transition path

COMPATIBILITY GUARANTEES:
    ✅ All v4.1 API calls work with v4.2
    ✅ v4.1 log format still supported (auto-upgraded internally)
    ✅ Existing RSA keys still work (supplemented with HSM)
    ✅ No breaking changes to integrations

TODO (Caetano):
    1. Wrap v4.2 classes with v4.1 interface
    2. Auto-detect v4.1 vs v4.2 mode
    3. Provide migration utilities
    4. Add deprecation warnings (but don't break)
    5. Write migration tests

TESTING:
    - Run all v4.1 tests with v4.2 backend
    - Verify no regressions
    - Test mixed deployments (some v4.1, some v4.2)
"""

import warnings
import logging
from typing import Dict, Any, Optional

# --- 1. CONFIGURATION ---
logger = logging.getLogger(__name__)

try:
    # On essaie de trouver l'ancien code v4.1 pour rester compatible
    from tbp_v4_hard_shield.integrations.log_signer import TBPLogSigner as TBPLogSigner_v41
except ImportError:
    TBPLogSigner_v41 = None

from core.hsm_signer import HSMSigner, HSMType
from core.merkle_audit import MerkleAuditChain

# --- 2. LE WRAPPER (Le Pont) ---
# --- 2. LE WRAPPER (Le Pont) ---
class TBPLogSigner:
    """Cette classe permet d'utiliser la v4.2 avec les commandes de la v4.1."""
    def __init__(self, use_hsm: bool = True, storage_path: Optional[str] = None):
        self.mode = "v4.1-compat"
        self.signer = None
        
        # On initialise la chaine avec le chemin de stockage si fourni
        self.chain = MerkleAuditChain(storage_path=storage_path)
        
        try:
            # On tente de passer en v4.2 (HSM)
            # Pour la compatibilité, on utilise SOFTWARE par défaut si pas de HSM physique
            hsm_type = HSMType.SOFTWARE if os.getenv("TBP_PRODUCTION", "false").lower() != "true" else HSMType.PKCS11_GENERIC
            self.signer = HSMSigner(hsm_type=hsm_type) 
            self.mode = "v4.2-hsm"
            logger.info(f"✅ Mode v4.2 (HSM: {hsm_type.value}) activé via wrapper v4.1.")
        except Exception as e:
            # Sinon, on reste en v4.1 si l'ancien code est présent
            if TBPLogSigner_v41:
                self.signer = TBPLogSigner_v41()
                warnings.warn(f"⚠️ Fallback sur v4.1 (Moins sécurisé) : {e}", DeprecationWarning)
            else:
                logger.error(f"Erreur d'initialisation HSM : {e}")
                raise RuntimeError("Erreur : Aucun moteur de signature v4.2 trouvé et v4.1 absent !")

    def sign_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Signe un log (Interface v4.1, mais moteur v4.2).
        
        Cette méthode intercepte les appels v4.1 et les injecte dans la 
        Merkle Audit Chain de la v4.2.
        """
        if self.mode == "v4.2-hsm":
            # 1. Préparation des données (on s'assure d'avoir un timestamp)
            if "timestamp" not in log_data:
                log_data["timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # 2. Ajout à la chaine de Merkle (génère le hash interne)
            # Note: chain.append gère la liaison avec le bloc précédent
            entry_hash = self.chain.append(log_data)
            
            # 3. Signature du hash de l'entrée via HSM
            # L'agent_id est fixé à "v4.1-migrated-agent" pour l'audit
            signing_result = self.signer.sign(entry_hash.encode(), agent_id="v4.1-legacy-wrapper")
            
            # 4. Retour au format compatible v4.1 enrichi
            return {
                "version": "4.2-compat",
                "data": log_data,
                "signature": signing_result.signature.hex(),
                "merkle_root": self.chain.get_root(),
                "previous_hash": self.chain.entries[-1].previous_hash if len(self.chain) > 1 else None,
                "audit_index": len(self.chain) - 1
            }
        
        # Si on est en pur v4.1
        return self.signer.sign_log(log_data)

# --- 3. L'ASSISTANT DE MIGRATION ---
class MigrationHelper:
    """Cette classe sert à transformer tes vieux fichiers logs .json en v4.2."""
    def __init__(self, signer: TBPLogSigner):
        self.signer = signer

    def migrate_file(self, old_logs: list) -> list:
        """
        Prend une liste de vieux logs et les transforme en chaîne Merkle v4.2.
        
        Idéal pour reprendre l'historique d'avant la mise à jour 'Hard-Shield'.
        """
        new_logs = []
        # On trie pour que la chaîne Merkle soit dans le bon ordre chronologique
        # Format v4.1 attendu : {'timestamp': ..., 'data': ...} ou juste le log brut
        try:
            sorted_logs = sorted(old_logs, key=lambda x: x.get('timestamp', x.get('data', {}).get('timestamp', '')))
        except Exception:
            sorted_logs = old_logs # Pas de tri si format inconnu
            
        logger.info(f"Migration de {len(sorted_logs)} logs vers le format Merkle v4.2...")
        
        for log in sorted_logs:
            # On extrait la donnée brute à re-signer
            raw_data = log.get("data", log) 
            # On re-signe via le wrapper v4.2
            new_logs.append(self.signer.sign_log(raw_data))
        
        # Sauvegarde finale de la chaine
        self.signer.chain.save()
        logger.info("✅ Migration terminée et chaine audit_chain.json mise à jour.")
        
        return new_logs
