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
from typing import Dict, Any, Optional
import logging

# v4.1 imports (old)
try:
    from tbp_v4_hard_shield.integrations.log_signer import TBPLogSigner as TBPLogSigner_v41
except ImportError:
    TBPLogSigner_v41 = None

# v4.2 imports (new)
from core.hsm_signer import HSMSigner, HSMType
from core.merkle_audit import MerkleAuditChain

logger = logging.getLogger(__name__)


class TBPLogSigner:
    """
    Backward-compatible wrapper for v4.1 TBPLogSigner.
    
    Behavior:
    - If HSM available: Use v4.2 (hsm_signer.py)
    - If no HSM: Fallback to v4.1 (software keys)
    - Warn user about migration path
    
    Usage (identical to v4.1):
        signer = TBPLogSigner()  # Auto-detects best mode
        signed = signer.sign_log(log_data)
        assert signer.verify_log(signed)
    """
    
    def __init__(self, use_hsm: bool = True, auto_migrate: bool = True):
        """
        Initialize log signer with backward compatibility.
        
        Args:
            use_hsm: Try to use HSM if available (v4.2)
            auto_migrate: Automatically upgrade to v4.2 features
        
        TODO (Caetano):
            1. Detect if HSM is available
            2. If yes: use v4.2 HSMSigner
            3. If no: fallback to v4.1 software keys
            4. Warn user about their mode
            5. Store mode for later reference
        """
        self.mode = "unknown"
        self.signer = None
        self.chain = MerkleAuditChain() if auto_migrate else None
        
        if use_hsm:
            try:
                # Try v4.2 HSM mode
                self.signer = HSMSigner(hsm_type=HSMType.SOFTWARE)  # TODO: Auto-detect real HSM
                self.mode = "v4.2-hsm"
                logger.info("✅ Using v4.2 HSM signer")
            except Exception as e:
                logger.warning(f"HSM not available: {e}")
                self._fallback_to_v41()
        else:
            self._fallback_to_v41()
        
        if auto_migrate and self.mode == "v4.1-compat":
            warnings.warn(
                "⚠️  Running in v4.1 compatibility mode. "
                "Consider migrating to v4.2 for enhanced security. "
                "See MIGRATION_GUIDE.md",
                DeprecationWarning
            )
    
    def _fallback_to_v41(self):
        """Fallback to v4.1 software keys"""
        if TBPLogSigner_v41:
            self.signer = TBPLogSigner_v41()
            self.mode = "v4.1-compat"
            logger.warning("⚠️  Fallback to v4.1 software keys (not recommended for production)")
        else:
            raise ImportError("Neither v4.2 HSM nor v4.1 software keys available")
    
    def sign_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign log entry (v4.1 compatible interface).
        
        Args:
            log_data: Log entry to sign
        
        Returns:
            Signed log with backward-compatible format
        
        TODO (Caetano):
            1. Sign using underlying signer (v4.1 or v4.2)
            2. Add to Merkle chain if v4.2
            3. Return in v4.1 format for compatibility
        """
        # TODO: Implement signing with backward compatibility
        raise NotImplementedError("sign_log not yet implemented")
    
    def verify_log(self, signed_log: Dict[str, Any]) -> bool:
        """
        Verify log signature (v4.1 compatible interface).
        
        Args:
            signed_log: Signed log entry
        
        Returns:
            True if signature valid
        
        TODO (Caetano):
            1. Detect if log is v4.1 or v4.2 format
            2. Verify using appropriate method
            3. Return boolean
        """
        # TODO: Implement verification with format auto-detection
        raise NotImplementedError("verify_log not yet implemented")


class MigrationHelper:
    """
    Utilities for migrating from v4.1 to v4.2.
    
    Features:
    - Batch convert v4.1 logs to v4.2 format
    - Verify migration integrity
    - Generate migration report
    
    Usage:
        helper = MigrationHelper()
        helper.migrate_logs("v4.1_logs.json", "v4.2_logs.json")
        helper.verify_migration()
        helper.generate_report()
    """
    
    def __init__(self):
        """
        Initialize migration helper.
        
        TODO (Caetano):
            1. Setup logging
            2. Initialize counters
            3. Prepare migration tracking
        """
        self.migrated_count = 0
        self.failed_count = 0
        self.warnings = []
    
    def migrate_logs(self, input_file: str, output_file: str):
        """
        Migrate v4.1 logs to v4.2 format.
        
        Args:
            input_file: Path to v4.1 logs (JSON)
            output_file: Path for v4.2 logs
        
        TODO (Caetano):
            1. Read v4.1 logs
            2. For each log:
               - Verify v4.1 signature (ensure not tampered)
               - Convert to v4.2 format
               - Add to Merkle chain
               - Re-sign with HSM
            3. Write v4.2 logs
            4. Generate migration report
        """
        logger.info(f"Migrating logs from {input_file} to {output_file}")
        # TODO: Implement batch migration
        pass
    
    def verify_migration(self) -> bool:
        """
        Verify migration completed successfully.
        
        Checks:
        - All v4.1 logs migrated
        - All signatures valid (both v4.1 and v4.2)
        - Merkle chain integrity
        - No data loss
        
        Returns:
            True if migration successful
        
        TODO (Caetano):
            1. Count logs in input vs output
            2. Verify each signature
            3. Check Merkle chain
            4. Return True only if ALL checks pass
        """
        # TODO: Implement migration verification
        return False
    
    def generate_report(self) -> str:
        """
        Generate human-readable migration report.
        
        Returns:
            Markdown-formatted report
        
        TODO (Caetano):
            Include:
            - Total logs migrated
            - Failures (if any)
            - Warnings
            - Performance stats
            - Next steps
        """
        report = f"""
# v4.1 → v4.2 Migration Report

## Summary
- **Total logs:** {self.migrated_count + self.failed_count}
- **Successfully migrated:** {self.migrated_count}
- **Failed:** {self.failed_count}

## Warnings
"""
        for warning in self.warnings:
            report += f"- ⚠️  {warning}\n"
        
        report += "\n## Next Steps\n"
        report += "1. Verify production deployment\n"
        report += "2. Monitor for issues\n"
        report += "3. Deprecate v4.1 after 30 days\n"
        
        return report


# =============================================================================
# Migration Detector (Auto-detect which version is running)
# =============================================================================

def detect_version() -> str:
    """
    Auto-detect if running v4.1 or v4.2.
    
    Returns:
        "v4.1" or "v4.2" or "unknown"
    
    TODO (Caetano):
        1. Check for HSM presence
        2. Check for Merkle chain
        3. Check log format
        4. Return detected version
    """
    # TODO: Implement version detection
    return "unknown"


# =============================================================================
# Example Migration Script
# =============================================================================

if __name__ == "__main__":
    print("=== TBP v4.1 → v4.2 Migration Tool ===\n")
    
    # Detect current version
    current = detect_version()
    print(f"Current version: {current}")
    
    if current == "v4.1":
        print("\n📦 Migration available!")
        print("Run: python -m integrations.backward_v4.1 --migrate")
    elif current == "v4.2":
        print("\n✅ Already on v4.2")
    else:
        print("\n⚠️  Cannot detect version")
    
    # Example migration
    # helper = MigrationHelper()
    # helper.migrate_logs("v4.1_audit_logs.json", "v4.2_audit_logs.json")
    # if helper.verify_migration():
    #     print(helper.generate_report())
    
    print("\n⚠️  Implementation pending. See TODO comments above.")
