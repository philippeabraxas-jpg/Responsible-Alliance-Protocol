# TBP Integrations

This directory contains integrations for the Teleological Bounding Protocol (TBP) V4.0 with popular AI agent frameworks.

## Available Integrations

| Framework | File | Status |
|-----------|------|--------|
| Microsoft AutoGen | `autogen_integration.py` | Production Ready |
| LangChain | `langchain_integration.py` | Production Ready |
| FastAPI | `fastapi_middleware.py` | Production Ready |

## Quick Start

### Prerequisites

1. **OPA Server Running**: All integrations require an Open Policy Agent server with TBP policies loaded.

```bash
# Start OPA with TBP policies
cd tbp-v4-hard-shield/deployment
docker-compose up -d
```

2. **Python Dependencies**:

```bash
pip install requests cryptography
```

3. **Framework-Specific Dependencies**:

```bash
# For AutoGen integration
pip install pyautogen

# For LangChain integration
pip install langchain langchain-openai

# For FastAPI integration
pip install fastapi uvicorn
```

---

## AutoGen Integration

### Overview

The AutoGen integration wraps Microsoft AutoGen's `ConversableAgent` with TBP policy enforcement. Every function call made by an AutoGen agent is checked against OPA policies before execution.

### Architecture

```
+-------------------+     +----------------+     +-------------+
|  AutoGen Agent    |---->| TBPEnforcer    |---->| OPA Server  |
|  (Function Call)  |     | (check_action) |     | (Policies)  |
+-------------------+     +----------------+     +-------------+
         |                       |
         |                       v
         |               +----------------+
         |               | Audit Log      |
         |               | (HMAC + RSA)   |
         |               +----------------+
         |
         v
+-------------------+
| Execute Function  |  <-- Only if allowed
| (or return error) |
+-------------------+
```

### Components

#### TBPEnforcementError

Exception raised when TBP policy blocks an action.

```python
from autogen_integration import TBPEnforcementError

try:
    # Action that might be blocked
    result = enforcer.check_action(domain="finance", operation="transfer", amount=5000000)
except TBPEnforcementError as e:
    print(f"Blocked: {e}")
```

#### TBPEnforcer

Communicates with OPA to check if actions are allowed.

```python
from autogen_integration import TBPEnforcer

enforcer = TBPEnforcer(
    opa_url="http://localhost:8181",      # OPA server URL
    policy_path="v1/data/tbp/core/v4",    # Policy path in OPA
    agent_id="my-agent-001"               # Unique agent identifier
)

# Check if action is allowed
result = enforcer.check_action(
    domain="finance",           # TBP domain (finance, system, human_interaction)
    operation="transfer",       # Operation type
    transaction_value=50000,    # Domain-specific context
    human_reviewed=True
)
```

**Parameters for check_action:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `domain` | str | TBP domain: `finance`, `system`, `human_interaction` |
| `operation` | str | Operation type: `read`, `write`, `transfer`, `trade`, etc. |
| `**kwargs` | dict | Domain-specific context passed to OPA |

**Common kwargs by domain:**

| Domain | Common kwargs |
|--------|---------------|
| `finance` | `transaction_value`, `market_impact_score`, `frequency_hz`, `human_reviewed` |
| `system` | `path`, `path_category`, `human_approved` |
| `human_interaction` | `manipulation_score`, `deception_indicators` |

#### TBPConversableAgent

A drop-in replacement for AutoGen's `ConversableAgent` with TBP enforcement.

```python
from autogen_integration import TBPConversableAgent, TBPEnforcer

# Create enforcer
enforcer = TBPEnforcer(opa_url="http://localhost:8181")

# Create TBP-protected agent
agent = TBPConversableAgent(
    name="TradingAgent",
    enforcer=enforcer,
    domain="finance",  # Default domain for this agent
    system_message="You are a trading assistant.",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "YOUR_KEY"}]}
)

# Register functions (automatically wrapped with TBP enforcement)
def execute_trade(symbol: str, amount: float, side: str):
    return {"status": "success", "symbol": symbol, "amount": amount}

agent.register_function(
    function_map={"execute_trade": execute_trade},
    domain="finance",      # Override default domain
    operation="trade"      # Operation type for TBP
)
```

### Usage Examples

#### Example 1: Simple Trading Agent

```python
from autogen_integration import TBPEnforcer, TBPConversableAgent

# Initialize
enforcer = TBPEnforcer(
    opa_url="http://localhost:8181",
    agent_id="trading-bot-001"
)

# Create agent
agent = TBPConversableAgent(
    name="Trader",
    enforcer=enforcer,
    domain="finance",
    system_message="You execute stock trades.",
    llm_config={"config_list": [{"model": "gpt-4", "api_key": "..."}]}
)

# Define trading function
def buy_stock(symbol: str, amount: float):
    """Buy stock shares"""
    # In production: call actual trading API
    return {"bought": symbol, "amount": amount, "status": "filled"}

# Register with TBP enforcement
agent.register_function(
    function_map={"buy_stock": buy_stock},
    domain="finance",
    operation="trade"
)

# Now when the agent calls buy_stock:
# 1. TBP checks the action against OPA policies
# 2. If amount > threshold without approval -> BLOCKED
# 3. If allowed -> function executes
# 4. All decisions are logged with dual signatures
```

#### Example 2: System Administration Agent

```python
from autogen_integration import TBPEnforcer, TBPConversableAgent

enforcer = TBPEnforcer(agent_id="sysadmin-001")

agent = TBPConversableAgent(
    name="SysAdmin",
    enforcer=enforcer,
    domain="system",
    system_message="You manage system files."
)

def read_file(path: str):
    """Read a file from the system"""
    with open(path, 'r') as f:
        return f.read()

def write_file(path: str, content: str):
    """Write content to a file"""
    with open(path, 'w') as f:
        f.write(content)
    return {"status": "written", "path": path}

agent.register_function(
    function_map={
        "read_file": read_file,
        "write_file": write_file
    },
    domain="system"
)

# TBP will automatically:
# - Block access to /sys/kernel/* paths (I-INTEGRITY)
# - Block access to security logs without approval
# - Allow access to user data paths
```

#### Example 3: Multi-Agent Workflow

```python
from autogen import UserProxyAgent, GroupChat, GroupChatManager
from autogen_integration import (
    TBPEnforcer,
    create_trading_agent,
    create_system_agent
)

# Shared enforcer (same OPA server)
enforcer = TBPEnforcer(
    opa_url="http://localhost:8181",
    agent_id="workflow-001"
)

# Create specialized agents
trading_agent = create_trading_agent(enforcer)
system_agent = create_system_agent(enforcer)

# Human proxy (no TBP - represents actual human)
user_proxy = UserProxyAgent(
    name="User",
    human_input_mode="TERMINATE"
)

# Group chat
group = GroupChat(
    agents=[user_proxy, trading_agent, system_agent],
    messages=[],
    max_round=10
)

manager = GroupChatManager(groupchat=group)

# Start conversation
user_proxy.initiate_chat(
    manager,
    message="Buy $50,000 of AAPL and save the receipt to ~/trades/receipt.txt"
)
```

### Context Extraction

The `TBPConversableAgent` automatically extracts context from function arguments:

| Argument | Extracted As | Used For |
|----------|--------------|----------|
| `amount` | `transaction_value` | F-STABILITY checks |
| `value` | `transaction_value` | F-STABILITY checks |
| `path` | `path`, `path_category` | I-INTEGRITY checks |

**Path Categories:**

| Path Pattern | Category | TBP Treatment |
|--------------|----------|---------------|
| `/sys/*`, `*kernel*` | `kernel_config` | Blocked without approval |
| `/home/user/*` | `user_data` | Generally allowed |
| `*security*log*` | `security_logs` | Requires approval |

### Error Handling

When TBP blocks an action, the wrapped function returns an error dict instead of raising:

```python
# Blocked action returns:
{
    "error": "TBP_BLOCKED",
    "message": "TBP Policy Violation: F-STABILITY breach: transaction exceeds threshold",
    "function": "execute_trade"
}

# Execution error returns:
{
    "error": "EXECUTION_ERROR",
    "message": "Connection refused",
    "function": "execute_trade"
}
```

This allows AutoGen conversations to continue gracefully when actions are blocked.

### Audit Logging

Every action (allowed or blocked) is logged with dual cryptographic signatures:

1. **HMAC Signature**: Generated by OPA (Rego policy)
2. **RSA Signature**: Generated by Python (log_signer.py)

```python
# Example audit log entry
{
    "timestamp": "2026-02-07T15:30:00.000000Z",
    "ai_id": "trading-bot-001",
    "domain": "finance",
    "operation": "trade",
    "transaction_value": 50000,
    "allowed": true,
    "signature_hmac": "a8f3d9c2...",
    "signature": "3b7e9f1a...",
    "signature_algorithm": "RSA-PSS-SHA256"
}
```

---

## Testing

### Running Tests

```bash
cd tbp-v4-hard-shield/integrations

# Run AutoGen integration tests
pytest test_autogen_integration.py -v

# Run log signer tests
pytest test_log_signer.py -v

# Run all integration tests
pytest -v
```

### Test Coverage

The test suite covers:

- TBPEnforcementError exception behavior
- TBPEnforcer OPA communication (with mocked responses)
- TBPConversableAgent wrapper functionality
- Context extraction logic
- Trading and system agent factories
- Error handling edge cases

Tests that require AutoGen installed are marked with `skipif` and will be skipped if AutoGen is not available.

### Testing with AutoGen Installed

```bash
# Install AutoGen
pip install pyautogen

# Run full test suite (no skips)
pytest test_autogen_integration.py -v
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TBP_OPA_URL` | `http://localhost:8181` | OPA server URL |
| `TBP_POLICY_PATH` | `v1/data/tbp/core/v4` | Policy path in OPA |
| `TBP_AGENT_ID` | `autogen-agent-001` | Default agent identifier |

### OPA Policy Requirements

The OPA server must have the following endpoints available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{policy_path}/allow` | POST | Returns `{"result": true/false}` |
| `/{policy_path}/signed_decision_log` | POST | Returns signed audit log |
| `/{policy_path}/denial_reason` | POST | Returns human-readable denial reason |

---

## Troubleshooting

### Common Issues

**1. OPA Connection Refused**

```
TBPEnforcementError: OPA query failed: Connection refused
```

Solution: Ensure OPA is running and accessible:

```bash
docker-compose up -d
curl http://localhost:8181/health
```

**2. Policy Not Found**

```
TBPEnforcementError: OPA query failed: 404 Not Found
```

Solution: Verify policy path and that policies are loaded:

```bash
curl http://localhost:8181/v1/data/tbp/core/v4
```

**3. AutoGen Not Installed**

```
ImportError: AutoGen is not installed. Install with: pip install pyautogen
```

Solution: Install AutoGen:

```bash
pip install pyautogen
```

**4. Cryptography Library Missing**

```
ImportError: cryptography library required
```

Solution: Install cryptography:

```bash
pip install cryptography
```

---

## Security Considerations

1. **RSA Key Management**: In production, use HSM or secure key storage for RSA private keys.

2. **OPA Communication**: Use TLS for OPA connections in production.

3. **Audit Log Storage**: Implement proper audit log storage (database, SIEM) instead of console output.

4. **Agent IDs**: Use unique, traceable agent IDs for audit purposes.

---

## API Reference

### autogen_integration.py

```python
class TBPEnforcementError(Exception)
    """Raised when TBP policy blocks an action"""

class TBPEnforcer
    def __init__(opa_url, policy_path, agent_id)
    def check_action(domain, operation, **kwargs) -> Dict

class TBPConversableAgent(ConversableAgent)
    def __init__(name, enforcer, domain, **kwargs)
    def register_function(function_map, domain, operation)

def create_trading_agent(enforcer) -> TBPConversableAgent
def create_system_agent(enforcer) -> TBPConversableAgent
def create_tbp_workflow() -> Tuple[UserProxyAgent, GroupChatManager]
```

### log_signer.py

```python
class TBPLogSigner
    def __init__(private_key_path, public_key_path)
    def sign_log(log: Dict) -> Dict
    def verify_log(log: Dict) -> bool
    def save_private_key(path: str)
    def save_public_key(path: str)
```

---

## Contributing

When adding new integrations:

1. Follow the existing pattern (TBPEnforcer + wrapper class)
2. Include comprehensive tests with mocked OPA responses
3. Document all public APIs
4. Ensure dual signature support (HMAC + RSA)

---

## License

See the main repository LICENSE file.
