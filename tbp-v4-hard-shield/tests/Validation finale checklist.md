# TBP v4.2 - Validation Finale - Checklist Complète

**Date:** Day 4 (Jeudi)  
**Objectif:** Vérifier que v4.2 est prêt pour Production  
**Assigné:** Caetano  
**Reviewer:** Philippe

---

## 📊 Section 1 : Tests Unitaires

### 1.1 Lancer tous les tests

```bash
cd tbp-v4-hard-shield

# Tests complets
pytest tests/ -v --tb=short

# Résultat attendu:
# - ✅ 56+ tests PASSED
# - ⏭️  3-5 tests SKIPPED (hardware HSM, réseau)
# - ❌ 0 tests FAILED
```

**Critère de succès:** 0 failures, 56+ passed

### 1.2 Tests par module

```bash
# HSM Signer
pytest tests/unit/test_hsm_signer.py -v
# Expected: 13/13 passed (+ 3 skipped)

# Time Attester
pytest tests/unit/test_time_attester.py -v
# Expected: 12/12 passed

# Merkle Audit
pytest tests/unit/test_merkle_audit*.py -v
# Expected: 39/39 passed

# Adversarial
pytest tests/adversarial/ -v
# Expected: 4+ passed (dépend implémentation Day 3)
```

**Critère de succès:** Tous les modules passent

---

## 📈 Section 2 : Coverage

### 2.1 Générer rapport coverage

```bash
# Installer coverage si besoin
pip install pytest-cov

# Générer rapport
pytest tests/ --cov=core --cov-report=html --cov-report=term

# Ouvrir rapport HTML
open htmlcov/index.html  # macOS
# ou
xdg-open htmlcov/index.html  # Linux
# ou
start htmlcov/index.html  # Windows
```

**Critère de succès:** Coverage > 80% pour chaque module

### 2.2 Vérifier coverage par fichier

```bash
pytest tests/ --cov=core --cov-report=term-missing
```

**Expected output:**
```
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
core/hsm_signer.py            450     45    90%   123-125, 234-236
core/time_attester.py         380     38    90%   456-458
core/merkle_audit.py          420     42    90%   567-569
---------------------------------------------------------
TOTAL                        1250    125    90%
```

**Critère de succès:**
- ✅ hsm_signer.py > 85%
- ✅ time_attester.py > 85%
- ✅ merkle_audit.py > 85%

---

## ⚡ Section 3 : Performance

### 3.1 Benchmark basique

```bash
# Créer script benchmark
cat > benchmark.py << 'EOF'
import time
from core.hsm_signer import HSMSigner, HSMType
from core.time_attester import TimeAttester, TSAType
from core.merkle_audit import MerkleAuditChain

# Test 1: HSM Signature
print("1. HSM Signature performance...")
signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
data = b"test" * 100

start = time.time()
for i in range(100):
    result = signer.sign(data, agent_id=f"bot-{i}")
elapsed = time.time() - start
print(f"   100 signatures: {elapsed:.2f}s ({100/elapsed:.1f} ops/sec)")
signer.close()

# Test 2: Timestamp (mock)
print("2. Timestamp performance (mock)...")
attester = TimeAttester(tsa_type=TSAType.MOCK)

start = time.time()
for i in range(100):
    token = attester.get_timestamp(b"test")
elapsed = time.time() - start
print(f"   100 timestamps: {elapsed:.2f}s ({100/elapsed:.1f} ops/sec)")
attester.close()

# Test 3: Merkle append
print("3. Merkle append performance...")
chain = MerkleAuditChain()

start = time.time()
for i in range(1000):
    chain.append({"entry": i})
elapsed = time.time() - start
print(f"   1000 appends: {elapsed:.2f}s ({1000/elapsed:.1f} ops/sec)")

print("\n✅ Benchmark complete")
EOF

python benchmark.py
```

**Critères de succès:**
- ✅ Signatures: > 50 ops/sec
- ✅ Timestamps (mock): > 500 ops/sec
- ✅ Merkle append: > 1000 ops/sec

### 3.2 Memory leak check (optionnel)

```bash
# Installer memory_profiler
pip install memory-profiler

# Profiler
python -m memory_profiler benchmark.py
```

**Critère:** Pas de growth > 100MB

---

## 🔒 Section 4 : Sécurité

### 4.1 Mode Production vérifié

```bash
# Test: SOFTWARE bloqué en production
TBP_PRODUCTION=true python3 << 'EOF'
from core.hsm_signer import HSMSigner, HSMType
import sys

try:
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    print("❌ FAIL: SOFTWARE should be blocked")
    sys.exit(1)
except Exception as e:
    if "disabled in production" in str(e).lower():
        print("✅ PASS: SOFTWARE blocked in production")
        sys.exit(0)
    else:
        print(f"❌ FAIL: Wrong error: {e}")
        sys.exit(1)
EOF
```

**Critère:** Exit code 0 (SUCCESS)

### 4.2 Tampering détecté

```bash
python3 << 'EOF'
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
assert is_valid == False
assert len(errors) > 0

print("✅ PASS: Tampering detected")
EOF
```

**Critère:** "✅ PASS" affiché

### 4.3 Signature replay bloqué

```bash
python3 << 'EOF'
from core.hsm_signer import HSMSigner, HSMType

signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
data = b"transfer $10000"

# Sign with bot-001
sig = signer.sign(data, agent_id="bot-001")

# Verify with correct agent: OK
assert signer.verify(data, sig, agent_id="bot-001") == True

# Verify with wrong agent: FAIL (replay blocked)
assert signer.verify(data, sig, agent_id="bot-999") == False

print("✅ PASS: Replay attack blocked")
signer.close()
EOF
```

**Critère:** "✅ PASS" affiché

---

## 🔗 Section 5 : Intégration End-to-End

### 5.1 Full chain test

```bash
cat > test_integration.py << 'EOF'
"""
Test intégration complète: HSM + TimeAttester + Merkle
"""

from core.hsm_signer import HSMSigner, HSMType
from core.time_attester import TimeAttester, TSAType
from core.merkle_audit import MerkleAuditChain
import json

print("🧪 Testing full TBP v4.2 integration...")

# Setup
signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
attester = TimeAttester(tsa_type=TSAType.MOCK)
chain = MerkleAuditChain()

# Simulate agent decision
decision_data = {
    "agent_id": "trading-bot-001",
    "action": "transfer",
    "amount": 50000,
    "to": "account-456",
    "reason": "profit taking"
}

print("1. Get trusted timestamp...")
data_bytes = json.dumps(decision_data).encode()
ts_token = attester.get_timestamp(data_bytes)
print(f"   ✓ Timestamp: {ts_token.timestamp}")

print("2. Sign with HSM...")
signature = signer.sign(data_bytes, agent_id=decision_data["agent_id"])
print(f"   ✓ Signature: {signature.key_id[:16]}...")

print("3. Add to audit chain...")
chain.append(
    decision_data,
    signature=signature.signature,
    timestamp=ts_token.timestamp,
    tsa_token=ts_token
)
print(f"   ✓ Chain length: {len(chain)}")

print("4. Verify integrity...")
is_valid, errors = chain.verify_integrity()
assert is_valid, f"Chain invalid: {errors}"
print("   ✓ Chain integrity OK")

print("5. Verify timestamp...")
assert ts_token.verify(data_bytes), "Timestamp invalid"
print("   ✓ Timestamp valid")

print("6. Verify signature...")
assert signer.verify(data_bytes, signature, agent_id=decision_data["agent_id"])
print("   ✓ Signature valid")

print("7. Get Merkle root (for publication)...")
root = chain.get_root()
print(f"   ✓ Root: {root[:32]}...")

# Cleanup
signer.close()
attester.close()

print("\n✅ FULL INTEGRATION TEST PASSED")
print("🎉 TBP v4.2 is ready for production!")
EOF

python test_integration.py
```

**Critère:** "✅ FULL INTEGRATION TEST PASSED"

---

## 📚 Section 6 : Documentation

### 6.1 Vérifier documentation existe

```bash
# Docs principales
ls -lh docs/ARCHITECTURE_DECISIONS.md
ls -lh docs/MIGRATION_GUIDE.md
ls -lh docs/TESTING_V4.2.md

# Docs core
ls -lh core/TIME_ATTESTER_QUICKSTART.md

# Docs policies
ls -lh policies/readme.md

# Expected: Tous les fichiers existent et > 1KB
```

### 6.2 README est à jour

```bash
# Vérifier README.md mentionne v4.2
grep -i "v4.2\|4.2" README.md

# Expected: Au moins une mention de v4.2
```

---

## 📦 Section 7 : Dépendances

### 7.1 requirements.txt complet

```bash
# Vérifier dépendances critiques
cat requirements.txt | grep -E "(asn1crypto|cryptography|pkcs11|pytest)"

# Expected output:
# asn1crypto>=1.5.1
# cryptography>=41.0.0
# python-pkcs11>=0.7.0
# pytest>=7.4.0
```

### 7.2 Installation propre

```bash
# Créer venv frais
python3 -m venv /tmp/tbp-test-venv
source /tmp/tbp-test-venv/bin/activate

# Install
cd tbp-v4-hard-shield
pip install -r requirements.txt

# Test imports
python3 -c "
from core.hsm_signer import HSMSigner
from core.time_attester import TimeAttester
from core.merkle_audit import MerkleAuditChain
print('✅ All imports OK')
"

# Cleanup
deactivate
rm -rf /tmp/tbp-test-venv
```

**Critère:** "✅ All imports OK"

---

## 🐛 Section 8 : Bugs Connus

### 8.1 Liste des issues ouvertes

```bash
# Vérifier GitHub Issues
# Aucun bug bloquant (severity: critical)
```

**Critère:** 0 critical issues

### 8.2 TODOs dans le code

```bash
# Chercher TODOs critiques
grep -r "TODO.*CRITICAL" core/

# Expected: Aucun TODO critique
```

---

## 📊 Section 9 : Métriques Finales

### 9.1 Générer rapport final

```bash
cat > generate_report.py << 'EOF'
"""Generate final validation report"""

import json
import subprocess
from datetime import datetime

report = {
    "timestamp": datetime.now().isoformat(),
    "version": "v4.2",
    "validator": "Caetano",
    "tests": {},
    "coverage": {},
    "performance": {},
    "security": {},
    "status": "UNKNOWN"
}

# Run tests and capture results
try:
    result = subprocess.run(
        ["pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=60
    )
    
    # Parse output
    lines = result.stdout.split('\n')
    for line in lines:
        if 'passed' in line:
            # Extract: "56 passed, 3 skipped"
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'passed':
                    report["tests"]["passed"] = int(parts[i-1])
                elif part == 'skipped':
                    report["tests"]["skipped"] = int(parts[i-1])
                elif part == 'failed':
                    report["tests"]["failed"] = int(parts[i-1])
    
    # Determine status
    if report["tests"].get("failed", 0) == 0:
        if report["tests"].get("passed", 0) >= 56:
            report["status"] = "READY_FOR_PR"
        else:
            report["status"] = "NEEDS_MORE_TESTS"
    else:
        report["status"] = "FAILED"
    
except Exception as e:
    report["status"] = "ERROR"
    report["error"] = str(e)

# Save report
with open("validation_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))

# Print summary
print("\n" + "="*60)
print("VALIDATION SUMMARY")
print("="*60)
print(f"Status: {report['status']}")
print(f"Tests passed: {report['tests'].get('passed', 0)}")
print(f"Tests failed: {report['tests'].get('failed', 0)}")
print("\nReport saved to: validation_report.json")
EOF

python generate_report.py
```

**Critère:** `"status": "READY_FOR_PR"`

---

## ✅ Section 10 : Sign-Off

### 10.1 Checklist finale

- [ ] Tous tests unitaires passent (56+)
- [ ] Coverage > 80%
- [ ] Performance OK (benchmarks passent)
- [ ] Sécurité OK (production mode, tampering, replay)
- [ ] Intégration end-to-end OK
- [ ] Documentation existe
- [ ] requirements.txt complet
- [ ] 0 bugs critiques
- [ ] validation_report.json généré

### 10.2 Commenter sur Issue #13

```markdown
## ✅ Day 4 - Validation Complete

**Date:** [DATE]  
**Validator:** Caetano

### Test Results
- Unit tests: 56/56 passed ✅
- Coverage: 87% ✅
- Performance: All benchmarks pass ✅
- Security: All checks pass ✅
- Integration: Full chain works ✅

### Deliverables
- validation_report.json ✅
- htmlcov/ (coverage report) ✅
- benchmark results ✅

### Status
🎉 **READY FOR PULL REQUEST** 🎉

All validation criteria met. v4.2 is production-ready.

Recommend: Create PR to merge v4.2-dev → main

cc @philippeabraxas-jpg
```

### 10.3 Créer tag (optionnel)

```bash
# Tag validation complete
git tag -a v4.2-validated -m "v4.2 validation complete - ready for PR"
git push origin v4.2-validated
```

---

## 📧 Section 11 : Préparer Pull Request

### 11.1 Générer diff summary

```bash
# Voir différences vs main
git diff main...v4.2-dev --stat

# Expected: ~3500 lignes ajoutées
```

### 11.2 Générer changelog

```bash
# Commits depuis main
git log main..v4.2-dev --oneline --no-merges > CHANGELOG_v4.2.txt

# Résumer
cat CHANGELOG_v4.2.txt
```

---

## 🎯 Critères de Succès Globaux

Pour que Caetano puisse signer "Ready for PR":

| Critère | Target | Status |
|---------|--------|--------|
| Tests passed | 56+ | ⏳ |
| Tests failed | 0 | ⏳ |
| Coverage | >80% | ⏳ |
| Performance | All pass | ⏳ |
| Security checks | All pass | ⏳ |
| Integration test | Pass | ⏳ |
| Documentation | Complete | ⏳ |

**Si TOUS ✅ → Ready for PR !**

---

## 📞 Support

**Questions pendant validation ?**
- GitHub Discussions
- Issue #13
- Direct message Philippe

**Bon courage Caetano ! Tu y es presque ! 🚀**
