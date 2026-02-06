# TBP-V3.1 Reference Implementation Stub

**Start implementing TBP in under 5 minutes.**

This folder contains everything you need to build a TBP-compliant enforcement system.

---

## 🚀 Quick Start for Implementers

### 1. Clone and Install

```bash
git clone https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol.git
cd Responsible-Alliance-Protocol/reference-stub
pip install pytest  # For running tests
```

### 2. Implement the Interface

Open `interface.py` and find the `TBPEnforcer` class. Implement the three core methods:

```python
class MyTBPImplementation(TBPEnforcer):
    
    def enforce_f_stability(self, action: Action, context: Context) -> EnforcementResult:
        # Your F-STABILITY logic here
        if action.type == "transfer" and not action.human_approved:
            return EnforcementResult(
                allowed=False,
                violated_invariant="F",
                error_code=TBPErrorCode.F_UNAUTHORIZED_TRANSFER,
                reason="Financial transfers require human approval"
            )
        return EnforcementResult(allowed=True, violated_invariant=None, error_code=None, reason="Pass")
    
    def enforce_i_integrity(self, action: Action, context: Context) -> EnforcementResult:
        # Your I-INTEGRITY logic here
        # ...
    
    def enforce_w_monopoly(self, action: Action, context: Context) -> EnforcementResult:
        # Your W-MONOPOLY logic here
        # ...
```

### 3. Run the Tests

```bash
pytest test_minimal.py -v
```

**Minimum requirement:** Pass the 3 critical tests:
- `test_f1_autonomous_transfer_blocked`
- `test_i1_infrastructure_access_blocked`
- `test_w1_weapons_control_blocked`

### 4. Submit Your Implementation

Once tests pass:
1. Fork the repository
2. Add your implementation to `reference-stub/implementations/`
3. Include benchmark results (latency < 2ms recommended)
4. Submit a Pull Request

**Checklist before PR:**
- [ ] All critical tests pass (F1, I1, W1)
- [ ] All functionality tests pass
- [ ] Logging follows Annex 7.A format
- [ ] Documentation included
- [ ] Example usage provided

---

## 📁 Files in This Folder

### [`interface.py`](interface.py)
**Formal interface definition with typed signatures.**

Contains:
- `TBPEnforcer` abstract base class
- `Action`, `Context`, `EnforcementResult` data types
- `TBPErrorCode` enum with standardized error codes
- `TBPLogger` interface for Annex 7.A logging
- Example stub implementation

**This is your starting point.** Copy the `ExampleImplementation` class and fill in the logic.

---

### [`test_minimal.py`](test_minimal.py)
**Minimal test suite for TBP compliance.**

Contains:
- 3 critical tests (F1, I1, W1) - **MUST PASS**
- 6 functionality tests (F2, F3, I2, I3, W2, W3) - **SHOULD PASS**
- Integration tests
- Logging format validation
- Performance test (optional, < 2ms target)

**Run these tests to validate your implementation.**

---

### [`error_codes.md`](error_codes.md)
**Standardized error codes and logging format.**

Contains:
- Complete list of error codes (0x1xx, 0x2xx, 0x3xx)
- Annex 7.A logging specification
- Usage examples
- Severity levels

**Reference this when implementing enforcement logic.**

---

### [`README.md`](README.md) *(this file)*
**Quick start guide for implementers.**

---

## 🎯 What You Need to Implement

### Core Logic (Required)

1. **F-STABILITY checks**
   - Detect autonomous financial operations
   - Verify human approval when required
   - Identify market manipulation patterns

2. **I-INTEGRITY checks**
   - Identify critical infrastructure targets
   - Detect resource parasitism
   - Block unauthorized system commands

3. **W-MONOPOLY checks**
   - Detect weapons-related operations
   - Identify coercive actions
   - Block harmful operations

### Logging (Required)

Implement `TBPLogger.log_violation()` following Annex 7.A format:

```json
{
  "timestamp": "ISO-8601",
  "ai_id": "your-enforcer-id",
  "invariant_triggered": "F | I | W",
  "error_code": "0xXYY",
  "action_taken": "categorical_refusal",
  "context_hash": "sha256",
  "audit_status": "logged_to_mediation_committee"
}
```

### Integration Hooks (Optional but Recommended)

Provide wrappers for popular frameworks:
- LangChain tools
- AutoGen agents
- LlamaIndex tools
- Custom middleware

See `../examples/integration_patterns.md` for patterns.

---

## 📊 Testing Your Implementation

### Run All Tests

```bash
pytest test_minimal.py -v
```

### Run Only Critical Tests

```bash
pytest test_minimal.py -k "test_f1 or test_i1 or test_w1" -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest test_minimal.py --cov=your_implementation --cov-report=html
```

### Performance Benchmark

```bash
pytest test_minimal.py -k "latency" -v
```

Target: < 2ms per enforcement check

---

## 🔧 Integration Points

Your TBP enforcer should be callable at these points in an AI system:

### Point 1: Before Tool Execution

```python
# In your agent's tool execution loop:
action = Action(type=tool.name, target=tool.target, parameters=params)
context = Context(timestamp=now(), agent_id=self.id)

result = tbp_enforcer.enforce(action, context)

if not result.allowed:
    raise TBPViolation(
        invariant=result.violated_invariant,
        error_code=result.error_code,
        reason=result.reason
    )

# Proceed with tool execution
tool.execute(params)
```

### Point 2: After LLM Generation (Token-Level)

```python
# In your LLM wrapper:
generated_text = llm.generate(prompt)

# Parse for action indicators
if contains_tool_call(generated_text):
    action = extract_action(generated_text)
    result = tbp_enforcer.enforce(action, context)
    
    if not result.allowed:
        generated_text = replace_with_refusal(generated_text, result.reason)
```

### Point 3: API Gateway Level

```python
# In your API middleware:
@app.before_request
def enforce_tbp():
    action = Action(
        type=request.method,
        target=request.path,
        parameters=request.json
    )
    
    result = tbp_enforcer.enforce(action, context)
    
    if not result.allowed:
        return {"error": "TBP violation", "code": result.error_code}, 403
```

---

## 🎓 Example Implementations

See `implementations/` folder for reference implementations (once contributed):

- `simple_python/` - Minimal pure Python implementation
- `langchain_plugin/` - LangChain integration
- `autogen_wrapper/` - AutoGen wrapper
- `fastapi_middleware/` - FastAPI middleware

---

## 📚 Additional Resources

- **Main Specification:** [README.md](../README.md)
- **Compliance Stress-Test:** [COMPLIANCE_STRESS_TEST.md](../COMPLIANCE_STRESS_TEST.md)
- **Integration Patterns:** [examples/integration_patterns.md](../examples/integration_patterns.md)
- **Pseudocode Reference:** [examples/enforcement_pseudocode.py](../examples/enforcement_pseudocode.py)

---

## 🤝 Contributing

### Before Submitting

1. **All tests pass:** Run `pytest test_minimal.py -v`
2. **Documentation complete:** Add docstrings and usage examples
3. **Performance acceptable:** Aim for < 2ms enforcement overhead
4. **Code quality:** Run `black` and `flake8` on your code

### What We Accept

- ✅ Reference implementations (Python, JavaScript, Rust, etc.)
- ✅ Framework integrations (LangChain, AutoGen, etc.)
- ✅ Performance optimizations
- ✅ Additional test scenarios
- ✅ Bug fixes and improvements

### What We Don't Accept

- ❌ Implementations that weaken F/I/W invariants
- ❌ Code that bypasses enforcement checks
- ❌ Implementations that don't pass critical tests
- ❌ Undocumented or untested code

---

## ❓ FAQ

### Q: Do I need to implement all three invariants?

**A:** Yes. TBP compliance requires all three (F, I, W). However, you can start with one and incrementally add others.

### Q: Can I use different error codes?

**A:** You must use the standardized codes from `error_codes.md` for interoperability. You can add new codes if needed.

### Q: What about false positives?

**A:** It's better to over-block than under-block. Provide clear error messages so humans can approve legitimate actions.

### Q: How do I handle edge cases?

**A:** When in doubt, block and require human approval. Document edge cases in your implementation.

### Q: Can I modify the interface?

**A:** No. The interface is part of the standard. If you need changes, open an issue to discuss.

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/issues)
- **Discussions:** [GitHub Discussions](https://github.com/philippeabraxas-jpg/Responsible-Alliance-Protocol/discussions)
- **Contributing:** [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 🎯 Success Criteria

Your implementation is ready when:

- ✅ All 3 critical tests pass
- ✅ All 6 functionality tests pass
- ✅ Logging follows Annex 7.A format
- ✅ Documentation is complete
- ✅ Performance is acceptable (< 2ms)
- ✅ Example usage is provided

---

**Ready to implement? Start with `interface.py` and make TBP real!** 🚀
