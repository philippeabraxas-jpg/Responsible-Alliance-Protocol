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
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Add root directory to path to allow local imports
sys.path.append(str(Path(__file__).parent))

from core.merkle_audit import MerkleAuditChain
from core.hsm_signer import HSMSigner, HSMType

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("TBP-Init")

def check_opa_policies():
    """Verify OPA policy syntax before activation."""
    logger.info("Verifying OPA policies...")
    policy_dirs = ["policy_engine", "policies"]
    
    opa_executable = "opa"
    try:
        for p_dir in policy_dirs:
            p_path = Path(__file__).parent / p_dir
            if p_path.exists():
                logger.info(f"Checking directory: {p_dir}")
                # Run 'opa check' on the directory
                result = subprocess.run(
                    [opa_executable, "check", str(p_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.error(f"OPA validation failed for {p_dir}:\n{result.stderr}")
                    return False
                logger.info(f"✅ {p_dir} policies are valid.")
        return True
    except FileNotFoundError:
        logger.warning("⚠️ 'opa' executable not found. Skipping syntax validation.")
        logger.info("Please install OPA (https://www.openpolicyagent.org/docs/latest/#installation) for production.")
        return True # Don't block dev if OPA missing, but warn

def generate_genesis_dashboard(data_dir: Path, chain: MerkleAuditChain):
    """Generate a simple HTML dashboard for the Genesis state."""
    logger.info("Generating Genesis Dashboard...")
    
    dashboard_path = data_dir / "genesis_dashboard.html"
    
    try:
        root_hash = chain.get_root()
        entry_count = len(chain)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TBP v4.2 Genesis Dashboard</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }}
        .container {{ max-width: 800px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
        h1 {{ color: #38bdf8; border-bottom: 2px solid #334155; padding-bottom: 10px; }}
        .stat {{ margin: 20px 0; padding: 15px; background: #0f172a; border-radius: 8px; border-left: 4px solid #38bdf8; }}
        .label {{ font-size: 0.875rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
        .value {{ font-family: monospace; font-size: 1.125rem; word-break: break-all; margin-top: 5px; }}
        .status {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-weight: bold; background: #10b981; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ TBP v4.2 "Hard-Shield" Status</h1>
        <div class="stat">
            <div class="label">Shield Status</div>
            <div class="value"><span class="status">ACTIVATED</span></div>
        </div>
        <div class="stat">
            <div class="label">Merkle Root (Genesis)</div>
            <div class="value">{root_hash}</div>
        </div>
        <div class="stat">
            <div class="label">Audit Chain Length</div>
            <div class="value">{entry_count} entries</div>
        </div>
        <div class="stat">
            <div class="label">Activation Timestamp</div>
            <div class="value">{datetime.now(timezone.utc).isoformat()}</div>
        </div>
        <div style="margin-top: 20px; color: #94a3b8; font-size: 0.8rem;">
            Responsible Alliance Protocol - Secure Genesis Block Created.
        </div>
    </div>
</body>
</html>
"""
        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"✅ Genesis dashboard generated: {dashboard_path}")
    except Exception as e:
        logger.error(f"Failed to generate dashboard: {e}")

def init_shield():
    print("--- TBP v4.2 'Shield-Hardening' Initialization ---\n")
    
    # 1. Directory Setup
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Directory {data_dir} ready.")

    # 2. OPA Validation
    if not check_opa_policies():
        return False

    # 3. HSM Check / Initialization
    try:
        logger.info("Checking HSM Signer status...")
        hsm_type = HSMType.SOFTWARE if os.getenv("TBP_PRODUCTION", "false").lower() != "true" else HSMType.PKCS11_GENERIC
        signer = HSMSigner(hsm_type=hsm_type)
        logger.info(f"HSM Signer initialized (Mode: {hsm_type}).")
        
        # Export public key
        pub_key = signer.get_public_key()
        pub_key_path = data_dir / "tbp_public_key.pem"
        with open(pub_key_path, "wb") as f:
            f.write(pub_key)
        logger.info(f"Public key exported to {pub_key_path}")
    except Exception as e:
        logger.error(f"HSM Initialization failed: {e}")
        return False

    # 4. Merkle Chain Initialization
    try:
        chain_path = data_dir / "audit_chain.json"
        chain = MerkleAuditChain(storage_path=str(chain_path))
        
        if len(chain) == 0:
            logger.info("Initializing Merkle Audit Chain (Genesis)...")
            genesis_data = {
                "event": "GENESIS",
                "version": "4.2.1",
                "message": "Responsible Alliance Protocol - Shield Hardening Activated",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            # Sign with HSM if possible
            signature = signer.sign(json.dumps(genesis_data).encode(), "TBP-SYSTEM").signature
            chain.append(genesis_data, signature=signature)
            chain.save()
            logger.info("Genesis block created and saved.")
        else:
            logger.info(f"Existing audit chain found ({len(chain)} entries).")

        # 5. Dashboard Generation
        generate_genesis_dashboard(data_dir, chain)
        
    except Exception as e:
        logger.error(f"Chain Initialization failed: {e}")
        return False

    print("\n✅ TBP Shield v4.2 Initialized Successfully.")
    print(f"Ready to protect the 3 invariants: F-STABILITY, I-INTEGRITY, W-MONOPOLY.")
    return True

if __name__ == "__main__":
    success = init_shield()
    sys.exit(0 if success else 1)
