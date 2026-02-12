import pytest
from policy_engine.rate_limiter import RateLimiter

def test_rate_limiting_blocks_flood():
    """
    Test that rate limiting blocks flood.
    
    Scenario:
    1. Send 10 requests rapidly (threshold is 5)
    2. TBP should rate-limit
    3. Verify that some are blocked
    """
    limiter = RateLimiter()
    limiter.limits["test_action"] = 5
    agent_id = "flooder"
    
    results = []
    for _ in range(10):
        allowed, _ = limiter.check_request(agent_id, "test_action")
        results.append(allowed)
        
    allowed_count = sum(1 for r in results if r)
    blocked_count = sum(1 for r in results if not r)
    
    assert allowed_count == 5
    assert blocked_count == 5

def test_global_rate_limit():
    """
    Test that global rate limit protects system across all agents.
    """
    limiter = RateLimiter()
    limiter.global_limit = 10
    
    # 5 different agents sending 5 requests each (Total 25)
    results = []
    for i in range(5):
        agent_id = f"bot-{i}"
        for _ in range(5):
            allowed, _ = limiter.check_request(agent_id, "any_action")
            results.append(allowed)
            
    allowed_count = sum(1 for r in results if r)
    assert allowed_count <= 10 # Global limit enforced
