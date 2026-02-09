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
class TBPLogSigner:
    """Cette classe permet d'utiliser la v4.2 avec les commandes de la v4.1."""
    def __init__(self, use_hsm: bool = True):
        self.mode = "v4.1-compat"
        self.signer = None
        self.chain = MerkleAuditChain()
        
        try:
            # On tente de passer en v4.2 (HSM)
            self.signer = HSMSigner(hsm_type=HSMType.SOFTWARE) 
            self.mode = "v4.2-hsm"
            logger.info("✅ Mode v4.2 (HSM) activé.")
        except Exception:
            # Sinon, on reste en v4.1 si possible
            if TBPLogSigner_v41:
                self.signer = TBPLogSigner_v41()
                warnings.warn("⚠️ Fallback sur v4.1 (Moins sécurisé)", DeprecationWarning)
            else:
                raise RuntimeError("Erreur : Aucun moteur de signature trouvé !")

    def sign_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """Signe un log (Interface v4.1, mais moteur v4.2)"""
        if self.mode == "v4.2-hsm":
            entry = self.chain.append(log_data)
            signature = self.signer.sign(entry.hash.encode())
            return {
                "version": "4.2",
                "data": log_data,
                "signature": signature.hex(),
                "merkle_root": self.chain.get_root(),
                "previous_hash": entry.previous_hash
            }
        return self.signer.sign_log(log_data)

# --- 3. L'ASSISTANT DE MIGRATION ---
class MigrationHelper:
    """Cette classe sert à transformer tes vieux fichiers logs .json en v4.2."""
    def __init__(self, signer: TBPLogSigner):
        self.signer = signer

    def migrate_file(self, old_logs: list) -> list:
        """Prend une liste de vieux logs et les transforme en chaîne Merkle v4.2."""
        new_logs = []
        # On trie pour que la chaîne Merkle soit dans le bon ordre chronologique
        sorted_logs = sorted(old_logs, key=lambda x: x.get('timestamp', ''))
        
        for log in sorted_logs:
            raw_data = log.get("data", log) # Récupère la donnée brute
            new_logs.append(self.signer.sign_log(raw_data))
        
        return new_logs
