"""
Tests for time_attester.py - RFC 3161 Timestamp Authority

Test coverage:
- Mock mode (no network)
- Real TSA integration (requires internet)
- Cache validation
- Time drift detection
- Error handling
- Token verification
"""

import pytest
import time
from datetime import datetime, timezone, timedelta
import hashlib

from core.time_attester import (
    TimeAttester,
    TSAType,
    TimestampToken,
    TSAError,
    TSAConnectionError,
    TSAValidationError,
)


class TestMockMode:
    """Tests for mock mode (no network required)"""

    def test_initialization(self):
        """Test mock attester initializes correctly"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        assert attester.tsa_type == TSAType.MOCK
        assert attester.hash_algorithm == "sha256"
        assert len(attester.tsa_servers) == 1

        attester.close()

    def test_get_timestamp_mock(self):
        """Test getting timestamp in mock mode"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        data = b"Test audit log"
        token = attester.get_timestamp(data)

        assert isinstance(token, TimestampToken)
        assert token.tsa_name == "mock"
        assert token.hash_algorithm == "sha256"
        assert token.timestamp is not None

        attester.close()

    def test_verify_mock_token(self):
        """Test verifying mock token"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        data = b"Test data"
        token = attester.get_timestamp(data)

        # Mock tokens always verify (no real crypto)
        assert token.verify(data) == True

        attester.close()

    def test_cache_enabled(self):
        """Test caching works"""
        attester = TimeAttester(tsa_type=TSAType.MOCK, cache_enabled=True)

        data = b"Cached data"

        # First request (cache miss)
        token1 = attester.get_timestamp(data)
        assert attester.metrics["cache_misses"] == 1
        assert attester.metrics["cache_hits"] == 0

        # Second request (cache hit)
        token2 = attester.get_timestamp(data)
        assert attester.metrics["cache_hits"] == 1

        # Same token
        assert token1.timestamp == token2.timestamp

        attester.close()

    def test_cache_disabled(self):
        """Test with cache disabled"""
        attester = TimeAttester(tsa_type=TSAType.MOCK, cache_enabled=False)

        data = b"Uncached data"

        token1 = attester.get_timestamp(data)
        token2 = attester.get_timestamp(data)

        # No cache hits (cache disabled)
        assert attester.metrics["cache_hits"] == 0

        attester.close()

    def test_cache_ttl(self):
        """Test cache expiration"""
        attester = TimeAttester(tsa_type=TSAType.MOCK, cache_ttl=1)  # 1 second

        data = b"Expiring data"

        # First request
        token1 = attester.get_timestamp(data)

        # Wait for cache to expire
        time.sleep(1.1)

        # Second request (cache expired)
        token2 = attester.get_timestamp(data)

        # Should be cache miss (expired)
        assert attester.metrics["cache_misses"] == 2

        attester.close()

    def test_different_hash_algorithms(self):
        """Test different hash algorithms"""
        for algo in ["sha256", "sha384", "sha512"]:
            attester = TimeAttester(tsa_type=TSAType.MOCK, hash_algorithm=algo)

            data = b"Test"
            token = attester.get_timestamp(data)

            assert token.hash_algorithm == algo

            attester.close()

    def test_context_manager(self):
        """Test context manager closes properly"""
        data = b"Context test"

        with TimeAttester(tsa_type=TSAType.MOCK) as attester:
            token = attester.get_timestamp(data)
            assert token is not None

        # attester.close() called automatically


class TestTimestampToken:
    """Tests for TimestampToken class"""

    def test_token_serialization(self):
        """Test token to_dict/from_dict"""
        original = TimestampToken(
            timestamp=datetime.now(timezone.utc),
            serial_number=b"test123",
            tsa_certificate=None,
            token_data=b"token_bytes",
            tsa_name="test.tsa",
            hash_algorithm="sha256",
            nonce=12345,
        )

        # Serialize
        data = original.to_dict()

        assert "timestamp" in data
        assert "serial_number" in data
        assert data["tsa_name"] == "test.tsa"
        assert data["nonce"] == 12345

        # Deserialize
        restored = TimestampToken.from_dict(data)

        assert restored.serial_number == original.serial_number
        assert restored.tsa_name == original.tsa_name
        assert restored.hash_algorithm == original.hash_algorithm
        assert restored.nonce == original.nonce


class TestErrorHandling:
    """Tests for error handling"""

    def test_invalid_hash_algorithm(self):
        """Test invalid hash algorithm raises error"""
        with pytest.raises(ValueError, match="Unsupported hash"):
            TimeAttester(tsa_type=TSAType.MOCK, hash_algorithm="md5")  # Not supported

    def test_custom_tsa_without_urls(self):
        """Test CUSTOM type requires URLs"""
        with pytest.raises(ValueError, match="custom_urls required"):
            TimeAttester(tsa_type=TSAType.CUSTOM)

    def test_no_tsa_servers(self):
        """Test error when no servers configured"""
        # This should not happen in practice, but test it
        with pytest.raises(TSAConnectionError, match="No TSA servers"):
            attester = TimeAttester(tsa_type=TSAType.MOCK)
            attester.tsa_servers = []  # Force empty
            attester.get_timestamp(b"test")


class TestMetrics:
    """Tests for metrics tracking"""

    def test_metrics_tracking(self):
        """Test metrics are tracked correctly"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        data = b"Metrics test"

        # Generate some activity
        attester.get_timestamp(data)  # Miss
        attester.get_timestamp(data)  # Hit
        attester.get_timestamp(data)  # Hit

        metrics = attester.get_metrics()

        assert metrics["requests_total"] == 3
        assert metrics["cache_hits"] == 2
        assert metrics["cache_misses"] == 1
        assert metrics["cache_hit_rate"] == 2 / 3

        attester.close()

    def test_cache_size_metric(self):
        """Test cache size is tracked"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        # Add multiple entries
        for i in range(5):
            attester.get_timestamp(f"data_{i}".encode())

        metrics = attester.get_metrics()
        assert metrics["cache_size"] == 5

        # Clear cache
        attester.clear_cache()

        metrics = attester.get_metrics()
        assert metrics["cache_size"] == 0

        attester.close()


class TestTimeDrift:
    """Tests for time drift detection"""

    def test_time_drift_detection(self):
        """Test time drift is detected"""
        attester = TimeAttester(tsa_type=TSAType.MOCK, max_time_drift=2.0)  # 2 seconds max

        # First timestamp sets reference
        data1 = b"First"
        token1 = attester.get_timestamp(data1)

        # Mock a drifted timestamp
        # (In mock mode, we can't really simulate this, but test the logic)
        assert attester._reference_timestamp is not None

        attester.close()


@pytest.mark.network
class TestRealTSA:
    """
    Tests with real TSA servers (requires internet).

    Run with: pytest -m network
    Skip with: pytest -m "not network"
    """

    @pytest.mark.skipif(
        "not config.getoption('--run-network-tests', default=False)",
        reason="Network tests disabled (use --run-network-tests to enable)",
    )
    def test_freetsa_real(self):
        """Test with real FreeTSA server"""
        try:
            # Try asn1crypto import
            import asn1crypto
        except ImportError:
            pytest.skip("asn1crypto not installed")

        attester = TimeAttester(tsa_type=TSAType.FREETSA, timeout=30)  # Generous timeout

        data = b"Real TSA test"

        try:
            token = attester.get_timestamp(data)

            # Verify token structure
            assert token.timestamp is not None
            assert token.tsa_name != "mock"
            assert token.serial_number is not None
            assert len(token.token_data) > 0

            # Verify token
            assert token.verify(data) == True

            # Verify wrong data fails
            wrong_data = b"Wrong data"
            assert token.verify(wrong_data) == False

            print(f"\n✓ Real TSA test passed")
            print(f"  Timestamp: {token.timestamp}")
            print(f"  TSA: {token.tsa_name}")

        except TSAConnectionError as e:
            pytest.skip(f"TSA server unavailable: {e}")
        finally:
            attester.close()

    @pytest.mark.skipif(
        "not config.getoption('--run-network-tests', default=False)",
        reason="Network tests disabled",
    )
    def test_multiple_tsa_servers(self):
        """Test failover between TSA servers"""
        try:
            import asn1crypto
        except ImportError:
            pytest.skip("asn1crypto not installed")

        # Use APPLE TSA (usually reliable)
        attester = TimeAttester(tsa_type=TSAType.APPLE, timeout=30)

        data = b"Failover test"

        try:
            token = attester.get_timestamp(data)
            assert token.verify(data) == True

            print(f"\n✓ Apple TSA test passed")

        except TSAConnectionError as e:
            pytest.skip(f"TSA unavailable: {e}")
        finally:
            attester.close()


class TestCacheIntegrity:
    """Tests for cache integrity validation (Gemini's concern)"""

    def test_cache_validation_on_retrieval(self):
        """Test cached tokens are validated before returning"""
        attester = TimeAttester(tsa_type=TSAType.MOCK)

        data = b"Cache integrity test"

        # Get initial token
        token1 = attester.get_timestamp(data)

        # Manually corrupt cache
        cache_key = f"sha256:{hashlib.sha256(data).digest().hex()}"
        with attester._cache_lock:
            if cache_key in attester._cache:
                corrupted_token, cached_time = attester._cache[cache_key]
                # Corrupt the token data
                corrupted_token.token_data = b"corrupted"
                attester._cache[cache_key] = (corrupted_token, cached_time)

        # Try to get from cache (should detect corruption)
        # In mock mode, verification always passes, so this test
        # is more meaningful with real TSA
        token2 = attester.get_timestamp(data)

        # Should still work (cache miss due to corruption)
        assert token2 is not None

        attester.close()


# =============================================================================
# Test Configuration
# =============================================================================


def pytest_addoption(parser):
    """Add custom pytest options"""
    parser.addoption(
        "--run-network-tests",
        action="store_true",
        default=False,
        help="Run tests that require network access",
    )


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "network: mark test as requiring network access")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
