# TBP Kubernetes Deployment

Production-ready Kubernetes manifests for deploying the Teleological Bounding Protocol (TBP) policy engine.

## Overview

This deployment provides:

- **Namespace isolation**: Dedicated `tbp-system` namespace
- **Network security**: Default deny-all NetworkPolicies with explicit allow rules
- **Resource management**: ResourceQuotas and LimitRanges to prevent OOM kills
- **High availability**: 2 OPA replicas with PodDisruptionBudget
- **Security hardening**: Non-root containers, read-only filesystem, dropped capabilities

## Prerequisites

- Kubernetes 1.21+ cluster
- `kubectl` configured to access your cluster
- A CNI plugin that supports NetworkPolicies (Calico, Cilium, Weave Net, etc.)

## Quick Start with kind

[kind](https://kind.sigs.k8s.io/) is a tool for running local Kubernetes clusters using Docker.

### 1. Install kind

```bash
# Windows (PowerShell)
choco install kind

# macOS
brew install kind

# Linux
curl -Lo ./kind https://kind.sigs.k8s.io/releases/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

### 2. Create a cluster with NetworkPolicy support

```bash
# Create a kind cluster with Calico CNI for NetworkPolicy support
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
networking:
  disableDefaultCNI: true
  podSubnet: 192.168.0.0/16
EOF

# Install Calico CNI
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.1/manifests/calico.yaml

# Wait for Calico to be ready
kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=300s
```

### 3. Deploy TBP

```bash
# Navigate to the kubernetes directory
cd tbp-v4-hard-shield/deployment/kubernetes

# Apply all manifests in order
kubectl apply -f namespace.yaml
kubectl apply -f resourcequota.yaml
kubectl apply -f limitrange.yaml
kubectl apply -f configmap-policies.yaml
kubectl apply -f deployment-opa.yaml
kubectl apply -f service-opa.yaml
kubectl apply -f networkpolicy-deny-all.yaml
kubectl apply -f networkpolicy-allow-opa.yaml

# Or apply all at once
kubectl apply -f .
```

### 4. Verify deployment

```bash
# Check namespace
kubectl get namespace tbp-system

# Check pods
kubectl get pods -n tbp-system

# Check services
kubectl get svc -n tbp-system

# Check resource quota
kubectl describe resourcequota -n tbp-system

# Check OPA health
kubectl port-forward -n tbp-system svc/opa 8181:8181 &
curl http://localhost:8181/health
```

## Quick Start with minikube

[minikube](https://minikube.sigs.k8s.io/) is another popular local Kubernetes tool.

### 1. Install minikube

```bash
# Windows (PowerShell)
choco install minikube

# macOS
brew install minikube

# Linux
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

### 2. Start minikube with CNI

```bash
# Start minikube with Calico CNI for NetworkPolicy support
minikube start --cni=calico --memory=4096 --cpus=2

# Wait for cluster to be ready
minikube status
```

### 3. Deploy TBP

```bash
# Navigate to the kubernetes directory
cd tbp-v4-hard-shield/deployment/kubernetes

# Apply all manifests
kubectl apply -f .
```

### 4. Verify deployment

```bash
# Check pods are running
kubectl get pods -n tbp-system -w

# Once pods are ready, test OPA
minikube service opa -n tbp-system --url
# or
kubectl port-forward -n tbp-system svc/opa 8181:8181
```

## Testing the Deployment

### Run OPA Policy Tests

```bash
# Execute tests inside the OPA pod
kubectl exec -n tbp-system deployment/opa -- opa test /policies -v

# Expected output: 40/40 tests pass
```

### Test Policy Enforcement

```bash
# Port-forward to access OPA
kubectl port-forward -n tbp-system svc/opa 8181:8181 &

# Test F-STABILITY: Block large transaction without approval
curl -X POST http://localhost:8181/v1/data/tbp/core/v4/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "domain": "finance",
      "operation": "transfer",
      "transaction_value": 2000000,
      "human_approved": false,
      "agent_id": "test-001"
    }
  }'
# Expected: {"result": false}

# Test F-STABILITY: Allow small transaction
curl -X POST http://localhost:8181/v1/data/tbp/core/v4/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "domain": "finance",
      "operation": "transfer",
      "transaction_value": 5000,
      "agent_id": "test-001"
    }
  }'
# Expected: {"result": true}

# Test I-INTEGRITY: Block kernel access
curl -X POST http://localhost:8181/v1/data/tbp/core/v4/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "domain": "system",
      "operation": "read",
      "path_category": "kernel_config",
      "agent_id": "test-001"
    }
  }'
# Expected: {"result": false}

# Test W-MONOPOLY: Block weapons domain
curl -X POST http://localhost:8181/v1/data/tbp/core/v4/allow \
  -H 'Content-Type: application/json' \
  -d '{
    "input": {
      "domain": "weapons",
      "operation": "control",
      "agent_id": "test-001"
    }
  }'
# Expected: {"result": false}
```

### Test NetworkPolicy Enforcement

```bash
# Create a test pod WITHOUT the tbp-client label
kubectl run test-unauthorized --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s --connect-timeout 5 http://opa.tbp-system:8181/health
# Expected: Connection timeout (blocked by NetworkPolicy)

# Create a test pod WITH the tbp-client label
kubectl run test-authorized --image=curlimages/curl --rm -it --restart=Never \
  --labels="tbp-client=true" -- \
  curl -s http://opa.tbp-system:8181/health
# Expected: {"} (health check response)
```

## Integrating Your Application

To allow your application pods to access TBP/OPA, add the `tbp-client: "true"` label:

### Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-ai-agent
spec:
  template:
    metadata:
      labels:
        app: my-ai-agent
        tbp-client: "true"  # Required to access OPA
    spec:
      containers:
        - name: agent
          image: my-agent:latest
          env:
            - name: OPA_URL
              value: "http://opa.tbp-system:8181"
```

### Python Client Example

```python
import requests

OPA_URL = "http://opa.tbp-system:8181"

def check_tbp_policy(domain, operation, **context):
    """Check if action is allowed by TBP policy."""
    response = requests.post(
        f"{OPA_URL}/v1/data/tbp/core/v4/allow",
        json={
            "input": {
                "domain": domain,
                "operation": operation,
                "agent_id": "my-agent",
                **context
            }
        }
    )
    return response.json().get("result", False)

# Usage
if check_tbp_policy("finance", "transfer", transaction_value=5000):
    # Execute the transfer
    pass
else:
    # Action blocked by TBP
    raise Exception("Action blocked by TBP policy")
```

## File Structure

```
kubernetes/
├── namespace.yaml              # tbp-system namespace
├── configmap-policies.yaml     # OPA policies (tbp_core.rego)
├── resourcequota.yaml          # Namespace resource limits
├── limitrange.yaml             # Container resource defaults
├── deployment-opa.yaml         # OPA deployment + PDB
├── service-opa.yaml            # OPA ClusterIP service
├── networkpolicy-deny-all.yaml # Default deny policies
├── networkpolicy-allow-opa.yaml# Allow rules for OPA access
└── README.md                   # This file
```

## Security Features

| Feature | Implementation |
|---------|----------------|
| Namespace isolation | Dedicated `tbp-system` namespace |
| Network isolation | Default deny-all NetworkPolicy |
| Authorized access only | `tbp-client: "true"` label required |
| No OOM kills | LimitRange + ResourceQuota |
| Immutable policies | ConfigMap mounted read-only |
| Non-root execution | SecurityContext: runAsNonRoot |
| Read-only filesystem | SecurityContext: readOnlyRootFilesystem |
| Minimal privileges | Capabilities: drop ALL |
| High availability | 2 replicas + PodDisruptionBudget |

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl describe pod -n tbp-system -l app.kubernetes.io/name=opa

# Check events
kubectl get events -n tbp-system --sort-by='.lastTimestamp'

# Common issues:
# - ResourceQuota exceeded: increase quota or reduce replicas
# - Image pull error: check image name and registry access
# - SecurityContext issues: ensure PSP/PSA allows the security settings
```

### NetworkPolicy blocking legitimate traffic

```bash
# Verify your pod has the tbp-client label
kubectl get pod <pod-name> -o jsonpath='{.metadata.labels}'

# Check NetworkPolicy is applied
kubectl get networkpolicy -n tbp-system

# Test connectivity from within the cluster
kubectl run debug --image=nicolaka/netshoot --rm -it -- \
  nslookup opa.tbp-system
```

### OPA not loading policies

```bash
# Check ConfigMap is mounted
kubectl exec -n tbp-system deployment/opa -- ls -la /policies

# Check OPA logs
kubectl logs -n tbp-system deployment/opa

# Verify policy syntax
kubectl exec -n tbp-system deployment/opa -- opa check /policies
```

### Resource limits causing restarts

```bash
# Check if OOM killed
kubectl describe pod -n tbp-system -l app.kubernetes.io/name=opa | grep -A5 "Last State"

# Check resource usage
kubectl top pod -n tbp-system

# Increase limits if needed by editing deployment-opa.yaml
```

## Cleanup

```bash
# Delete all TBP resources
kubectl delete -f .

# Or delete the namespace (removes everything)
kubectl delete namespace tbp-system
```

## Production Considerations

1. **Use specific image tags**: Replace `openpolicyagent/opa:latest` with a specific version
2. **Configure resource limits**: Adjust based on actual workload
3. **Enable audit logging**: Configure OPA decision logs
4. **Set up monitoring**: Add Prometheus ServiceMonitor for metrics
5. **Configure RBAC**: Create dedicated ServiceAccount with minimal permissions
6. **Use Secrets**: Store HMAC keys in Kubernetes Secrets, not ConfigMaps
7. **Enable TLS**: Configure OPA to use HTTPS for production

## Related Documentation

- [TBP Main README](../../../README.md)
- [TBP V4 Hard-Shield](../../README.md)
- [OPA Documentation](https://www.openpolicyagent.org/docs/latest/)
- [Kubernetes NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
