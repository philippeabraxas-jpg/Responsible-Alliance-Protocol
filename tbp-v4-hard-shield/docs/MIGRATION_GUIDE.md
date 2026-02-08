# Migration Guide: v4.1 → v4.2

**Target Audience:** DevOps, System Administrators, Security Engineers  
**Estimated Time:** 2-4 hours (depends on deployment size)  
**Risk Level:** Low (backward compatible, rollback supported)

---

## 📋 Pre-Migration Checklist

**Before starting, ensure:**

- [ ] v4.1 is running stable (no recent issues)
- [ ] Full backup of audit logs exists
- [ ] Staging environment available for testing
- [ ] Rollback plan documented
- [ ] Team availability (2-3 people recommended)
- [ ] Maintenance window scheduled (optional but recommended)

**If ANY checkbox unchecked → STOP. Fix issue first.**

---

## 🎯 Migration Strategy Overview

**Philosophy:** Zero downtime, gradual rollout, easy rollback.

**Phases:**
1. **Preparation** (Day 1): Backup, test in staging
2. **Deployment** (Day 2-3): Deploy v4.2 alongside v4.1
3. **Validation** (Day 4-7): Monitor, compare outputs
4. **Switchover** (Day 8): Route traffic to v4.2
5. **Cleanup** (Day 30+): Remove v4.1

**Total timeline:** 1 month (conservative)

---

## Phase 1: Preparation (Day 1)

### Step 1.1: Backup Current State

```bash
# Backup audit logs
cd /var/tbp/logs
tar -czf audit_logs_backup_$(date +%Y%m%d).tar.gz *.json

# Backup configuration
kubectl get configmap tbp-policies -n tbp-system -o yaml > tbp-policies-backup.yaml

# Backup keys
cp /path/to/tbp_private_key.pem /secure/backup/
cp /path/to/tbp_public_key.pem /secure/backup/

# Verify backups
ls -lh *backup*
```

**⚠️ CRITICAL:** Store backups OFF the server (S3, NAS, etc.)

### Step 1.2: Review Current Configuration

```bash
# Check current version
kubectl get deployment -n tbp-system
kubectl describe pod -n tbp-system | grep Image

# Check current thresholds
kubectl exec -n tbp-system tbp-opa-xxx -- curl localhost:8181/v1/data/tbp/config

# Document any customizations
diff tbp_core.rego /path/to/default/tbp_core.rego
```

**Save output for reference.**

### Step 1.3: Test in Staging

```bash
# Deploy v4.2 to staging
cd tbp-v4.2-shield-hardening
./deploy-staging.sh

# Run test suite
pytest tests/ -v

# Run backward compatibility tests
pytest tests/test_backward_compat.py -v

# Verify all v4.1 tests still pass
cd ../tbp-v4-hard-shield
pytest tests/ -v
```

**Expected result:** All tests pass. If not → investigate before proceeding.

---

## Phase 2: Deployment (Day 2-3)

### Step 2.1: Deploy v4.2 Components

**Option A: Kubernetes (Recommended)**

```bash
# Create v4.2 namespace (separate from v4.1)
kubectl create namespace tbp-system-v42

# Deploy HSM signer
kubectl apply -f deployment/hsm-signer.yaml -n tbp-system-v42

# Deploy Merkle audit service
kubectl apply -f deployment/merkle-audit.yaml -n tbp-system-v42

# Deploy OPA with v4.2 policies
kubectl apply -f deployment/opa-v42.yaml -n tbp-system-v42

# Verify all pods running
kubectl get pods -n tbp-system-v42
```

**Option B: Docker Compose**

```bash
# Deploy v4.2 stack
cd tbp-v4.2-shield-hardening/deployment
docker-compose -f docker-compose-v42.yml up -d

# Verify services
docker-compose ps
```

### Step 2.2: Configure Dual Routing

**Run BOTH v4.1 and v4.2 in parallel.**

```yaml
# nginx.conf
upstream tbp_v41 {
    server tbp-opa-v41:8181;
}

upstream tbp_v42 {
    server tbp-opa-v42:8181;
}

server {
    location /v1/data/tbp {
        # Route 10% to v4.2 (canary)
        split_clients "${remote_addr}${http_user_agent}" $backend {
            10%     "tbp_v42";
            *       "tbp_v41";
        }
        
        proxy_pass http://$backend;
    }
}
```

**Start with 10% traffic to v4.2.**

### Step 2.3: Migrate Audit Logs

```bash
# Use migration helper
python3 -m integrations.backward_v4.1 migrate \
    --input /var/tbp/v41_logs/ \
    --output /var/tbp/v42_logs/ \
    --verify

# This will:
# 1. Read all v4.1 logs
# 2. Verify v4.1 signatures
# 3. Convert to v4.2 format
# 4. Build Merkle chain
# 5. Sign with HSM
# 6. Verify integrity

# Check migration report
cat /var/tbp/migration_report.md
```

**Expected time:** 1000 logs/second (depends on hardware)

---

## Phase 3: Validation (Day 4-7)

### Step 3.1: Compare Outputs

**Run same request through both versions:**

```bash
# Test request
REQUEST='{"input": {"domain": "finance", "operation": "trade", "transaction_value": 50000}}'

# Query v4.1
V41_RESULT=$(curl -s http://tbp-v41:8181/v1/data/tbp/core/v4/allow -d "$REQUEST")

# Query v4.2
V42_RESULT=$(curl -s http://tbp-v42:8181/v1/data/tbp/core/v4/allow -d "$REQUEST")

# Compare
if [ "$V41_RESULT" == "$V42_RESULT" ]; then
    echo "✅ Results match"
else
    echo "❌ MISMATCH - Investigate!"
    diff <(echo "$V41_RESULT") <(echo "$V42_RESULT")
fi
```

**Run this for 1000+ real requests over 3-7 days.**

### Step 3.2: Monitor Metrics

```bash
# Key metrics to watch
watch -n 5 'kubectl top pods -n tbp-system-v42'

# Decision latency (should be < 10ms)
# Memory usage (should be < 256MB)
# CPU usage (should be < 0.5 core)
# Error rate (should be 0%)
```

**Set up alerts:**

```yaml
# Grafana alert
- alert: TBPv42HighLatency
  expr: tbp_decision_latency_ms{version="v42"} > 50
  for: 5m
  annotations:
    summary: "v4.2 latency above 50ms"
```

### Step 3.3: Verify Merkle Chain

```python
# Verify Merkle chain integrity
from core.merkle_audit import MerkleAuditChain

chain = MerkleAuditChain()
chain.load("/var/tbp/v42_logs/merkle_chain.json")

if chain.verify_integrity():
    print("✅ Merkle chain intact")
else:
    print("❌ CHAIN BROKEN - Investigate!")
```

**Run daily during validation period.**

---

## Phase 4: Switchover (Day 8)

### Step 4.1: Gradual Traffic Increase

```bash
# Day 8: 25% to v4.2
# Day 9: 50% to v4.2
# Day 10: 75% to v4.2
# Day 11: 100% to v4.2

# Update nginx config each day
# Example for 50%:
split_clients "${remote_addr}${http_user_agent}" $backend {
    50%     "tbp_v42";
    *       "tbp_v41";
}

# Reload nginx
nginx -s reload
```

**Monitor closely during each increase.**

### Step 4.2: Full Switchover

```bash
# Day 11: Route 100% to v4.2
split_clients "${remote_addr}${http_user_agent}" $backend {
    100%    "tbp_v42";
}

# Or simply:
location /v1/data/tbp {
    proxy_pass http://tbp-v42:8181;
}

# Reload
nginx -s reload

# Verify
curl http://your-server/v1/data/tbp/health
# Should return v4.2 version
```

### Step 4.3: Update Client Configurations

```bash
# Update all agents to point to v4.2
# (Only if using direct connection, not recommended)

# LangChain integration
pip install --upgrade tbp-enforcer

# Update environment variable
export TBP_VERSION=v4.2
```

---

## Phase 5: Cleanup (Day 30+)

### Step 5.1: Monitor for 30 Days

**Watch for:**
- Unexpected errors
- Performance degradation
- Client complaints

**If ANY issues → Rollback (see below)**

### Step 5.2: Deprecate v4.1

```bash
# After 30 days of stable v4.2

# Stop v4.1 services
kubectl scale deployment tbp-opa-v41 --replicas=0 -n tbp-system

# Keep for 7 more days (in case rollback needed)

# Day 37: Delete v4.1
kubectl delete namespace tbp-system
# (v4.1 was in tbp-system, v4.2 is in tbp-system-v42)

# Rename v4.2 namespace to standard
kubectl create namespace tbp-system
kubectl get all -n tbp-system-v42 -o yaml | \
    sed 's/tbp-system-v42/tbp-system/g' | \
    kubectl apply -f -
kubectl delete namespace tbp-system-v42
```

### Step 5.3: Archive v4.1 Logs

```bash
# Move v4.1 logs to cold storage
tar -czf v41_logs_archive.tar.gz /var/tbp/v41_logs/
aws s3 cp v41_logs_archive.tar.gz s3://tbp-archives/v41/

# Keep local copy for 90 days (compliance)
mv v41_logs_archive.tar.gz /archive/tbp/

# Delete after 90 days (set reminder)
```

---

## 🚨 Rollback Procedure

**If issues detected during migration:**

### Quick Rollback (< 5 min)

```bash
# Revert nginx to 100% v4.1
location /v1/data/tbp {
    proxy_pass http://tbp-v41:8181;
}
nginx -s reload

# Verify
curl http://your-server/v1/data/tbp/health
# Should return v4.1
```

### Full Rollback (< 30 min)

```bash
# Stop v4.2
kubectl scale deployment --all --replicas=0 -n tbp-system-v42

# Restore v4.1 from backup (if needed)
kubectl apply -f tbp-policies-backup.yaml

# Verify v4.1 working
curl http://tbp-v41:8181/v1/data/tbp/health

# Restore audit logs (if needed)
tar -xzf audit_logs_backup_*.tar.gz -C /var/tbp/logs/
```

---

## 📊 Success Criteria

**Migration successful if:**

✅ All v4.1 functionality still works  
✅ v4.2 latency < 10ms (same as v4.1)  
✅ Zero data loss (all logs migrated)  
✅ Merkle chain integrity verified  
✅ HSM signing operational  
✅ No production incidents  
✅ Zero rollbacks needed  

---

## 🐛 Troubleshooting

### Issue: HSM Not Found

**Symptom:**
```
ERROR: HSM connection failed
```

**Solution:**
```bash
# Check HSM device
lsusb  # Should show YubiKey or similar

# Check PKCS#11 library
ls -la /usr/lib/libpkcs11.so

# Fallback to software mode (development only)
export TBP_HSM_MODE=software
```

### Issue: Merkle Chain Broken

**Symptom:**
```
ERROR: Chain integrity verification failed at entry #500
```

**Solution:**
```bash
# Identify broken entry
python3 -c "
from core.merkle_audit import MerkleAuditChain
chain = MerkleAuditChain()
chain.load('merkle_chain.json')
chain.verify_integrity()  # Will print which entry failed
"

# Rebuild from v4.1 logs
python3 -m integrations.backward_v4.1 migrate --rebuild
```

### Issue: High Latency

**Symptom:**
```
TBP decision latency: 50ms (expected < 10ms)
```

**Solution:**
```bash
# Check network latency
ping tbp-opa-v42

# Check resource usage
kubectl top pod tbp-opa-v42

# Scale horizontally
kubectl scale deployment tbp-opa-v42 --replicas=3

# Check HSM performance
# (HSM signing slower than software, expected 2-5ms)
```

### Issue: Signature Verification Fails

**Symptom:**
```
ERROR: Invalid signature on log entry
```

**Solution:**
```bash
# Verify public key matches
diff /secure/backup/tbp_public_key.pem /current/tbp_public_key.pem

# Check HSM key ID
python3 -c "
from core.hsm_signer import HSMSigner
signer = HSMSigner()
print(signer.get_public_key())
"

# Regenerate keys if needed (LAST RESORT)
# This invalidates ALL previous signatures!
```

---

## 📝 Post-Migration Report Template

```markdown
# TBP v4.1 → v4.2 Migration Report

**Date:** YYYY-MM-DD  
**Performed by:** [Your name]  
**Environment:** [Production/Staging]

## Summary
- **Start:** [Date/time]
- **End:** [Date/time]
- **Duration:** [Hours]
- **Downtime:** [Minutes (should be 0)]

## Metrics
- **Logs migrated:** [Count]
- **Migration speed:** [logs/sec]
- **Errors:** [Count (should be 0)]
- **Rollbacks:** [Count (should be 0)]

## Validation
- [ ] All v4.1 tests pass with v4.2
- [ ] Merkle chain integrity verified
- [ ] HSM operational
- [ ] Latency < 10ms
- [ ] 30-day monitoring complete

## Issues Encountered
[List any issues and how resolved]

## Recommendations
[Any improvements for next migration]

## Sign-off
- DevOps: [Name] ✅
- Security: [Name] ✅
- Management: [Name] ✅
```

---

## 🎓 Training for Team

**Before migration, ensure team knows:**

1. **v4.2 architecture** (read ARCHITECTURE_DECISIONS.md)
2. **Rollback procedure** (practice in staging)
3. **Monitoring dashboards** (set up alerts)
4. **Troubleshooting** (common issues above)
5. **On-call schedule** (migration week coverage)

**Dry run recommended:** Practice entire migration in staging first.

---

## 📞 Support

**During migration, if stuck:**

1. **Check troubleshooting section above**
2. **GitHub Discussions:** Search for similar issues
3. **Emergency rollback:** Use procedure above
4. **Post-migration:** Open GitHub Issue with migration report

---

## ✅ Final Checklist

**Before marking migration complete:**

- [ ] v4.2 handling 100% of traffic for 30+ days
- [ ] Zero production incidents
- [ ] Monitoring confirms performance meets SLA
- [ ] Team trained on v4.2 operations
- [ ] v4.1 safely archived
- [ ] Migration report documented
- [ ] Lessons learned captured for next time

**Only then: Migration officially complete! 🎉**

---

**Document Version:** 1.0  
**Last Updated:** February 8, 2026  
**Next Review:** After first production migration
