# Pattern Analysis + OPA Integration Guide

## Overview

The Pattern Analyzer enriches OPA policy evaluation with temporal behavioral metrics. This enables detection of **salami attacks** and other cumulative violations that individual policies cannot catch.

---

## Architecture

```
┌─────────────────┐
│  Agent Request  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ Pattern Analyzer    │  ◄── Analyzes history
│ (pattern_analysis)  │
└─────────┬───────────┘
          │
          │ Enriched Context
          ▼
┌─────────────────────┐
│  OPA Policy Server  │  ◄── Makes decision
│  (tbp_core.rego)    │
└─────────┬───────────┘
          │
          │ Allow/Deny + Log
          ▼
┌─────────────────────┐
│  Audit System       │
│  (Merkle Chain)     │
└─────────────────────┘
```

**Flow:**
1. Agent request arrives
2. **Pattern Analyzer** computes metrics (cumulative amounts, frequency, risk score)
3. Metrics added to OPA input context
4. **OPA policies** evaluate using both:
   - Static rules (transaction limits)
   - Dynamic metrics (cumulative patterns)
5. Decision logged with pattern context

---

## OPA Policy Extension

### Add Pattern Metrics to Input

**Before (v4.0):**
```rego
package tbp.finance

# Simple threshold check
deny[msg] if {
    input.transaction_value > 1000000
    msg := "Transaction exceeds limit"
}
```

**After (v4.2.1 with Pattern Analysis):**
```rego
package tbp.finance

import data.tbp.patterns

# Check BOTH static limit AND cumulative pattern
deny[msg] if {
    # Individual transaction limit
    input.transaction_value > 1000000
    msg := "Transaction exceeds limit"
}

deny[msg] if {
    # Cumulative 24h limit (salami attack detection)
    input.pattern_metrics.cumulative_24h.amount > 100000
    msg := sprintf(
        "Cumulative 24h amount $%.2f exceeds threshold. Possible salami attack.",
        [input.pattern_metrics.cumulative_24h.amount]
    )
}

deny[msg] if {
    # High risk score
    input.pattern_metrics.risk_score > 80
    msg := sprintf(
        "High risk score %.1f detected. Pattern analysis flagged behavior.",
        [input.pattern_metrics.risk_score]
    )
}

deny[msg] if {
    # Burst detection
    input.pattern_metrics.frequency.burst == true
    msg := "Burst of rapid transactions detected. Rate limiting triggered."
}

deny[msg] if {
    # Sequential similarity (repetitive pattern)
    input.pattern_metrics.sequential.similar_count > 10
    msg := sprintf(
        "%d consecutive similar actions detected. Possible automation attack.",
        [input.pattern_metrics.sequential.similar_count]
    )
}
```

---

## Python Integration

### Option 1: Middleware Pattern

```python
from pattern_analysis import PatternAnalyzer
import requests

class TBPEnforcer:
    """
    TBP enforcer with pattern analysis.
    
    Wraps OPA calls with pattern enrichment.
    """
    
    def __init__(self, opa_url: str, pattern_storage: str = "patterns.json"):
        self.opa_url = opa_url
        self.analyzer = PatternAnalyzer(
            storage_path=pattern_storage,
            auto_save=True
        )
    
    def check_action(self, action: dict) -> dict:
        """
        Check if action is allowed.
        
        Args:
            action: {
                "agent_id": str,
                "action_type": str,
                "amount": float,
                ...
            }
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "pattern_metrics": dict
            }
        """
        # 1. Compute pattern metrics
        metrics = self.analyzer.analyze(action)
        
        # 2. Enrich OPA input
        opa_input = {
            **action,
            "pattern_metrics": metrics.to_dict()
        }
        
        # 3. Query OPA
        response = requests.post(
            f"{self.opa_url}/v1/data/tbp/allow",
            json={"input": opa_input}
        )
        
        result = response.json()
        
        return {
            "allowed": result.get("result", False),
            "reason": result.get("reason", ""),
            "pattern_metrics": metrics.to_dict()
        }


# Usage
enforcer = TBPEnforcer(opa_url="http://localhost:8181")

action = {
    "agent_id": "trading-bot-001",
    "action_type": "transfer",
    "amount": 9999.0,
    "to": "account-xyz"
}

result = enforcer.check_action(action)

if not result["allowed"]:
    print(f"❌ Action blocked: {result['reason']}")
    print(f"   Risk score: {result['pattern_metrics']['risk_score']}")
else:
    print("✅ Action allowed")
```

---

### Option 2: Decorator Pattern

```python
from functools import wraps
from pattern_analysis import PatternAnalyzer

# Global analyzer
_analyzer = PatternAnalyzer(storage_path="patterns.json")

def enforce_tbp(func):
    """
    Decorator to enforce TBP on agent methods.
    
    Usage:
        class TradingAgent:
            @enforce_tbp
            def execute_trade(self, amount: float):
                # ... actual trade logic
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Extract agent_id and action
        agent_id = getattr(self, 'agent_id', 'unknown')
        action_type = func.__name__
        
        # Build action context
        action = {
            "agent_id": agent_id,
            "action_type": action_type,
            "amount": kwargs.get('amount', 0.0)
        }
        
        # Analyze pattern
        metrics = _analyzer.analyze(action)
        
        # Check risk
        if metrics.risk_score > 80:
            raise PermissionError(
                f"TBP blocked {action_type}: "
                f"risk_score={metrics.risk_score:.1f}"
            )
        
        if metrics.cumulative_amount_24h > 100000:
            raise PermissionError(
                f"TBP blocked {action_type}: "
                f"cumulative_24h=${metrics.cumulative_amount_24h:.2f}"
            )
        
        # Execute if allowed
        return func(self, *args, **kwargs)
    
    return wrapper


# Usage
class TradingAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
    
    @enforce_tbp
    def execute_trade(self, amount: float):
        print(f"Executing trade: ${amount}")
        # ... actual trade logic


agent = TradingAgent("bot-001")

try:
    # This will be checked by pattern analyzer
    agent.execute_trade(amount=50000)
except PermissionError as e:
    print(f"❌ Trade blocked: {e}")
```

---

### Option 3: FastAPI Integration

```python
from fastapi import FastAPI, HTTPException, Depends
from pattern_analysis import PatternAnalyzer
from pydantic import BaseModel

app = FastAPI()

# Global analyzer
analyzer = PatternAnalyzer(storage_path="patterns.json")


class TradeRequest(BaseModel):
    agent_id: str
    action_type: str
    amount: float
    to_account: str


@app.post("/api/trade")
async def execute_trade(request: TradeRequest):
    """
    Execute trade with TBP enforcement.
    """
    # Analyze pattern
    action = request.dict()
    metrics = analyzer.analyze(action)
    
    # Check thresholds
    if metrics.risk_score > 80:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "TBP_BLOCKED",
                "reason": f"High risk score: {metrics.risk_score:.1f}",
                "metrics": metrics.to_dict()
            }
        )
    
    if metrics.cumulative_amount_24h > 100000:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "TBP_BLOCKED",
                "reason": f"Cumulative 24h limit exceeded: ${metrics.cumulative_amount_24h:.2f}",
                "metrics": metrics.to_dict()
            }
        )
    
    # Execute trade (actual logic here)
    return {
        "success": True,
        "transaction_id": "txn-123",
        "metrics": metrics.to_dict()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Testing Integration

### Test: Pattern Enrichment Works

```python
import pytest
from pattern_analysis import PatternAnalyzer
import requests_mock

def test_pattern_enrichment():
    """Test that pattern metrics are added to OPA input"""
    analyzer = PatternAnalyzer()
    
    # Simulate action
    action = {
        "agent_id": "bot-001",
        "action_type": "transfer",
        "amount": 50000
    }
    
    # Compute metrics
    metrics = analyzer.analyze(action)
    
    # Build OPA input
    opa_input = {
        **action,
        "pattern_metrics": metrics.to_dict()
    }
    
    # Verify structure
    assert "pattern_metrics" in opa_input
    assert "cumulative_24h" in opa_input["pattern_metrics"]
    assert "risk_score" in opa_input["pattern_metrics"]


def test_salami_attack_blocked():
    """Test that salami attack is blocked via pattern analysis"""
    analyzer = PatternAnalyzer()
    
    # Simulate 100 small transactions
    for i in range(100):
        action = {
            "agent_id": "salami-bot",
            "action_type": "transfer",
            "amount": 9999
        }
        metrics = analyzer.analyze(action)
    
    # Final metrics should flag attack
    assert metrics.cumulative_amount_24h > 100000  # Over threshold
    assert metrics.risk_score > 50  # High risk
    
    # OPA policy would block this based on:
    # - cumulative_amount_24h > 100000
    # - risk_score > 80
```

---

## OPA Test Cases

Add these tests to `tbp_core_test.rego`:

```rego
# Test: Pattern metrics block cumulative violations
test_pattern_cumulative_blocks if {
    not allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 5000,  # Individual OK
        "pattern_metrics": {
            "cumulative_24h": {
                "amount": 150000  # Cumulative NOT OK
            }
        }
    }
}

# Test: High risk score blocks action
test_pattern_risk_score_blocks if {
    not allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 5000,
        "pattern_metrics": {
            "risk_score": 85  # High risk
        }
    }
}

# Test: Burst detection blocks
test_pattern_burst_blocks if {
    not allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 1000,
        "pattern_metrics": {
            "frequency": {
                "burst": true  # Burst detected
            }
        }
    }
}

# Test: Normal patterns allow
test_pattern_normal_allows if {
    allow with input as {
        "domain": "finance",
        "operation": "transfer",
        "transaction_value": 5000,
        "pattern_metrics": {
            "cumulative_24h": {
                "amount": 20000  # Under threshold
            },
            "risk_score": 15  # Low risk
        }
    }
}
```

---

## Deployment Checklist

- [ ] Install pattern_analysis.py in core/
- [ ] Update OPA policies to use pattern_metrics
- [ ] Add pattern tests to test suite
- [ ] Configure storage path (patterns.json)
- [ ] Set thresholds in config
- [ ] Monitor pattern analyzer performance
- [ ] Set up alerts for high risk scores

---

## Performance Considerations

**Pattern Analyzer Performance:**
- Analysis: ~1-2ms per action
- Storage save: ~10ms (if auto_save=True)
- Memory: ~1MB per 1000 events

**Optimization Tips:**
1. Disable auto_save for high-frequency systems
2. Batch save every N events or M seconds
3. Use separate storage per agent for parallelism
4. Prune old data periodically (> 7 days)

---

## Monitoring

### Key Metrics to Track

```python
# Add to Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

pattern_analysis_duration = Histogram(
    'tbp_pattern_analysis_duration_seconds',
    'Time to analyze pattern'
)

pattern_risk_score = Gauge(
    'tbp_pattern_risk_score',
    'Current risk score',
    ['agent_id']
)

pattern_blocks = Counter(
    'tbp_pattern_blocks_total',
    'Actions blocked by pattern analysis',
    ['reason']
)


# Usage
with pattern_analysis_duration.time():
    metrics = analyzer.analyze(action)

pattern_risk_score.labels(agent_id=action['agent_id']).set(metrics.risk_score)

if metrics.risk_score > 80:
    pattern_blocks.labels(reason='high_risk').inc()
```

---

## Troubleshooting

**Q: Pattern analyzer not detecting salami attacks?**
A: Check thresholds in analyzer initialization. Default is $100k/24h.

**Q: High memory usage?**
A: Prune old events or reduce window size.

**Q: Slow analysis?**
A: Disable auto_save and batch saves.

**Q: False positives?**
A: Adjust risk score thresholds or customize weights.

---

**Pattern Analysis is now integrated with TBP v4.2.1! 🎯**
