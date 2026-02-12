#!/usr/bin/env python3
"""
TBP v4.2.1 - Automated Validation Script (Industrial Grade)
Includes Performance Benchmarking and E2E Integration.
"""

import subprocess
import sys
import json
import time
import os
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

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
            "checks": {},
            "summary": {"total": 0, "passed": 0, "failed": 0}
        }

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

    # --- NOUVELLE SECTION : PERFORMANCE BENCHMARK ---
    def check_performance_benchmarks(self):
        self.print_header("4. PERFORMANCE BENCHMARKS (SLA)")
        try:
            from core.hsm_signer import HSMSigner, HSMType
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            payload = b"benchmark_data_v421"
            latencies = []

            for i in range(100):
                start = time.perf_counter()
                signer.sign(payload, agent_id=f"perf-{i}")
                latencies.append((time.perf_counter() - start) * 1000)

            avg_lat = statistics.mean(latencies)
            p95_lat = statistics.quantiles(latencies, n=20)[18] # 95th percentile
            
            signer.close()
            
            passed = p95_lat <= 5.0
            self.print_check(
                "HSM Latency (P95 < 5ms)", 
                passed, 
                f"Avg: {avg_lat:.2f}ms, P95: {p95_lat:.2f}ms"
            )
        except Exception as e:
            self.print_check("Performance Benchmarks", False, str(e))

    # --- NOUVELLE SECTION : INTEGRATION E2E ---
    def check_e2e_integration(self):
        self.print_header("7. E2E INTEGRATION (FULL CHAIN)")
        try:
            from core.hsm_signer import HSMSigner, HSMType
            from core.merkle_audit import MerkleAuditChain
            from policy_engine.enforcer import TBPEnforcer
            
            # Init
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            audit = MerkleAuditChain(storage_path="tests/e2e_audit.json")
            enforcer = TBPEnforcer()
            
            # Flow
            action = {"agent_id": "bot-e2e", "type": "critical_op", "val": 100}
            data = json.dumps(action).encode()
            
            # 1. Sign
            sig_res = signer.sign(data, agent_id=action["agent_id"])
            # 2. Enforce
            allowed, _ = enforcer.check_policy(action, sig_res)
            # 3. Audit
            audit.append(action, signature=sig_res.signature)
            # 4. Verify Integrity
            valid, _ = audit.verify_integrity()
            
            signer.close()
            if os.path.exists("tests/e2e_audit.json"): os.remove("tests/e2e_audit.json")

            self.print_check(
                "End-to-End Workflow", 
                allowed and valid, 
                "Sign -> Policy -> Merkle -> Integrity: OK"
            )
        except Exception as e:
            self.print_check("E2E Integration", False, str(e))

    def run_all(self):
        # On réutilise les méthodes précédentes (Dependencies, Unit Tests, etc.)
        self.check_performance_benchmarks()
        self.check_e2e_integration()
        # ... (Appel des autres sections)
        
        # Résumé Final
        passed = self.results["summary"]["passed"]
        total = self.results["summary"]["total"]
        success = (passed == total)
        
        print(f"\n{Colors.BOLD}{Colors.GREEN if success else Colors.RED}")
        print(f"STATUS: {'READY_FOR_PRODUCTION' if success else 'NEEDS_WORK'}")
        print(f"Score: {passed}/{total}{Colors.END}\n")
        return 0 if success else 1

if __name__ == "__main__":
    runner = ValidationRunner()
    sys.exit(runner.run_all())
