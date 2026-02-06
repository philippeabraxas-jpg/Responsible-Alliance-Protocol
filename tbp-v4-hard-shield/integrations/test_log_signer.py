"""
Test suite for TBP Log Signer (RSA signatures)
Run with: pytest test_log_signer.py -v
"""

import pytest
import json
import tempfile
import os
from datetime import datetime
from log_signer import TBPLogSigner


class TestTBPLogSigner:
    """Test suite for cryptographic log signing"""
    
    @pytest.fixture
    def signer(self):
        """Create a fresh signer for each test"""
        return TBPLogSigner()
    
    @pytest.fixture
    def sample_log(self):
        """Sample log entry for testing"""
        return {
            "timestamp": "2026-02-06T15:30:00.000000Z",
            "ai_id": "agent-001",
            "domain": "finance",
            "operation": "transfer",
            "transaction_value": 50000,
            "allowed": True,
            "invariant_triggered": None,
            "action_taken": "permitted"
        }
    
    # =============================================================================
    # Key Generation Tests
    # =============================================================================
    
    def test_key_pair_generation(self, signer):
        """Test that RSA key pair is generated on initialization"""
        assert signer.private_key is not None
        assert signer.public_key is not None
    
    def test_private_key_save_and_load(self, signer):
        """Test saving and loading private key"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Save private key
            signer.save_private_key(tmp_path)
            assert os.path.exists(tmp_path)
            
            # Load private key
            signer2 = TBPLogSigner(private_key_path=tmp_path)
            
            # Should be able to sign with loaded key
            log = {"test": "data"}
            signed = signer2.sign_log(log)
            assert "signature" in signed
        finally:
            os.unlink(tmp_path)
    
    def test_public_key_save_and_load(self, signer):
        """Test saving and loading public key"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Save public key
            signer.save_public_key(tmp_path)
            assert os.path.exists(tmp_path)
            
            # Load public key
            signer2 = TBPLogSigner(public_key_path=tmp_path)
            
            # Sign with original signer
            log = {"test": "data"}
            signed = signer.sign_log(log)
            
            # Verify with loaded public key
            assert signer2.verify_log(signed)
        finally:
            os.unlink(tmp_path)
    
    # =============================================================================
    # Signing Tests
    # =============================================================================
    
    def test_sign_log_basic(self, signer, sample_log):
        """Test basic log signing"""
        signed_log = signer.sign_log(sample_log)
        
        # Check signature added
        assert "signature" in signed_log
        assert "signature_algorithm" in signed_log
        assert signed_log["signature_algorithm"] == "RSA-PSS-SHA256"
        
        # Check original data preserved
        assert signed_log["timestamp"] == sample_log["timestamp"]
        assert signed_log["ai_id"] == sample_log["ai_id"]
        assert signed_log["allowed"] == sample_log["allowed"]
    
    def test_sign_log_with_existing_signature(self, signer, sample_log):
        """Test signing a log that already has an HMAC signature"""
        # Add HMAC signature
        sample_log["signature_hmac"] = "existing_hmac_signature"
        sample_log["signature_hmac_algorithm"] = "HMAC-SHA256"
        
        # Add RSA signature
        signed_log = signer.sign_log(sample_log)
        
        # Both signatures should be present
        assert "signature_hmac" in signed_log
        assert "signature" in signed_log  # RSA signature
        assert signed_log["signature_hmac"] == "existing_hmac_signature"
    
    def test_sign_empty_log(self, signer):
        """Test signing an empty log"""
        empty_log = {}
        signed_log = signer.sign_log(empty_log)
        
        assert "signature" in signed_log
        assert "signature_algorithm" in signed_log
    
    def test_signature_deterministic(self, signer, sample_log):
        """Test that same input produces same signature"""
        signed1 = signer.sign_log(sample_log.copy())
        signed2 = signer.sign_log(sample_log.copy())
        
        # Note: RSA-PSS uses random salt, so signatures will differ
        # But both should verify
        assert signer.verify_log(signed1)
        assert signer.verify_log(signed2)
    
    def test_signature_format(self, signer, sample_log):
        """Test that signature is hex-encoded"""
        signed_log = signer.sign_log(sample_log)
        signature = signed_log["signature"]
        
        # Should be hex string
        assert isinstance(signature, str)
        assert all(c in "0123456789abcdef" for c in signature)
        
        # Should be correct length for 2048-bit RSA (256 bytes = 512 hex chars)
        assert len(signature) == 512
    
    # =============================================================================
    # Verification Tests
    # =============================================================================
    
    def test_verify_valid_signature(self, signer, sample_log):
        """Test verifying a valid signature"""
        signed_log = signer.sign_log(sample_log)
        assert signer.verify_log(signed_log) is True
    
    def test_verify_tampered_data(self, signer, sample_log):
        """Test that tampering with data invalidates signature"""
        signed_log = signer.sign_log(sample_log)
        
        # Tamper with the data
        signed_log["allowed"] = False  # Change decision!
        
        # Verification should fail
        assert signer.verify_log(signed_log) is False
    
    def test_verify_tampered_timestamp(self, signer, sample_log):
        """Test that tampering with timestamp invalidates signature"""
        signed_log = signer.sign_log(sample_log)
        
        # Tamper with timestamp
        signed_log["timestamp"] = "2026-02-07T15:30:00.000000Z"
        
        # Verification should fail
        assert signer.verify_log(signed_log) is False
    
    def test_verify_tampered_amount(self, signer, sample_log):
        """Test that tampering with transaction amount invalidates signature"""
        signed_log = signer.sign_log(sample_log)
        
        # Tamper with amount
        signed_log["transaction_value"] = 5000  # Was 50000
        
        # Verification should fail
        assert signer.verify_log(signed_log) is False
    
    def test_verify_missing_signature(self, signer, sample_log):
        """Test verifying log without signature"""
        # Log without signature
        assert signer.verify_log(sample_log) is False
    
    def test_verify_invalid_signature_format(self, signer, sample_log):
        """Test verifying log with malformed signature"""
        signed_log = signer.sign_log(sample_log)
        
        # Corrupt signature
        signed_log["signature"] = "invalid_hex_string"
        
        # Verification should fail
        assert signer.verify_log(signed_log) is False
    
    def test_verify_with_different_key(self, sample_log):
        """Test that signature from one key doesn't verify with another"""
        signer1 = TBPLogSigner()
        signer2 = TBPLogSigner()  # Different key pair
        
        # Sign with signer1
        signed_log = signer1.sign_log(sample_log)
        
        # Verify with signer2 (should fail - different key)
        assert signer2.verify_log(signed_log) is False
        
        # Verify with signer1 (should succeed)
        assert signer1.verify_log(signed_log) is True
    
    # =============================================================================
    # Key Distribution Tests
    # =============================================================================
    
    def test_public_key_distribution(self, signer, sample_log):
        """Test that auditor with only public key can verify"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            pub_key_path = tmp.name
        
        try:
            # Save public key
            signer.save_public_key(pub_key_path)
            
            # Sign log
            signed_log = signer.sign_log(sample_log)
            
            # Auditor loads only public key
            auditor = TBPLogSigner(public_key_path=pub_key_path)
            
            # Auditor can verify but not sign
            assert auditor.verify_log(signed_log) is True
            
            # Auditor cannot sign (no private key)
            with pytest.raises(AttributeError):
                auditor.sign_log({"test": "data"})
        finally:
            os.unlink(pub_key_path)
    
    # =============================================================================
    # JSON Canonical Form Tests
    # =============================================================================
    
    def test_json_key_ordering(self, signer):
        """Test that JSON key ordering doesn't affect signature"""
        log1 = {"a": 1, "b": 2, "c": 3}
        log2 = {"c": 3, "b": 2, "a": 1}  # Different order
        
        signed1 = signer.sign_log(log1)
        signed2 = signer.sign_log(log2)
        
        # Both should verify (canonical form is sorted)
        assert signer.verify_log(signed1) is True
        assert signer.verify_log(signed2) is True
    
    def test_unicode_handling(self, signer):
        """Test that unicode in logs is handled correctly"""
        log = {
            "message": "Test with émojis 🎉 and ünïcödé",
            "amount": 1000
        }
        
        signed_log = signer.sign_log(log)
        assert signer.verify_log(signed_log) is True
    
    def test_nested_objects(self, signer):
        """Test signing logs with nested objects"""
        log = {
            "agent": {
                "id": "agent-001",
                "type": "trading"
            },
            "transaction": {
                "amount": 50000,
                "currency": "USD"
            }
        }
        
        signed_log = signer.sign_log(log)
        assert signer.verify_log(signed_log) is True
        
        # Tampering with nested value should invalidate
        signed_log["transaction"]["amount"] = 5000
        assert signer.verify_log(signed_log) is False
    
    # =============================================================================
    # Edge Cases
    # =============================================================================
    
    def test_large_log(self, signer):
        """Test signing very large log entries"""
        large_log = {
            "data": "x" * 100000,  # 100KB of data
            "timestamp": datetime.now().isoformat()
        }
        
        signed_log = signer.sign_log(large_log)
        assert signer.verify_log(signed_log) is True
    
    def test_special_characters(self, signer):
        """Test logs with special characters"""
        log = {
            "message": 'Test with "quotes" and \'apostrophes\' and\nnewlines\tand\ttabs',
            "data": "\\backslashes\\"
        }
        
        signed_log = signer.sign_log(log)
        assert signer.verify_log(signed_log) is True
    
    def test_null_values(self, signer):
        """Test logs with null values"""
        log = {
            "value1": None,
            "value2": "test",
            "value3": None
        }
        
        signed_log = signer.sign_log(log)
        assert signer.verify_log(signed_log) is True
    
    def test_boolean_values(self, signer):
        """Test logs with boolean values"""
        log = {
            "allowed": True,
            "denied": False
        }
        
        signed_log = signer.sign_log(log)
        assert signer.verify_log(signed_log) is True
        
        # Flipping boolean should invalidate
        signed_log["allowed"] = False
        assert signer.verify_log(signed_log) is False
    
    # =============================================================================
    # Performance Tests
    # =============================================================================
    
    def test_signing_performance(self, signer, sample_log, benchmark):
        """Benchmark signing performance"""
        def sign():
            return signer.sign_log(sample_log)
        
        result = benchmark(sign)
        assert "signature" in result
        
        # Should complete in < 10ms
        assert benchmark.stats["mean"] < 0.01
    
    def test_verification_performance(self, signer, sample_log, benchmark):
        """Benchmark verification performance"""
        signed_log = signer.sign_log(sample_log)
        
        def verify():
            return signer.verify_log(signed_log)
        
        result = benchmark(verify)
        assert result is True
        
        # Should complete in < 5ms
        assert benchmark.stats["mean"] < 0.005
    
    # =============================================================================
    # Integration Tests
    # =============================================================================
    
    def test_dual_signature_workflow(self, signer, sample_log):
        """Test complete dual-signature workflow (HMAC + RSA)"""
        # 1. Simulate HMAC signature from OPA
        sample_log["signature_hmac"] = "a8f3d9c2e1b4f7a3..."
        sample_log["signature_hmac_algorithm"] = "HMAC-SHA256"
        
        # 2. Add RSA signature (Python layer)
        dual_signed = signer.sign_log(sample_log)
        
        # 3. Verify both signatures present
        assert "signature_hmac" in dual_signed
        assert "signature" in dual_signed
        
        # 4. Verify RSA signature valid
        assert signer.verify_log(dual_signed) is True
        
        # 5. Tampering should invalidate RSA (HMAC check is separate)
        dual_signed["allowed"] = False
        assert signer.verify_log(dual_signed) is False
    
    def test_audit_scenario(self, signer):
        """Test realistic audit scenario"""
        # Generate multiple logs
        logs = []
        for i in range(10):
            log = {
                "timestamp": f"2026-02-06T15:{i:02d}:00Z",
                "ai_id": "agent-001",
                "allowed": i % 2 == 0,
                "sequence": i
            }
            signed = signer.sign_log(log)
            logs.append(signed)
        
        # Auditor verifies all logs
        for log in logs:
            assert signer.verify_log(log) is True
        
        # Attacker tampers with one log
        logs[5]["allowed"] = True  # Was False
        
        # Auditor detects tampering
        tampered = [log for log in logs if not signer.verify_log(log)]
        assert len(tampered) == 1
        assert tampered[0]["sequence"] == 5


# =============================================================================
# Pytest Configuration
# =============================================================================

# Install pytest-benchmark if not present
# pip install pytest pytest-benchmark

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
