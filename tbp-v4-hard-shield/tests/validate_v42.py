#!/usr/bin/env python3
"""
TBP v4.2.1 - Automated Validation Script (Industrial Grade)
Includes Performance Benchmarking, E2E Integration, Rate Limiting, and Pattern Analysis.
"""

import subprocess
import sys
import json
import time
import os
import statistics
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Fix path to allow importing from parent
sys.path.append(str(Path(__file__).parent.parent))

from core.hsm_signer import HSMSigner, HSMType
from core.merkle_audit import MerkleAuditChain
from core.tbp_signature_service import TBPFullAuditSystem
from policy_engine.rate_limiter import RateLimiter
from policy_engine.pattern_analysis import PatternAnalyzer

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

class ValidationRunner:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "version": "v4.2.1",
            "summary": {"total": 0, "passed": 0, "failed": 0}
        }
        # Silence noisy logs during validation
        logging.getLogger("TBP-Init").setLevel(logging.ERROR)
        logging.getLogger("tbp.rate_limiter").setLevel(logging.ERROR)

    def print_header(self, text: str):
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

    def print_check(self, name: str, passed: bool, details: str = ""):
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"{status} - {name}")
        if details: print(f"      {details}")
        self.results["summary"]["total"] += 1
        if passed: self.results["summary"]["passed"] += 1
        else: self.results["summary"]["failed"] += 1

    def check_hsm_performance(self):
        self.print_header("1. HSM PERFORMANCE BENCHMARK")
        try:
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            payload = b"benchmark_data_v421"
            latencies = []

            for i in range(100):
                start = time.perf_counter()
                signer.sign(payload, agent_id=f"perf-{i}")
                latencies.append((time.perf_counter() - start) * 1000)

            avg_lat = statistics.mean(latencies)
            p95_lat = statistics.quantiles(latencies, n=20)[18] 
            
            passed = p95_lat <= 5.0
            self.print_check(
                "HSM Latency (P95 < 5ms)", 
                passed, 
                f"Avg: {avg_lat:.2f}ms, P95: {p95_lat:.2f}ms"
            )
        except Exception as e:
            self.print_check("HSM Performance", False, str(e))

    def check_rate_limiting(self):
        self.print_header("2. RATE LIMITING (DoS PROTECTION)")
        try:
            limiter = RateLimiter(window_seconds=10)
            limiter.limits["test_action"] = 5
            
            # First 5 should pass
            success_count = 0
            for _ in range(5):
                if limiter.check_limit("attacker-001", "test_action"):
                    success_count += 1
            
            # 6th should be blocked
            blocked = not limiter.check_limit("attacker-001", "test_action")
            
            passed = (success_count == 5) and blocked
            self.print_check(
                "Rate Limiter Enforcement", 
                passed, 
                "Blocked attacker after 5 requests" if passed else f"Failed: success={success_count}, blocked={blocked}"
            )
        except Exception as e:
            self.print_check("Rate Limiter", False, str(e))

    def check_pattern_analysis(self):
        self.print_header("3. PATTERN ANALYSIS (SALAMI ATTACK)")
        try:
            analyzer = PatternAnalyzer(thresholds={"cumulative_24h_amount": 1000})
            
            # Send 10 small transactions of $150 (Total $1500 > $1000 threshold)
            risks = []
            for _ in range(10):
                metrics = analyzer.analyze({"agent_id": "bot-001", "action": "transfer", "amount": 150})
                risks.append(metrics.risk_score)
            
            # Risk should increase as we approach/exceed threshold
            detection = risks[-1] > risks[0] and risks[-1] > 50
            
            self.print_check(
                "Salami Attack Detection", 
                detection, 
                f"Initial Risk: {risks[0]:.1f}, Final Risk: {risks[-1]:.1f}"
            )
        except Exception as e:
            self.print_check("Pattern Analysis", False, str(e))

    def check_full_audit_chain(self):
        self.print_header("4. FULL AUDIT SYSTEM (HSM + MERKLE)")
        try:
            config = {"hsm": {"hsm_type": "software"}, "storage_path": "tests/test_audit_chain.json"}
            system = TBPFullAuditSystem(config)
            
            # Log a decision
            decision = {"allowed": True, "reason": "test"}
            result = system.log_decision(decision, "agent-test", {"context": "validation"})
            
            # Verify chain
            valid, errors = system.audit_chain.verify_integrity()
            
            # Cleanup
            if os.path.exists("tests/test_audit_chain.json"):
                os.remove("tests/test_audit_chain.json")

            self.print_check(
                "Cryptographic Bundle Integrity", 
                valid and "signature" in result, 
                "HSM Signature + Merkle Linkage: OK"
            )
        except Exception as e:
            self.print_check("Full Audit System", False, str(e))

    def run_all(self):
        self.check_hsm_performance()
        self.check_rate_limiting()
        self.check_pattern_analysis()
        self.check_full_audit_chain()
        
        passed = self.results["summary"]["passed"]
        total = self.results["summary"]["total"]
        success = (passed == total)
        
        print(f"\n{Colors.BOLD}{Colors.GREEN if success else Colors.RED}")
        print(f"VALDATION STATUS: {'READY_FOR_PR' if success else 'NEEDS_FIXES'}")
        print(f"Score: {passed}/{total}{Colors.END}\n")
        return 0 if success else 1

if __name__ == "__main__":
    runner = ValidationRunner()
    sys.exit(runner.run_all())
