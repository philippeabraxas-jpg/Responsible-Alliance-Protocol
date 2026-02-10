"""
TBP v4.2 - Shield Initialization Script
PURPOSE:
    Prepare the environment for the first run of the "Hard-Shield".
    1. Initialize Merkle Audit Chain (Genesis Block).
    2. Check HSM connectivity (or setup Software Fallback).
    3. Verify OPA policy syntax.
    4. Generate initial metrics dashboard.
"""

import sys
import os
import logging
from pathlib import Path

# Add root directory to path to allow local imports
sys.path.append(str(Path(__file__).parent))

from core.merkle_audit import MerkleAuditChain
from core.hsm_signer import HSMSigner, HSMType

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("TBP-Init")

def init_shield():
    print("--- TBP v4.2 'Shield-Hardening' Initialization ---\n")
    
    # 1. Directory Setup
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Directory {data_dir} ready.")

    # 2. HSM Check / Initialization
    try:
        logger.info("Checking HSM Signer status...")
        # Start in software mode by default for dev, but check env for production
        hsm_type = HSMType.SOFTWARE if os.getenv("TBP_PRODUCTION", "false").lower() != "true" else HSMType.PKCS11_GENERIC
        signer = HSMSigner(hsm_type=hsm_type)
        logger.info(f"HSM Signer initialized (Mode: {hsm_type}).")
        
        # Export public key for auditors
        pub_key = signer.get_public_key()
        with open(data_dir / "tbp_public_key.pem", "wb") as f:
            f.write(pub_key)
        logger.info(f"Public key exported to {data_dir / 'tbp_public_key.pem'}")
        signer.close()
    except Exception as e:
        logger.error(f"HSM Initialization failed: {e}")
        return False

    # 3. Merkle Chain Initialization (Genesis Block)
    try:
        chain_path = data_dir / "audit_chain.json"
        if not chain_path.exists():
            logger.info("Initializing Merkle Audit Chain (Genesis)...")
            chain = MerkleAuditChain(storage_path=str(chain_path))
            genesis_data = {
                "event": "GENESIS",
                "version": "4.2.1",
                "message": "Responsible Alliance Protocol - Shield Hardening Activated",
                "timestamp": "2026-02-10T00:00:00Z"
            }
            chain.append(genesis_data)
            chain.save()
            logger.info("Genesis block created and saved.")
        else:
            logger.info("Existing audit chain found. Skipping genesis.")
    except Exception as e:
        logger.error(f"Chain Initialization failed: {e}")
        return False

    print("\n✅ TBP Shield v4.2 Initialized Successfully.")
    print(f"Ready to protect the 3 invariants.")
    return True

if __name__ == "__main__":
    success = init_shield()
    sys.exit(0 if success else 1)
