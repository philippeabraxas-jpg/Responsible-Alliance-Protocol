#!/usr/bin/env python3
"""
TBP v4.2 - Automated Validation Script

Run all validation checks automatically.
Usage: python validate_v42.py
"""

import subprocess
import sys
import json
import time
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
    """Run all validation checks"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "version": "v4.2",
            "checks": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0
            }
        }
    
    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    def print_check(self, name: str, passed: bool, details: str = ""):
        """Print check result"""
        status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
        print(f"{status} - {name}")
        if details:
            print(f"      {details}")
        
        self.results["summary"]["total"] += 1
        if passed:
            self.results["summary"]["passed"] += 1
        else:
            self.results["summary"]["failed"] += 1
        
        self.results["checks"][name] = {
            "passed": passed,
            "details": details
        }
    
    def run_command(self, cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """Run command and return (success, output)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "Command timed out")
        except Exception as e:
            return (False, str(e))
    
    def check_dependencies(self):
        """Check all dependencies installed"""
        self.print_header("1. DEPENDENCIES")
        
        required = [
            "asn1crypto",
            "cryptography",
            "pytest",
            "requests"
        ]
        
        for pkg in required:
            try:
                __import__(pkg)
                self.print_check(f"Import {pkg}", True)
            except ImportError:
                self.print_check(f"Import {pkg}", False, f"Run: pip install {pkg}")
    
    def check_unit_tests(self):
        """Run unit tests"""
        self.print_header("2. UNIT TESTS")
        
        success, output = self.run_command([
            "pytest", "tests/unit/", "-v", "--tb=short", "-q"
        ])
        
        # Parse output
        passed = failed = 0
        for line in output.split('\n'):
            if 'passed' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        passed = int(parts[i-1])
                    elif part == 'failed':
                        failed = int(parts[i-1])
        
        self.print_check(
            "Unit tests",
            success and failed == 0,
            f"{passed} passed, {failed} failed"
        )
    
    def check_coverage(self):
        """Check code coverage"""
        self.print_header("3. COVERAGE")
        
        success, output = self.run_command([
            "pytest", "tests/", "--cov=core", "--cov-report=term", "-q"
        ])
        
        # Parse coverage
        coverage = 0
        for line in output.split('\n'):
            if 'TOTAL' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if '%' in part:
                        coverage = int(part.replace('%', ''))
        
        self.print_check(
            "Code coverage",
            coverage >= 80,
            f"{coverage}% (target: 80%)"
        )
    
    def check_performance(self):
        """Basic performance check"""
        self.print_header("4. PERFORMANCE")
        
        # Test HSM signing speed
        try:
            from core.hsm_signer import HSMSigner, HSMType
            
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            data = b"test" * 100
            
            start = time.time()
            for i in range(100):
                signer.sign(data, agent_id=f"bot-{i}")
            elapsed = time.time() - start
            
            ops_per_sec = 100 / elapsed
            signer.close()
            
            self.print_check(
                "HSM signing performance",
                ops_per_sec >= 50,
                f"{ops_per_sec:.1f} ops/sec (target: 50)"
            )
        except Exception as e:
            self.print_check("HSM signing performance", False, str(e))
        
        # Test Merkle append speed
        try:
            from core.merkle_audit import MerkleAuditChain
            
            chain = MerkleAuditChain()
            
            start = time.time()
            for i in range(1000):
                chain.append({"entry": i})
            elapsed = time.time() - start
            
            ops_per_sec = 1000 / elapsed
            
            self.print_check(
                "Merkle append performance",
                ops_per_sec >= 1000,
                f"{ops_per_sec:.1f} ops/sec (target: 1000)"
            )
        except Exception as e:
            self.print_check("Merkle append performance", False, str(e))
    
    def check_security(self):
        """Security checks"""
        self.print_header("5. SECURITY")
        
        # Check 1: Production mode blocks SOFTWARE
        try:
            import os
            os.environ["TBP_PRODUCTION"] = "true"
            
            from core.hsm_signer import HSMSigner, HSMType
            
            try:
                signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
                self.print_check("Production mode enforcement", False, "SOFTWARE not blocked")
            except Exception as e:
                if "disabled in production" in str(e).lower():
                    self.print_check("Production mode enforcement", True)
                else:
                    self.print_check("Production mode enforcement", False, f"Wrong error: {e}")
            
            os.environ["TBP_PRODUCTION"] = "false"
        except Exception as e:
            self.print_check("Production mode enforcement", False, str(e))
        
        # Check 2: Tampering detection
        try:
            from core.merkle_audit import MerkleAuditChain
            
            chain = MerkleAuditChain()
            chain.append({"test": "data1"})
            chain.append({"test": "data2"})
            
            # Verify OK
            assert chain.verify_integrity()[0] == True
            
            # Tamper
            chain.entries[0].data["test"] = "HACKED"
            
            # Should detect
            is_valid, errors = chain.verify_integrity()
            
            self.print_check(
                "Tampering detection",
                not is_valid and len(errors) > 0
            )
        except Exception as e:
            self.print_check("Tampering detection", False, str(e))
        
        # Check 3: Replay attack protection
        try:
            from core.hsm_signer import HSMSigner, HSMType
            
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            data = b"transfer $10000"
            
            sig = signer.sign(data, agent_id="bot-001")
            
            # Correct agent: should pass
            valid_correct = signer.verify(data, sig, agent_id="bot-001")
            
            # Wrong agent: should fail
            valid_wrong = signer.verify(data, sig, agent_id="bot-999")
            
            signer.close()
            
            self.print_check(
                "Replay attack protection",
                valid_correct and not valid_wrong
            )
        except Exception as e:
            self.print_check("Replay attack protection", False, str(e))
    
    def check_integration(self):
        """End-to-end integration test"""
        self.print_header("6. INTEGRATION")
        
        try:
            from core.hsm_signer import HSMSigner, HSMType
            from core.time_attester import TimeAttester, TSAType
            from core.merkle_audit import MerkleAuditChain
            import json
            
            # Setup
            signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
            attester = TimeAttester(tsa_type=TSAType.MOCK)
            chain = MerkleAuditChain()
            
            # Decision
            decision_data = {
                "agent_id": "bot-001",
                "action": "transfer",
                "amount": 50000
            }
            
            # Timestamp
            data_bytes = json.dumps(decision_data).encode()
            ts_token = attester.get_timestamp(data_bytes)
            
            # Sign
            signature = signer.sign(data_bytes, agent_id=decision_data["agent_id"])
            
            # Add to chain
            chain.append(
                decision_data,
                signature=signature.signature,
                timestamp=ts_token.timestamp,
                tsa_token=ts_token
            )
            
            # Verify
            chain_valid = chain.verify_integrity()[0]
            ts_valid = ts_token.verify(data_bytes)
            sig_valid = signer.verify(data_bytes, signature, agent_id=decision_data["agent_id"])
            
            # Cleanup
            signer.close()
            attester.close()
            
            self.print_check(
                "Full chain integration",
                chain_valid and ts_valid and sig_valid,
                "HSM + TimeAttester + Merkle"
            )
        except Exception as e:
            self.print_check("Full chain integration", False, str(e))
    
    def check_documentation(self):
        """Check documentation exists"""
        self.print_header("7. DOCUMENTATION")
        
        docs = [
            "docs/ARCHITECTURE_DECISIONS.md",
            "docs/MIGRATION_GUIDE.md",
            "docs/TESTING_V4.2.md",
            "core/TIME_ATTESTER_QUICKSTART.md",
            "README.md"
        ]
        
        for doc in docs:
            exists = Path(doc).exists()
            size = Path(doc).stat().st_size if exists else 0
            
            self.print_check(
                f"Documentation: {doc}",
                exists and size > 1000,
                f"{size} bytes"
            )
    
    def generate_report(self):
        """Generate final report"""
        self.print_header("VALIDATION SUMMARY")
        
        total = self.results["summary"]["total"]
        passed = self.results["summary"]["passed"]
        failed = self.results["summary"]["failed"]
        
        print(f"Total checks:  {total}")
        print(f"{Colors.GREEN}Passed:        {passed}{Colors.END}")
        print(f"{Colors.RED}Failed:        {failed}{Colors.END}")
        print(f"Success rate:  {100*passed/total:.1f}%\n")
        
        # Determine status
        if failed == 0:
            status = "READY_FOR_PR"
            status_color = Colors.GREEN
            emoji = "🎉"
        elif failed <= 2:
            status = "MINOR_ISSUES"
            status_color = Colors.YELLOW
            emoji = "⚠️"
        else:
            status = "NEEDS_WORK"
            status_color = Colors.RED
            emoji = "❌"
        
        print(f"{status_color}{Colors.BOLD}{emoji} Status: {status} {emoji}{Colors.END}\n")
        
        self.results["status"] = status
        
        # Save report
        with open("validation_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"📄 Report saved to: validation_report.json")
        
        return status == "READY_FOR_PR"
    
    def run_all(self):
        """Run all validation checks"""
        print(f"{Colors.BOLD}TBP v4.2 - Automated Validation{Colors.END}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.check_dependencies()
        self.check_unit_tests()
        self.check_coverage()
        self.check_performance()
        self.check_security()
        self.check_integration()
        self.check_documentation()
        
        success = self.generate_report()
        
        return 0 if success else 1


if __name__ == "__main__":
    runner = ValidationRunner()
    sys.exit(runner.run_all())
