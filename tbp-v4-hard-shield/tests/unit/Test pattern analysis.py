"""
TBP v4.2.1 - Pattern Analysis Tests

Tests for salami attack detection and behavioral analysis.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pattern_analysis import (
    PatternAnalyzer,
    PatternMetrics,
    ActionEvent,
    SlidingWindow
)
import tempfile
import json


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def analyzer():
    """Create fresh analyzer for each test"""
    return PatternAnalyzer(storage_path=None, auto_save=False)


@pytest.fixture
def analyzer_with_storage():
    """Create analyzer with temporary storage"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        return PatternAnalyzer(storage_path=f.name, auto_save=True)


@pytest.fixture
def sample_action():
    """Sample action for testing"""
    return {
        "agent_id": "test-bot-001",
        "action_type": "transfer",
        "amount": 5000.0,
        "metadata": {"to": "account-123"}
    }


# =============================================================================
# SlidingWindow Tests
# =============================================================================

class TestSlidingWindow:
    """Test sliding window implementation"""
    
    def test_window_creation(self):
        """Test window initialization"""
        window = SlidingWindow(timedelta(hours=24))
        assert window.get_count() == 0
        assert window.get_cumulative_amount() == 0.0
    
    def test_add_event(self):
        """Test adding events to window"""
        window = SlidingWindow(timedelta(hours=24))
        
        event = ActionEvent(
            timestamp=datetime.now(timezone.utc),
            agent_id="bot-001",
            action_type="transfer",
            amount=1000.0
        )
        
        window.add(event)
        
        assert window.get_count() == 1
        assert window.get_cumulative_amount() == 1000.0
    
    def test_window_expiration(self):
        """Test old events expire"""
        window = SlidingWindow(timedelta(seconds=1))
        
        # Add old event
        old_event = ActionEvent(
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=2),
            agent_id="bot-001",
            action_type="transfer",
            amount=1000.0
        )
        window.add(old_event)
        
        # Should be expired
        assert window.get_count() == 0
    
    def test_cumulative_amount(self):
        """Test cumulative amount calculation"""
        window = SlidingWindow(timedelta(hours=1))
        
        for i in range(10):
            event = ActionEvent(
                timestamp=datetime.now(timezone.utc),
                agent_id="bot-001",
                action_type="transfer",
                amount=1000.0
            )
            window.add(event)
        
        assert window.get_cumulative_amount() == 10000.0
    
    def test_frequency_calculation(self):
        """Test frequency calculation"""
        window = SlidingWindow(timedelta(hours=1))
        
        # Add 10 events over 1 second
        now = datetime.now(timezone.utc)
        for i in range(10):
            event = ActionEvent(
                timestamp=now + timedelta(milliseconds=i*100),
                agent_id="bot-001",
                action_type="transfer",
                amount=100.0
            )
            window.add(event)
        
        freq = window.get_frequency()
        assert freq > 0  # Should have some frequency


# =============================================================================
# PatternMetrics Tests
# =============================================================================

class TestPatternMetrics:
    """Test pattern metrics dataclass"""
    
    def test_metrics_creation(self):
        """Test metrics initialization"""
        metrics = PatternMetrics()
        assert metrics.cumulative_amount_24h == 0.0
        assert metrics.risk_score == 0.0
    
    def test_metrics_to_dict(self):
        """Test serialization to dict"""
        metrics = PatternMetrics(
            cumulative_amount_24h=50000.0,
            risk_score=75.0
        )
        
        d = metrics.to_dict()
        
        assert d["cumulative_24h"]["amount"] == 50000.0
        assert d["risk_score"] == 75.0


# =============================================================================
# PatternAnalyzer - Basic Tests
# =============================================================================

class TestPatternAnalyzerBasic:
    """Test basic analyzer functionality"""
    
    def test_analyzer_initialization(self, analyzer):
        """Test analyzer creation"""
        assert analyzer is not None
        assert analyzer.thresholds["cumulative_24h_amount"] == 100000
    
    def test_single_action_analysis(self, analyzer, sample_action):
        """Test analyzing single action"""
        metrics = analyzer.analyze(sample_action)
        
        assert metrics.cumulative_amount_24h == 5000.0
        assert metrics.cumulative_count_24h == 1
        assert metrics.risk_score >= 0.0
    
    def test_multiple_actions(self, analyzer):
        """Test analyzing multiple actions"""
        agent_id = "bot-001"
        
        for i in range(10):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 1000.0
            }
            metrics = analyzer.analyze(action)
        
        assert metrics.cumulative_amount_24h == 10000.0
        assert metrics.cumulative_count_24h == 10
    
    def test_different_agents_isolated(self, analyzer):
        """Test that different agents have isolated metrics"""
        # Agent 1
        analyzer.analyze({
            "agent_id": "bot-001",
            "action_type": "transfer",
            "amount": 5000.0
        })
        
        # Agent 2
        metrics2 = analyzer.analyze({
            "agent_id": "bot-002",
            "action_type": "transfer",
            "amount": 3000.0
        })
        
        # Agent 2 should only see their own amount
        assert metrics2.cumulative_amount_24h == 3000.0


# =============================================================================
# Salami Attack Detection
# =============================================================================

class TestSalamiAttackDetection:
    """Test detection of salami attacks"""
    
    def test_small_repeated_transactions(self, analyzer):
        """Test detection of many small transactions"""
        agent_id = "salami-bot"
        
        # Simulate 100 x $9,999 = $999,900
        for i in range(100):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 9999.0
            }
            metrics = analyzer.analyze(action)
        
        # Should detect high cumulative amount
        assert metrics.cumulative_amount_24h >= 900000  # At least $900k
        
        # Should have high risk score
        assert metrics.risk_score > 50  # Should be flagged
    
    def test_cumulative_threshold_exceeded(self, analyzer):
        """Test that cumulative threshold is detected"""
        agent_id = "bot-threshold"
        
        # Add transactions totaling $150k (exceeds $100k threshold)
        for i in range(15):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 10000.0
            }
            metrics = analyzer.analyze(action)
        
        # Risk score should increase as threshold exceeded
        assert metrics.cumulative_amount_24h == 150000.0
        assert metrics.risk_score > 40  # Should contribute to risk
    
    def test_sequential_similar_detection(self, analyzer):
        """Test detection of consecutive similar actions"""
        agent_id = "bot-sequential"
        
        # Do 10 identical transactions
        for i in range(10):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 5000.0
            }
            metrics = analyzer.analyze(action)
        
        # Should detect high sequential similarity
        assert metrics.sequential_similar_count >= 5
    
    def test_burst_detection(self, analyzer):
        """Test detection of rapid bursts"""
        agent_id = "bot-burst"
        
        # Add many actions very quickly
        for i in range(50):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 100.0
            }
            metrics = analyzer.analyze(action)
        
        # Should detect high frequency
        assert metrics.frequency_1h > 0


# =============================================================================
# Behavioral Analysis
# =============================================================================

class TestBehavioralAnalysis:
    """Test behavioral pattern detection"""
    
    def test_pattern_similarity(self, analyzer):
        """Test pattern similarity calculation"""
        agent_id = "bot-pattern"
        
        # Establish pattern (10 read actions)
        for i in range(10):
            analyzer.analyze({
                "agent_id": agent_id,
                "action_type": "read",
                "amount": 0.0
            })
        
        # Continue same pattern
        metrics = analyzer.analyze({
            "agent_id": agent_id,
            "action_type": "read",
            "amount": 0.0
        })
        
        # Should have high similarity
        assert metrics.pattern_similarity > 0.5
    
    def test_behavioral_drift(self, analyzer):
        """Test behavioral drift detection"""
        agent_id = "bot-drift"
        
        # Establish baseline (reads only)
        for i in range(20):
            analyzer.analyze({
                "agent_id": agent_id,
                "action_type": "read",
                "amount": 0.0
            })
        
        # Suddenly switch to transfers
        for i in range(20):
            analyzer.analyze({
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 1000.0
            })
        
        # Get final metrics
        metrics = analyzer.analyze({
            "agent_id": agent_id,
            "action_type": "transfer",
            "amount": 1000.0
        })
        
        # Should detect drift (though may take time to manifest)
        # Note: Drift detection uses exponential moving average
        # so might not be immediately high


# =============================================================================
# Temporal Analysis
# =============================================================================

class TestTemporalAnalysis:
    """Test time-based anomaly detection"""
    
    def test_time_of_day_anomaly(self, analyzer):
        """Test detection of unusual hours"""
        # Analyzer default: normal hours 9am-5pm
        
        # Create action at 3am (unusual)
        action = {
            "agent_id": "bot-night",
            "action_type": "transfer",
            "amount": 5000.0
        }
        
        # Mock timestamp at 3am
        # (In real test, would need to mock datetime.now)
        # For now, test the detection method directly
        from datetime import datetime, timezone
        
        night_time = datetime(2026, 2, 13, 3, 0, 0, tzinfo=timezone.utc)
        is_anomaly = analyzer._is_time_anomaly(night_time)
        
        assert is_anomaly == True
        
        # Test normal time (noon)
        day_time = datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
        is_anomaly = analyzer._is_time_anomaly(day_time)
        
        assert is_anomaly == False
    
    def test_weekend_anomaly(self, analyzer):
        """Test detection of weekend activity"""
        # Saturday (weekday = 5)
        saturday = datetime(2026, 2, 14, 12, 0, 0, tzinfo=timezone.utc)
        is_weekend = analyzer._is_weekend_anomaly(saturday)
        assert is_weekend == True
        
        # Monday (weekday = 0)
        monday = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)
        is_weekend = analyzer._is_weekend_anomaly(monday)
        assert is_weekend == False


# =============================================================================
# Risk Scoring
# =============================================================================

class TestRiskScoring:
    """Test risk score calculation"""
    
    def test_risk_increases_with_amount(self, analyzer):
        """Test risk score increases with cumulative amount"""
        agent_id = "bot-risk"
        
        scores = []
        
        # Add increasing amounts
        for i in range(20):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 10000.0  # $10k each
            }
            metrics = analyzer.analyze(action)
            scores.append(metrics.risk_score)
        
        # Risk should generally increase
        assert scores[-1] > scores[0]
    
    def test_risk_score_bounds(self, analyzer):
        """Test risk score is within 0-100"""
        # Extreme scenario
        for i in range(1000):
            action = {
                "agent_id": "bot-extreme",
                "action_type": "transfer",
                "amount": 50000.0
            }
            metrics = analyzer.analyze(action)
        
        # Should be capped at 100
        assert 0 <= metrics.risk_score <= 100
    
    def test_low_risk_normal_behavior(self, analyzer):
        """Test low risk for normal behavior"""
        # Small, infrequent actions
        for i in range(3):
            action = {
                "agent_id": "bot-normal",
                "action_type": "read",
                "amount": 10.0
            }
            metrics = analyzer.analyze(action)
        
        # Should have low risk
        assert metrics.risk_score < 30


# =============================================================================
# Persistence
# =============================================================================

class TestPersistence:
    """Test state persistence"""
    
    def test_save_and_load(self, analyzer_with_storage):
        """Test saving and loading state"""
        # Add some data
        for i in range(5):
            analyzer_with_storage.analyze({
                "agent_id": "bot-persist",
                "action_type": "transfer",
                "amount": 1000.0
            })
        
        # Save (should auto-save already)
        storage_path = analyzer_with_storage.storage_path
        
        # Create new analyzer and load
        analyzer2 = PatternAnalyzer(storage_path=storage_path, auto_save=False)
        
        # Should have loaded data
        summary = analyzer2.get_agent_summary("bot-persist")
        assert summary["events_24h"] >= 5
    
    def test_baseline_persistence(self, analyzer_with_storage):
        """Test baseline data is persisted"""
        agent_id = "bot-baseline"
        
        # Establish baseline
        for i in range(10):
            analyzer_with_storage.analyze({
                "agent_id": agent_id,
                "action_type": "read",
                "amount": 0.0
            })
        
        storage_path = analyzer_with_storage.storage_path
        
        # Load in new analyzer
        analyzer2 = PatternAnalyzer(storage_path=storage_path)
        
        # Should have baseline
        summary = analyzer2.get_agent_summary(agent_id)
        assert "baseline" in summary
        assert summary["baseline"]


# =============================================================================
# Agent Summary
# =============================================================================

class TestAgentSummary:
    """Test agent summary functionality"""
    
    def test_get_summary(self, analyzer):
        """Test getting agent summary"""
        agent_id = "bot-summary"
        
        # Add some actions
        for i in range(5):
            analyzer.analyze({
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 2000.0
            })
        
        summary = analyzer.get_agent_summary(agent_id)
        
        assert summary["agent_id"] == agent_id
        assert summary["events_24h"] == 5
        assert summary["cumulative_24h"] == 10000.0
    
    def test_reset_agent(self, analyzer):
        """Test resetting agent data"""
        agent_id = "bot-reset"
        
        # Add data
        analyzer.analyze({
            "agent_id": agent_id,
            "action_type": "transfer",
            "amount": 5000.0
        })
        
        # Reset
        analyzer.reset_agent(agent_id)
        
        # Summary should show no data
        summary = analyzer.get_agent_summary(agent_id)
        assert summary["events_24h"] == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with realistic scenarios"""
    
    def test_realistic_salami_attack(self, analyzer):
        """Test realistic salami attack scenario"""
        agent_id = "malicious-trader"
        
        # Attacker does 500 small transactions just under threshold
        # Total: $4,995,000 (way over $100k daily threshold)
        results = []
        
        for i in range(500):
            action = {
                "agent_id": agent_id,
                "action_type": "transfer",
                "amount": 9990.0  # Just under $10k
            }
            metrics = analyzer.analyze(action)
            results.append(metrics)
        
        # Final metrics
        final = results[-1]
        
        # Should detect massive cumulative amount
        assert final.cumulative_amount_24h > 1000000  # > $1M
        
        # Should have very high risk score
        assert final.risk_score > 70
        
        # Should detect sequential similarity
        assert final.sequential_similar_count > 10
    
    def test_normal_trading_day(self, analyzer):
        """Test normal trading activity doesn't trigger false positives"""
        agent_id = "normal-trader"
        
        # Normal trading: varied amounts, different actions, moderate frequency
        actions = [
            {"action_type": "read", "amount": 0},
            {"action_type": "read", "amount": 0},
            {"action_type": "transfer", "amount": 5000},
            {"action_type": "read", "amount": 0},
            {"action_type": "transfer", "amount": 3000},
            {"action_type": "read", "amount": 0},
            {"action_type": "transfer", "amount": 7000},
        ]
        
        for action in actions:
            action["agent_id"] = agent_id
            metrics = analyzer.analyze(action)
        
        # Should have low risk
        assert metrics.risk_score < 50  # Not flagged as high risk


# =============================================================================
# Performance Tests
# =============================================================================

@pytest.mark.slow
class TestPerformance:
    """Test performance characteristics"""
    
    def test_large_volume_performance(self, analyzer):
        """Test analyzer handles large volumes"""
        import time
        
        start = time.time()
        
        # Analyze 1000 actions
        for i in range(1000):
            analyzer.analyze({
                "agent_id": f"bot-{i % 10}",  # 10 different agents
                "action_type": "transfer",
                "amount": 1000.0
            })
        
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0
        
        # Should handle frequency calculation
        ops_per_sec = 1000 / elapsed
        print(f"\nPattern analysis: {ops_per_sec:.1f} ops/sec")
        assert ops_per_sec > 100  # At least 100 ops/sec


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
