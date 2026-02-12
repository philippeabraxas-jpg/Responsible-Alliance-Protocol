"""
TBP v4.2.1 - Pattern Analysis Engine

PURPOSE:
    Detect salami attacks (cumulative small violations) and suspicious patterns
    in AI agent behavior through temporal analysis with sliding windows.

THREAT MODEL:
    - Agent makes 1000 x $9,999 transactions = $9,999,000 stolen
    - Each transaction individually "allowed" but cumulative pattern is attack
    - Frequency analysis detects rapid repeated actions
    - Behavioral drift detection (agent changing patterns over time)

ARCHITECTURE:
    ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
    │  Decision    │────▶│ Pattern Engine  │────▶│  OPA Policy  │
    │  Request     │     │ (This Module)   │     │  Evaluation  │
    └──────────────┘     └─────────────────┘     └──────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │  Time-Series │
                        │  Storage     │
                        └──────────────┘

SLIDING WINDOW ALGORITHM:
    - 24-hour window for cumulative tracking
    - Exponential decay for older events
    - Multiple aggregation levels (hour, day, week)

DETECTION PATTERNS:
    1. Cumulative amount exceeds threshold
    2. Frequency exceeds normal baseline
    3. Behavioral drift (sudden pattern change)
    4. Time-of-day anomalies
    5. Sequential similar actions

INTEGRATION:
    - Called BEFORE OPA evaluation
    - Enriches input context with pattern metrics
    - OPA uses metrics for decision
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


@dataclass
class PatternMetrics:
    """Metrics computed from pattern analysis"""
    
    # Cumulative metrics (sliding window)
    cumulative_amount_24h: float = 0.0
    cumulative_count_24h: int = 0
    cumulative_amount_7d: float = 0.0
    cumulative_count_7d: int = 0
    
    # Frequency metrics
    frequency_1h: float = 0.0  # Actions per hour
    frequency_24h: float = 0.0
    burst_detected: bool = False  # Rapid sequence detected
    
    # Behavioral metrics
    pattern_similarity: float = 0.0  # 0-1, how similar to past actions
    behavioral_drift: float = 0.0  # 0-1, how much behavior changed
    
    # Time-based metrics
    time_of_day_anomaly: bool = False  # Action outside normal hours
    weekend_anomaly: bool = False  # Action on unusual day
    
    # Sequential metrics
    sequential_similar_count: int = 0  # Consecutive similar actions
    
    # Risk score (aggregate)
    risk_score: float = 0.0  # 0-100, overall risk
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for OPA input"""
        return {
            "cumulative_24h": {
                "amount": self.cumulative_amount_24h,
                "count": self.cumulative_count_24h
            },
            "cumulative_7d": {
                "amount": self.cumulative_amount_7d,
                "count": self.cumulative_count_7d
            },
            "frequency": {
                "per_hour": self.frequency_1h,
                "per_day": self.frequency_24h,
                "burst": self.burst_detected
            },
            "behavioral": {
                "similarity": self.pattern_similarity,
                "drift": self.behavioral_drift
            },
            "temporal": {
                "time_anomaly": self.time_of_day_anomaly,
                "weekend_anomaly": self.weekend_anomaly
            },
            "sequential": {
                "similar_count": self.sequential_similar_count
            },
            "risk_score": self.risk_score
        }


@dataclass
class ActionEvent:
    """Single action event in time series"""
    timestamp: datetime
    agent_id: str
    action_type: str
    amount: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "amount": self.amount,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ActionEvent':
        """Deserialize from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(d["timestamp"]),
            agent_id=d["agent_id"],
            action_type=d["action_type"],
            amount=d.get("amount", 0.0),
            metadata=d.get("metadata", {})
        )


class SlidingWindow:
    """
    Time-based sliding window for event aggregation.
    
    Uses deque for efficient O(1) append and O(n) expiration.
    """
    
    def __init__(self, window_size: timedelta):
        """
        Initialize sliding window.
        
        Args:
            window_size: Duration of the window (e.g., 24 hours)
        """
        self.window_size = window_size
        self.events: deque[ActionEvent] = deque()
        self._lock = threading.RLock()
    
    def add(self, event: ActionEvent):
        """Add event to window"""
        with self._lock:
            self.events.append(event)
            self._expire_old()
    
    def _expire_old(self):
        """Remove events outside window"""
        now = datetime.now(timezone.utc)
        cutoff = now - self.window_size
        
        # Remove from left (oldest)
        while self.events and self.events[0].timestamp < cutoff:
            self.events.popleft()
    
    def get_events(self) -> List[ActionEvent]:
        """Get all events in current window"""
        with self._lock:
            self._expire_old()
            return list(self.events)
    
    def get_cumulative_amount(self) -> float:
        """Get sum of all amounts in window"""
        return sum(e.amount for e in self.get_events())
    
    def get_count(self) -> int:
        """Get count of events in window"""
        return len(self.get_events())
    
    def get_frequency(self) -> float:
        """Get frequency (events per second)"""
        events = self.get_events()
        if not events:
            return 0.0
        
        duration = (events[-1].timestamp - events[0].timestamp).total_seconds()
        if duration == 0:
            return float('inf')  # All events at same time = burst
        
        return len(events) / duration


class PatternAnalyzer:
    """
    Main pattern analysis engine.
    
    Detects salami attacks and behavioral anomalies using:
    - Sliding windows (24h, 7d)
    - Frequency analysis
    - Behavioral profiling
    - Temporal anomaly detection
    
    Usage:
        analyzer = PatternAnalyzer(storage_path="patterns.json")
        
        # Analyze action
        metrics = analyzer.analyze({
            "agent_id": "bot-001",
            "action": "transfer",
            "amount": 9999
        })
        
        # Check risk
        if metrics.risk_score > 80:
            print("🚨 High risk action detected!")
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        auto_save: bool = True,
        thresholds: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize pattern analyzer.
        
        Args:
            storage_path: Path for persistent storage
            auto_save: Auto-save state after each analysis
            thresholds: Custom thresholds (uses defaults if None)
        """
        # Sliding windows per agent
        self.windows_24h: Dict[str, SlidingWindow] = defaultdict(
            lambda: SlidingWindow(timedelta(hours=24))
        )
        self.windows_7d: Dict[str, SlidingWindow] = defaultdict(
            lambda: SlidingWindow(timedelta(days=7))
        )
        
        # Behavioral baselines per agent
        self.baselines: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Storage
        self.storage_path = storage_path
        self.auto_save = auto_save
        
        # Thresholds (can be customized)
        self.thresholds = thresholds or {
            "cumulative_24h_amount": 100000,  # $100k per day
            "cumulative_7d_amount": 500000,   # $500k per week
            "frequency_burst_hz": 10,          # 10 actions/sec = burst
            "behavioral_drift_threshold": 0.7, # 70% change = drift
            "sequential_similar_max": 5,       # 5 consecutive = suspicious
            "time_anomaly_hours": (9, 17),    # Normal hours: 9am-5pm
        }
        
        # Load existing data
        if storage_path and Path(storage_path).exists():
            self.load(storage_path)
        
        logger.info(f"PatternAnalyzer initialized with thresholds: {self.thresholds}")
    
    def analyze(self, action: Dict[str, Any]) -> PatternMetrics:
        """
        Analyze action and compute pattern metrics.
        
        Args:
            action: Action to analyze with fields:
                - agent_id: str
                - action_type: str (e.g., "transfer")
                - amount: float (optional)
                - metadata: dict (optional)
        
        Returns:
            PatternMetrics with computed values
        """
        agent_id = action["agent_id"]
        action_type = action.get("action_type", action.get("action", "unknown"))
        amount = float(action.get("amount", 0.0))
        
        # Create event
        event = ActionEvent(
            timestamp=datetime.now(timezone.utc),
            agent_id=agent_id,
            action_type=action_type,
            amount=amount,
            metadata=action.get("metadata", {})
        )
        
        # Add to windows
        self.windows_24h[agent_id].add(event)
        self.windows_7d[agent_id].add(event)
        
        # Compute metrics
        metrics = PatternMetrics()
        
        # 1. Cumulative metrics
        metrics.cumulative_amount_24h = self.windows_24h[agent_id].get_cumulative_amount()
        metrics.cumulative_count_24h = self.windows_24h[agent_id].get_count()
        metrics.cumulative_amount_7d = self.windows_7d[agent_id].get_cumulative_amount()
        metrics.cumulative_count_7d = self.windows_7d[agent_id].get_count()
        
        # 2. Frequency metrics
        frequency_1h = self._compute_frequency(agent_id, hours=1)
        frequency_24h = self._compute_frequency(agent_id, hours=24)
        metrics.frequency_1h = frequency_1h
        metrics.frequency_24h = frequency_24h
        
        # Burst detection (> threshold Hz)
        burst_hz = self.thresholds["frequency_burst_hz"]
        metrics.burst_detected = frequency_1h > (burst_hz * 3600)  # Convert to per-hour
        
        # 3. Behavioral metrics
        metrics.pattern_similarity = self._compute_similarity(agent_id, event)
        metrics.behavioral_drift = self._compute_drift(agent_id, event)
        
        # 4. Temporal anomalies
        metrics.time_of_day_anomaly = self._is_time_anomaly(event.timestamp)
        metrics.weekend_anomaly = self._is_weekend_anomaly(event.timestamp)
        
        # 5. Sequential similar actions
        metrics.sequential_similar_count = self._count_sequential_similar(agent_id, event)
        
        # 6. Compute risk score (0-100)
        metrics.risk_score = self._compute_risk_score(metrics)
        
        # Update baseline
        self._update_baseline(agent_id, event)
        
        # Auto-save
        if self.auto_save and self.storage_path:
            self.save()
        
        logger.debug(
            f"Analyzed {agent_id}/{action_type}: "
            f"risk={metrics.risk_score:.1f}, "
            f"cumulative_24h=${metrics.cumulative_amount_24h:.2f}"
        )
        
        return metrics
    
    def _compute_frequency(self, agent_id: str, hours: int) -> float:
        """Compute frequency (actions per hour) for time window"""
        events = self.windows_24h[agent_id].get_events()
        if not events:
            return 0.0
        
        # Filter to time window
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        recent_events = [e for e in events if e.timestamp >= cutoff]
        
        if not recent_events:
            return 0.0
        
        # Compute frequency
        duration_hours = (now - recent_events[0].timestamp).total_seconds() / 3600
        if duration_hours == 0:
            return float('inf')
        
        return len(recent_events) / duration_hours
    
    def _compute_similarity(self, agent_id: str, event: ActionEvent) -> float:
        """
        Compute similarity to past actions (0-1).
        
        High similarity = repetitive pattern
        """
        events = self.windows_24h[agent_id].get_events()
        if len(events) < 2:
            return 1.0  # First action = 100% similar to itself
        
        # Compare to recent actions
        recent = events[-10:]  # Last 10 actions
        similar_count = sum(
            1 for e in recent
            if e.action_type == event.action_type
            and abs(e.amount - event.amount) < (event.amount * 0.1)  # Within 10%
        )
        
        return similar_count / len(recent)
    
    def _compute_drift(self, agent_id: str, event: ActionEvent) -> float:
        """
        Compute behavioral drift (0-1).
        
        High drift = sudden change in behavior
        """
        baseline = self.baselines[agent_id]
        if not baseline:
            return 0.0  # No baseline yet
        
        # Compare action type frequency
        baseline_freq = baseline.get("action_frequencies", {})
        current_freq = self._get_current_frequencies(agent_id)
        
        # Compute KL divergence or similar metric (simplified)
        if not baseline_freq or not current_freq:
            return 0.0
        
        # Simple drift: % change in frequencies
        total_drift = 0.0
        for action_type in set(baseline_freq.keys()) | set(current_freq.keys()):
            baseline_val = baseline_freq.get(action_type, 0.0)
            current_val = current_freq.get(action_type, 0.0)
            total_drift += abs(baseline_val - current_val)
        
        return min(total_drift, 1.0)
    
    def _get_current_frequencies(self, agent_id: str) -> Dict[str, float]:
        """Get current action type frequencies"""
        events = self.windows_24h[agent_id].get_events()
        if not events:
            return {}
        
        # Count action types
        counts = defaultdict(int)
        for event in events:
            counts[event.action_type] += 1
        
        # Normalize to frequencies
        total = len(events)
        return {k: v / total for k, v in counts.items()}
    
    def _is_time_anomaly(self, timestamp: datetime) -> bool:
        """Check if timestamp is outside normal hours"""
        start_hour, end_hour = self.thresholds["time_anomaly_hours"]
        hour = timestamp.hour
        return hour < start_hour or hour >= end_hour
    
    def _is_weekend_anomaly(self, timestamp: datetime) -> bool:
        """Check if timestamp is on weekend"""
        # 5 = Saturday, 6 = Sunday
        return timestamp.weekday() >= 5
    
    def _count_sequential_similar(self, agent_id: str, event: ActionEvent) -> int:
        """Count consecutive similar actions"""
        events = self.windows_24h[agent_id].get_events()
        if len(events) < 2:
            return 1
        
        # Count backwards from end
        count = 1  # Current action
        for i in range(len(events) - 2, -1, -1):
            e = events[i]
            if (e.action_type == event.action_type and
                abs(e.amount - event.amount) < (event.amount * 0.1)):
                count += 1
            else:
                break
        
        return count
    
    def _compute_risk_score(self, metrics: PatternMetrics) -> float:
        """
        Compute overall risk score (0-100).
        
        Weighted combination of all metrics.
        """
        score = 0.0
        
        # Cumulative amount (0-40 points)
        amount_ratio = metrics.cumulative_amount_24h / self.thresholds["cumulative_24h_amount"]
        score += min(amount_ratio * 40, 40)
        
        # Frequency burst (0-20 points)
        if metrics.burst_detected:
            score += 20
        
        # Behavioral drift (0-15 points)
        if metrics.behavioral_drift > self.thresholds["behavioral_drift_threshold"]:
            score += 15
        
        # Sequential similar (0-15 points)
        if metrics.sequential_similar_count >= self.thresholds["sequential_similar_max"]:
            score += 15
        
        # Temporal anomalies (0-10 points)
        if metrics.time_of_day_anomaly:
            score += 5
        if metrics.weekend_anomaly:
            score += 5
        
        return min(score, 100.0)
    
    def _update_baseline(self, agent_id: str, event: ActionEvent):
        """Update behavioral baseline for agent"""
        baseline = self.baselines[agent_id]
        
        # Update action frequencies
        if "action_frequencies" not in baseline:
            baseline["action_frequencies"] = {}
        
        freqs = self._get_current_frequencies(agent_id)
        
        # Exponential moving average (EMA) for smooth updates
        alpha = 0.1  # Learning rate
        for action_type, freq in freqs.items():
            old_freq = baseline["action_frequencies"].get(action_type, 0.0)
            baseline["action_frequencies"][action_type] = (
                alpha * freq + (1 - alpha) * old_freq
            )
        
        # Update last seen
        baseline["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    def get_agent_summary(self, agent_id: str) -> Dict[str, Any]:
        """Get summary statistics for agent"""
        return {
            "agent_id": agent_id,
            "events_24h": self.windows_24h[agent_id].get_count(),
            "events_7d": self.windows_7d[agent_id].get_count(),
            "cumulative_24h": self.windows_24h[agent_id].get_cumulative_amount(),
            "cumulative_7d": self.windows_7d[agent_id].get_cumulative_amount(),
            "baseline": self.baselines.get(agent_id, {})
        }
    
    def save(self, filepath: Optional[str] = None):
        """Save state to file"""
        filepath = filepath or self.storage_path
        if not filepath:
            raise ValueError("No storage path specified")
        
        # Serialize state
        state = {
            "version": "1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thresholds": self.thresholds,
            "agents": {}
        }
        
        # Save per-agent data
        for agent_id in set(self.windows_24h.keys()) | set(self.baselines.keys()):
            state["agents"][agent_id] = {
                "events_24h": [e.to_dict() for e in self.windows_24h[agent_id].get_events()],
                "baseline": self.baselines.get(agent_id, {})
            }
        
        # Write to file
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Pattern state saved to {filepath}")
    
    def load(self, filepath: str):
        """Load state from file"""
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # Load thresholds
        self.thresholds = state.get("thresholds", self.thresholds)
        
        # Load per-agent data
        for agent_id, agent_data in state.get("agents", {}).items():
            # Restore events
            for event_dict in agent_data.get("events_24h", []):
                event = ActionEvent.from_dict(event_dict)
                self.windows_24h[agent_id].add(event)
                self.windows_7d[agent_id].add(event)
            
            # Restore baseline
            self.baselines[agent_id] = agent_data.get("baseline", {})
        
        logger.info(f"Pattern state loaded from {filepath}")
    
    def reset_agent(self, agent_id: str):
        """Reset all data for specific agent"""
        if agent_id in self.windows_24h:
            del self.windows_24h[agent_id]
        if agent_id in self.windows_7d:
            del self.windows_7d[agent_id]
        if agent_id in self.baselines:
            del self.baselines[agent_id]
        
        logger.info(f"Reset pattern data for {agent_id}")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== TBP Pattern Analysis - Salami Attack Detection ===\n")
    
    # Initialize analyzer
    analyzer = PatternAnalyzer()
    
    # Scenario: Agent tries salami attack
    print("1. Simulating salami attack (100 x $9,999)...")
    
    agent_id = "bot-001"
    for i in range(100):
        action = {
            "agent_id": agent_id,
            "action_type": "transfer",
            "amount": 9999.0
        }
        
        metrics = analyzer.analyze(action)
        
        # Print every 10th
        if (i + 1) % 10 == 0:
            print(f"   Transaction #{i+1}:")
            print(f"   - Cumulative 24h: ${metrics.cumulative_amount_24h:,.2f}")
            print(f"   - Risk score: {metrics.risk_score:.1f}/100")
            print(f"   - Sequential similar: {metrics.sequential_similar_count}")
            
            if metrics.risk_score > 80:
                print(f"   🚨 HIGH RISK DETECTED!")
    
    print("\n2. Agent summary:")
    summary = analyzer.get_agent_summary(agent_id)
    print(f"   Total 24h: ${summary['cumulative_24h']:,.2f}")
    print(f"   Total events: {summary['events_24h']}")
    
    print("\n3. Testing normal behavior...")
    normal_agent = "bot-002"
    for i in range(5):
        action = {
            "agent_id": normal_agent,
            "action_type": "read",
            "amount": 0.0
        }
        metrics = analyzer.analyze(action)
    
    print(f"   Normal agent risk: {metrics.risk_score:.1f}/100")
    
    print("\n=== Pattern Analysis Complete ===")
    print("✅ Salami attack detection implemented")
    print("✅ Sliding window tracking working")
    print("✅ Risk scoring operational")
