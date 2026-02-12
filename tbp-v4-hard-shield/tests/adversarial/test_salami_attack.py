import pytest
from policy_engine.pattern_analysis import PatternAnalyzer

def test_cumulative_threshold_blocks_salami():
    """
    Test that TBP detects accumulation on 24h.
    
    Scenario:
    1. Agent makes multiple transactions of $9,999
    2. Total cumulative threshold is $100k
    3. TBP should increase risk score and eventually block
    """
    analyzer = PatternAnalyzer(thresholds={"cumulative_24h_amount": 100000})
    agent_id = "attacker-bot"
    
    # Send 9 transactions of $9,999 (Total $89,991)
    for _ in range(9):
        metrics = analyzer.analyze({
            "agent_id": agent_id,
            "action": "transfer",
            "amount": 9999.0
        })
        assert metrics.risk_score < 80 # Should still be relatively low
        
    # Send 11 transactions of $9,999 (Total $109,989)
    # This should cross the cumulative threshold
    for _ in range(2):
        metrics = analyzer.analyze({
                "agent_id": agent_id,
                "action": "transfer",
                "amount": 9999.0
        })
    
    # We expect risk score to increase as we approach and cross thresholds
    assert metrics.cumulative_amount_24h > 100000
    assert metrics.risk_score >= 40 # Based on weight (amount_ratio * 40)

def test_frequency_detection():
    """
    Test detection of rapid repeated actions.
    """
    analyzer = PatternAnalyzer(thresholds={"frequency_burst_hz": 1})
    agent_id = "burst-bot"
    
    # Simulate rapid transactions
    for i in range(10):
        metrics = analyzer.analyze({
            "agent_id": agent_id,
            "action": "read",
            "amount": 0.0
        })
    
    # Frequency should be high since they happened in the same second
    assert metrics.burst_detected == True
    assert metrics.risk_score >= 20 # frequency_burst adds 20 points
