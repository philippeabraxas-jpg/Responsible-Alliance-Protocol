# TBP Reference Implementation Guide

**Version:** 4.0  
**Last Updated:** February 7, 2026  
**Purpose:** Detailed guide for implementing TBP in your AI system

---

## 📖 What is This?

This directory contains **reference implementations** and **integration patterns** for the Teleological Bounding Protocol (TBP).

**Use this guide to:**
- ✅ Understand how to integrate TBP into your AI agent
- ✅ See working examples for popular frameworks
- ✅ Follow best practices for production deployment
- ✅ Avoid common pitfalls

---

## 🎯 Quick Start (5 Minutes)

### Step 1: Choose Your Framework

**Select the integration that matches your stack:**

| Framework | File | Use Case |
|-----------|------|----------|
| **LangChain** | [langchain_integration.py](../tbp-v4-hard-shield/integrations/langchain_integration.py) | LLM chains, agents with tools |
| **AutoGen** | [autogen_integration.py](../tbp-v4-hard-shield/integrations/autogen_integration.py) | Multi-agent conversations |
| **FastAPI** | [fastapi_middleware.py](../tbp-v4-hard-shield/integrations/fastapi_middleware.py) | HTTP API gateway |
| **Custom** | See "Custom Integration" below | Any other framework |

### Step 2: Deploy OPA

**Start Open Policy Agent:**

```bash
cd tbp-v4-hard-shield/deployment
docker-compose up -d opa

# Verify OPA is running
curl http://localhost:8181/health
# Expected: {"status": "ok"}
```

### Step 3: Integrate Your Agent

**Example (LangChain):**

```python
from tbp_enforcer import TBPEnforcer, TBPTradingTool

# Initialize TBP enforcement
enforcer = TBPEnforcer(
    opa_url="http://localhost:8181",
    agent_id="my-trading-bot-001"
)

# Wrap your tools with TBP
trading_tool = TBPTradingTool(enforcer)

# Use in LangChain agent
agent = initialize_agent(
    tools=[trading_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION
)

# Now all trades are TBP-protected!
agent.run("Buy $5000 of AAPL")  # ✅ Allowed
agent.run("Buy $2M of TSLA")    # ❌ Blocked by F-STABILITY
```

**That's it! Your agent is now TBP-protected.**

---

## 🏗️ Architecture Overview

### How TBP Works

```
┌─────────────────────────────────────────────────────────┐
│                    Your AI Agent                         │
│  (LangChain, AutoGen, Custom, etc.)                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ 1. Action Request
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 TBP Enforcer                             │
│  (Python/JS wrapper in your code)                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ 2. Query (JSON)
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 OPA Server                               │
│  (Open Policy Agent running tbp_core.rego)              │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ 3. Decision (allow/deny)
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Action Execution                         │
│  (If allowed) OR (Categorical refusal if blocked)       │
└─────────────────────────────────────────────────────────┘
                     │
                     │ 4. Audit Log (dual signatures)
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Audit Database                           │
│  (PostgreSQL, Elasticsearch, etc.)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 Integration Patterns

### Pattern 1: Tool Wrapping (LangChain)

**Best for:** Existing LangChain agents

**How it works:**
- Wrap each tool with `TBPTool` class
- TBP enforcer checks action before execution
- Tool execution blocked if policy denies

**Example:**

```python
from langchain.tools import BaseTool
from tbp_enforcer import TBPEnforcer

class TBPTradingTool(BaseTool):
    name = "trade_executor"
    description = "Execute stock trades"
    
    def __init__(self, enforcer: TBPEnforcer):
        super().__init__()
        self.enforcer = enforcer
    
    def _run(self, query: str, **kwargs) -> str:
        # Extract parameters
        symbol = kwargs.get("symbol")
        amount = kwargs.get("amount")
        
        # Check with TBP
        decision = self.enforcer.check_action(
            domain="finance",
            operation="trade",
            transaction_value=amount,
            symbol=symbol
        )
        
        if not decision["allowed"]:
            return f"❌ Trade blocked by TBP: {decision['reason']}"
        
        # Execute trade
        result = self._execute_trade(symbol, amount)
        return f"✅ Trade executed: {result}"
```

**Pros:**
- ✅ Minimal code changes
- ✅ Works with existing agents
- ✅ Tool-level granularity

**Cons:**
- ⚠️ Must wrap each tool manually
- ⚠️ Agent could use unwrapped tools if available

---

### Pattern 2: Agent Subclassing (AutoGen)

**Best for:** Multi-agent systems

**How it works:**
- Subclass framework's agent class
- Override function registration
- Inject TBP checks automatically

**Example:**

```python
from autogen import ConversableAgent
from tbp_enforcer import TBPEnforcer

class TBPConversableAgent(ConversableAgent):
    def __init__(self, name, enforcer, domain="general", **kwargs):
        super().__init__(name=name, **kwargs)
        self.enforcer = enforcer
        self.default_domain = domain
    
    def register_function(self, function_map, domain=None):
        # Wrap all functions with TBP
        wrapped = {}
        for name, func in function_map.items():
            wrapped[name] = self._wrap_function(func, domain or self.default_domain)
        
        super().register_function(function_map=wrapped)
    
    def _wrap_function(self, func, domain):
        def wrapped(*args, **kwargs):
            # Check TBP before execution
            decision = self.enforcer.check_action(
                domain=domain,
                operation="execute",
                function_name=func.__name__
            )
            
            if not decision["allowed"]:
                return {"error": "TBP_BLOCKED", "reason": decision["reason"]}
            
            return func(*args, **kwargs)
        
        return wrapped
```

**Pros:**
- ✅ All functions protected automatically
- ✅ Clean separation of concerns
- ✅ Hard to bypass

**Cons:**
- ⚠️ Framework-specific
- ⚠️ Requires understanding agent internals

---

### Pattern 3: Middleware (FastAPI)

**Best for:** HTTP API gateways

**How it works:**
- Middleware intercepts all requests
- Extracts action parameters
- Checks with TBP before routing

**Example:**

```python
from fastapi import FastAPI, Request
from tbp_enforcer import TBPEnforcer

app = FastAPI()
enforcer = TBPEnforcer(opa_url="http://localhost:8181")

@app.middleware("http")
async def tbp_middleware(request: Request, call_next):
    # Extract action from request
    path = request.url.path
    method = request.method
    body = await request.json() if request.method == "POST" else {}
    
    # Determine domain and operation
    domain, operation = extract_action(path, method, body)
    
    # Check with TBP
    decision = enforcer.check_action(
        domain=domain,
        operation=operation,
        **body
    )
    
    if not decision["allowed"]:
        return JSONResponse(
            status_code=403,
            content={"error": "TBP blocked", "reason": decision["reason"]}
        )
    
    # Proceed with request
    response = await call_next(request)
    return response
```

**Pros:**
- ✅ Single enforcement point
- ✅ Works for all endpoints
- ✅ Easy to add/remove

**Cons:**
- ⚠️ Requires careful action extraction
- ⚠️ Can't inspect internal function calls

---

### Pattern 4: Decorator (Python Functions)

**Best for:** Simple function protection

**How it works:**
- Decorator wraps individual functions
- TBP check before function executes
- Clean and Pythonic

**Example:**

```python
from functools import wraps
from tbp_enforcer import TBPEnforcer

enforcer = TBPEnforcer(opa_url="http://localhost:8181")

def tbp_protect(domain, operation):
    """Decorator to protect function with TBP"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check with TBP
            decision = enforcer.check_action(
                domain=domain,
                operation=operation,
                function_name=func.__name__,
                **kwargs
            )
            
            if not decision["allowed"]:
                raise TBPViolation(decision["reason"])
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Use it
@tbp_protect(domain="finance", operation="trade")
def execute_trade(symbol: str, amount: float):
    """Execute a stock trade"""
    # ... actual trading logic
    return {"status": "success", "symbol": symbol, "amount": amount}

# Now this function is TBP-protected
execute_trade("AAPL", 5000)   # ✅ Allowed
execute_trade("TSLA", 2000000)  # ❌ Raises TBPViolation
```

**Pros:**
- ✅ Very simple
- ✅ Clear which functions are protected
- ✅ No framework dependency

**Cons:**
- ⚠️ Must decorate each function
- ⚠️ Easy to forget decorators

---

## 🔧 Custom Integration Guide

**For frameworks not listed above:**

### Step 1: Install Dependencies

```bash
pip install requests  # For OPA communication
pip install cryptography  # For signatures
```

### Step 2: Create TBP Client

```python
import requests
import json

class TBPClient:
    def __init__(self, opa_url="http://localhost:8181", agent_id="custom-agent-001"):
        self.opa_url = opa_url
        self.agent_id = agent_id
    
    def check_action(self, domain, operation, **context):
        """
        Check if action is allowed by TBP
        
        Args:
            domain: "finance", "system", "human_interaction", etc.
            operation: "read", "write", "transfer", etc.
            **context: Additional parameters (transaction_value, path, etc.)
        
        Returns:
            dict: {
                "allowed": bool,
                "reason": str (if denied),
                "invariant": str (F/I/W if triggered)
            }
        """
        # Build input
        input_data = {
            "domain": domain,
            "operation": operation,
            "agent_id": self.agent_id,
            **context
        }
        
        # Query OPA
        response = requests.post(
            f"{self.opa_url}/v1/data/tbp/core/v4/allow",
            json={"input": input_data},
            timeout=5
        )
        
        result = response.json()
        allowed = result.get("result", False)
        
        # Get reason if denied
        reason = None
        if not allowed:
            reason_resp = requests.post(
                f"{self.opa_url}/v1/data/tbp/core/v4/denial_reason",
                json={"input": input_data}
            )
            reason = reason_resp.json().get("result", "Unknown")
        
        return {
            "allowed": allowed,
            "reason": reason,
            "input": input_data
        }
```

### Step 3: Integrate at Critical Points

**Identify where your agent makes impactful decisions:**

```python
class YourAIAgent:
    def __init__(self):
        self.tbp = TBPClient()
    
    def execute_action(self, action_type, **params):
        # Determine domain
        domain = self._get_domain(action_type)
        
        # Check with TBP
        decision = self.tbp.check_action(
            domain=domain,
            operation=action_type,
            **params
        )
        
        if not decision["allowed"]:
            # Categorical refusal
            return {
                "status": "blocked",
                "reason": decision["reason"],
                "message": "This action violates TBP safety bounds"
            }
        
        # Execute action
        return self._do_action(action_type, **params)
```

---

## 🎨 Domain Mapping Guide

**Map your actions to TBP domains:**

### Finance Domain (F-STABILITY)

**Triggers when:**
- Transaction value > $10k (auto-approval threshold)
- Transaction value > $1M (always requires review)
- Market volatility impact > 5%
- Trading frequency > 100 operations/second

**Examples:**
```python
# Trading
check_action(domain="finance", operation="trade", transaction_value=50000)

# Money transfer
check_action(domain="finance", operation="transfer", transaction_value=500000)

# Portfolio rebalancing
check_action(domain="finance", operation="rebalance", volatility_impact=0.03)
```

---

### Infrastructure Domain (I-INTEGRITY)

**Triggers when:**
- Writing to kernel/system paths
- Modifying SCADA/ICS systems
- Network configuration changes
- Critical service restart

**Examples:**
```python
# File system
check_action(domain="system", operation="write", path="/etc/passwd")

# SCADA (always blocked for writes)
check_action(domain="system", operation="write", path="/sys/kernel/config")

# Service restart
check_action(domain="system", operation="restart", service="nginx")
```

---

### Weapons Domain (W-MONOPOLY)

**Triggers when:**
- Integration with weapons systems (always blocked)
- Lethal decision chains
- Coercive manipulation detection

**Examples:**
```python
# Always blocked
check_action(domain="weapons", operation="integrate", system="defense_system")

# Coercion detection
check_action(domain="human_interaction", operation="persuade", coercion_score=0.8)
```

---

## 📊 Testing Your Integration

### Unit Tests

```python
import pytest
from your_agent import YourAIAgent

def test_safe_action_allowed():
    """Test that safe actions are allowed"""
    agent = YourAIAgent()
    result = agent.execute_action("trade", transaction_value=5000)
    assert result["status"] == "success"

def test_dangerous_action_blocked():
    """Test that dangerous actions are blocked"""
    agent = YourAIAgent()
    result = agent.execute_action("trade", transaction_value=2000000)
    assert result["status"] == "blocked"
    assert "TBP" in result["message"]

def test_system_write_blocked():
    """Test that kernel writes are blocked"""
    agent = YourAIAgent()
    result = agent.execute_action("write", path="/sys/kernel/config")
    assert result["status"] == "blocked"
```

### Integration Tests

```bash
# Start OPA
docker-compose up -d opa

# Run your agent tests
pytest tests/test_tbp_integration.py -v

# Expected output:
# test_safe_action_allowed ✅ PASSED
# test_dangerous_action_blocked ✅ PASSED
# test_system_write_blocked ✅ PASSED
```

---

## 🚀 Production Deployment Checklist

**Before going live:**

### Infrastructure
- [ ] OPA deployed on separate, hardened infrastructure
- [ ] Network isolation configured (VPC, firewall)
- [ ] Resource limits set (prevent DoS)
- [ ] High availability setup (multiple OPA replicas)
- [ ] Monitoring and alerting configured

### Security
- [ ] HMAC secret changed from default
- [ ] RSA keys generated (not using examples)
- [ ] Keys stored in HSM or secure vault
- [ ] TLS enabled between agent and OPA
- [ ] Audit logging enabled and tested

### Configuration
- [ ] Thresholds reviewed ($10k, $1M, 100Hz)
- [ ] Domain mappings validated
- [ ] Error handling tested
- [ ] Fallback behavior defined (fail-safe)

### Operational
- [ ] Incident response plan documented
- [ ] On-call rotation established
- [ ] Security update subscription (GitHub watch)
- [ ] Regular security reviews scheduled
- [ ] Staff trained on TBP operations

---

## 📈 Performance Optimization

### Typical Latency

**Expected performance:**
- OPA policy evaluation: < 1ms
- Network round-trip: 1-5ms
- Total overhead: **< 10ms per action**

**If experiencing slowness:**

1. **Check network latency**
   ```bash
   curl -w "@curl-format.txt" -o /dev/null -s http://opa-server:8181/health
   ```

2. **Deploy OPA closer to agent** (same datacenter/VPC)

3. **Use connection pooling**
   ```python
   import requests
   session = requests.Session()  # Reuse connections
   ```

4. **Cache policy decisions** (if actions are identical)
   ```python
   from functools import lru_cache
   
   @lru_cache(maxsize=1000)
   def check_action_cached(domain, operation, **kwargs):
       return tbp.check_action(domain, operation, **kwargs)
   ```

---

## 🐛 Troubleshooting

### Problem: OPA returns 404

**Cause:** Policy not loaded

**Solution:**
```bash
# Verify policy loaded
curl http://localhost:8181/v1/data/tbp/core/v4

# If empty, reload policies
docker-compose restart opa
```

### Problem: All actions blocked

**Cause:** Default deny policy

**Solution:**
```bash
# Check OPA logs
docker-compose logs opa

# Verify input format
curl -X POST http://localhost:8181/v1/data/tbp/core/v4/allow \
  -d '{"input": {"domain": "finance", "operation": "trade", "transaction_value": 1000}}'
```

### Problem: Signatures invalid

**Cause:** Key mismatch or corruption

**Solution:**
```python
# Verify keys
from log_signer import TBPLogSigner
signer = TBPLogSigner()
log = {"test": "data"}
signed = signer.sign_log(log)
assert signer.verify_log(signed)  # Should be True
```

---

## 📚 Further Reading

**Essential docs:**
- [Architecture Overview](../ARCHITECTURE.md) - Understand CORE vs GOVERNANCE
- [Security Model](../SECURITY.md) - Threat model and limitations
- [OPA Policies](../tbp-v4-hard-shield/policies/tbp_core.rego) - Policy source code
- [Cryptographic Audit](../docs/CRYPTOGRAPHIC_AUDIT.md) - Signature details

**Example integrations:**
- [LangChain Integration](../tbp-v4-hard-shield/integrations/langchain_integration.py)
- [AutoGen Integration](../tbp-v4-hard-shield/integrations/autogen_integration.py)
- [FastAPI Middleware](../tbp-v4-hard-shield/integrations/fastapi_middleware.py)

**Community:**
- [GitHub Discussions](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/discussions)
- [Contributing Guide](../CONTRIBUTING.md)

---

## 💬 Questions?

**Need help integrating?**
- Open a GitHub Discussion: "Integration Help: [Your Framework]"
- Check existing issues: Someone may have asked already
- Read the FAQ below

---

## ❓ FAQ

### Q: Can I use TBP with [my framework]?

**A:** Yes! TBP works with any framework that can make HTTP requests. Follow the "Custom Integration" guide above.

### Q: Does TBP slow down my agent?

**A:** Minimal. Typical overhead is < 10ms per action. For most agents, this is negligible.

### Q: What if OPA is down?

**A:** Implement fail-safe behavior. Default recommendation: **Fail closed** (block all actions if TBP unavailable). For non-critical systems, you might fail open with alerts.

### Q: Can I customize the thresholds?

**A:** Yes! Edit `tbp_core.rego` to change $10k, $1M, 100Hz limits. See [INVARIANT_THRESHOLDS.md](../docs/INVARIANT_THRESHOLDS.md) for guidance.

### Q: Do I need both HMAC and RSA signatures?

**A:** HMAC is automatic (OPA). RSA is optional but recommended for external audit capability.

### Q: What about multi-agent systems?

**A:** Each agent gets a unique `agent_id`. All agents share the same OPA server. Logs distinguish which agent did what.

### Q: Can agents bypass TBP?

**A:** Not if implemented correctly. TBP-CORE has zero bypass mechanisms. See [SECURITY.md](../SECURITY.md) for known limitations (e.g., social engineering).

---

## 🎯 Next Steps

**You've integrated TBP! Now:**

1. **Monitor in production** (watch for false positives/negatives)
2. **Tune thresholds** (if default values don't fit your use case)
3. **Enable audit logging** (store logs for compliance)
4. **Consider GOVERNANCE** (if you need emergency bypass capability)
5. **Contribute back** (share your integration pattern!)

---

**Document Version:** 1.0  
**Last Updated:** February 7, 2026  
**Maintainer:** @philippeabraxas-jpg

---

*"The shield before the incident."*
