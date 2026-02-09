# tbp_signature_service.py
class TBPFullAuditSystem:
    """Système complet d'audit TBP avec HSM + TSA + Merkle"""
    
    def __init__(self, config: Dict[str, Any]):
        self.hsm_signer = HSMSigner(**config.get("hsm", {}))
        
        # TimeAttester optionnel (production seulement)
        if config.get("tsa", {}).get("enabled", False):
            from core.time_attester import TimeAttester
            self.time_attester = TimeAttester(**config["tsa"])
        else:
            self.time_attester = None
        
        # Merkle chain
        self.audit_chain = MerkleAuditChain(
            storage_path=config.get("storage_path"),
            auto_save=True,
            root_publisher=self._publish_root
        )
        
        # Configuration
        self.require_tsa = config.get("require_tsa", False)
    
    def _publish_root(self, root_hash: str):
        """Publier la racine (blockchain, service audit, etc.)"""
        # Implémentation spécifique au déploiement
        logger.info(f"Root ready for publication: {root_hash[:32]}...")
        # blockchain.publish(root_hash)  # Exemple
    
    def log_decision(
        self,
        decision: Dict[str, Any],
        agent_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Logger une décision TBP complètement.
        
        Returns:
            {
                "entry_hash": str,
                "root_hash": str,
                "merkle_index": int,
                "signature": bytes,
                "timestamp": datetime,
                "tsa_token": Optional
            }
        """
        # Préparer les données
        log_data = {
            "decision": decision,
            "agent_id": agent_id,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 1. Signature HSM
        data_bytes = json.dumps(log_data, sort_keys=True).encode()
        hsm_result = self.hsm_signer.sign(data_bytes, agent_id)
        
        # 2. Timestamp TSA (optionnel)
        tsa_token = None
        if self.time_attester and self.require_tsa:
            try:
                tsa_token = self.time_attester.get_timestamp(
                    hsm_result.signature
                )
            except Exception as e:
                logger.error(f"TSA failed: {e}")
                if self.require_tsa:
                    raise
        
        # 3. Ajouter à la chaine Merkle
        entry_hash = self.audit_chain.append(
            data=log_data,
            signature=hsm_result.signature,
            tsa_token=tsa_token
        )
        
        return {
            "entry_hash": entry_hash,
            "root_hash": self.audit_chain.get_root(),
            "merkle_index": len(self.audit_chain) - 1,
            "signature": hsm_result.signature,
            "timestamp": hsm_result.timestamp,
            "tsa_token": tsa_token.to_dict() if tsa_token else None
        }
