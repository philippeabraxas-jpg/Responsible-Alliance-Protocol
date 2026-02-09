import hashlib
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AuditVerifier:
    """
    Vérificateur tiers indépendant. 
    Permet de valider un log sans avoir accès à l'intégralité de la chaîne.
    """

    @staticmethod
    def hash_leaf(entry_data: Dict[str, Any], previous_hash: str) -> str:
        """Reconstitue le hash d'une feuille à partir des données brutes."""
        canonical_json = json.dumps(entry_data, sort_keys=True, separators=(',', ':'))
        # Note: On doit reproduire exactement la logique de AuditEntry.compute_hash
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    @staticmethod
    def verify_merkle_proof(leaf_hash: str, proof: List[str], index: int, root_hash: str) -> bool:
        """
        Reconstruit la racine à partir d'une preuve de Merkle (chemins frères).
        """
        current_hash = leaf_hash
        
        # Le bit de l'index indique si on est à gauche (0) ou à droite (1) à chaque niveau
        for i, sibling_hash in enumerate(proof):
            if (index >> i) & 1:
                # On est à droite, le frère est à gauche
                combined = sibling_hash + current_hash
            else:
                # On est à gauche, le frère est à droite
                combined = current_hash + sibling_hash
            
            current_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        return current_hash == root_hash

    def verify_full_proof(
        self, 
        log_entry: Dict[str, Any], 
        merkle_proof: List[str], 
        merkle_index: int, 
        public_root: str
    ) -> bool:
        """
        Validation complète d'un point d'audit.
        """
        try:
            # 1. Calcul du hash de l'entrée (Payload + Header - Signature)
            # On extrait les données nécessaires
            data = log_entry["payload"]
            prev_hash = log_entry["header"]["previous_hash"]
            
            leaf_hash = self.hash_leaf(data, prev_hash)
            
            # Vérification de cohérence interne du log fourni
            if leaf_hash != log_entry["header"]["hash"]:
                logger.error("Le hash du log fourni est invalide (Tampering détecté)")
                return False

            # 2. Vérification de l'appartenance à la racine publique
            is_in_root = self.verify_merkle_proof(leaf_hash, merkle_proof, merkle_index, public_root)
            
            if is_in_root:
                print("✅ Vérification réussie : Le log est authentique et immuable.")
                return True
            else:
                print("❌ Échec : Le log ne correspond pas à la racine d'audit publiée.")
                return False

        except Exception as e:
            logger.error(f"Erreur de vérification : {e}")
            return False

# --- Exemple de test de vérification ---
if __name__ == "__main__":
    verifier = AuditVerifier()
    
    # Données reçues pour vérification (simulées)
    sample_log = {
        "payload": {"decision": "ALLOW", "agent": "TBP-01"},
        "header": {
            "previous_hash": "000000000000...",
            "hash": "abc123hash...", # Le hash calculé à l'époque
        }
    }
    
    # Preuve fournie par le système
    sample_proof = ["sibling_hash_1", "sibling_hash_2"]
    root_validee = "root_hash_publie_sur_blockchain"
    
    # verifier.verify_full_proof(sample_log, sample_proof, 0, root_validee)
