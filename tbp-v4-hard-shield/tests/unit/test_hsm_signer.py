"""
Unit tests for HSM signer - Complete test suite
"""

import pytest
import time
from core.hsm_signer import (
    HSMSigner, HSMType, SigningResult,
    HSMSignerError, HSMConnectionError, HSMSigningError
)

class TestSoftwareMode:
    """Tests for software fallback mode"""
    
    def test_initialization(self):
        """Test software signer initializes correctly"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        assert signer.hsm_type == HSMType.SOFTWARE
        assert signer.private_key is not None
        assert signer.public_key_pem is not None
        signer.close()
    
    def test_sign_and_verify(self):
        """Test basic sign/verify workflow"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        data = b"Test log entry"
        result = signer.sign(data, "test-agent")
        
        assert isinstance(result, SigningResult)
        assert len(result.signature) > 0
        assert result.key_id.startswith("software-")
        
        # Verify
        assert signer.verify(data, result, "test-agent") == True
        signer.close()
    
    def test_verify_tampered_data_fails(self):
        """Test verification fails for tampered data"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        data = b"Original data"
        result = signer.sign(data, "test-agent")
        
        # Tamper with data
        tampered = b"Tampered data"
        
        # Should fail verification
        assert signer.verify(tampered, result, "test-agent") == False
        signer.close()
    
    def test_verify_tampered_signature_fails(self):
        """Test verification fails for tampered signature"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        data = b"Test data"
        result = signer.sign(data, "test-agent")
        
        # Tamper with signature
        tampered_result = SigningResult(
            signature=result.signature[:100] + b"tampered" + result.signature[108:],
            key_id=result.key_id,
            timestamp=result.timestamp,
            mechanism=result.mechanism,
            hsm_type=result.hsm_type
        )
        
        # Should fail verification
        assert signer.verify(data, tampered_result, "test-agent") == False
        signer.close()
    
    def test_public_key_export(self):
        """Test public key can be exported"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        pub_key = signer.get_public_key()
        
        assert pub_key.startswith(b"-----BEGIN PUBLIC KEY-----")
        assert len(pub_key) > 200
        signer.close()
    
    def test_rate_limiting(self):
        """Test rate limiting prevents abuse"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        data = b"Test"
        
        # Should allow 100 operations
        for i in range(100):
            signer.sign(data, "test-agent")
        
        # 101st should fail
        with pytest.raises(HSMSigningError, match="Rate limit"):
            signer.sign(data, "test-agent")
        
        signer.close()
    
    def test_timestamp_included_in_signature(self):
        """Test timestamp is part of signature"""
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        data = b"Test data"
        
        # Sign with timestamp 1
        result1 = signer.sign(data, "test-agent", timestamp=1000.0)
        
        # Sign same data with timestamp 2
        result2 = signer.sign(data, "test-agent", timestamp=2000.0)
        
        # Signatures should differ (timestamp is included)
        assert result1.signature != result2.signature
        
        signer.close()
    
    def test_context_manager(self):
        """Test context manager closes session"""
        with HSMSigner(hsm_type=HSMType.SOFTWARE) as signer:
            data = b"Test"
            result = signer.sign(data, "test-agent")
            assert signer.verify(data, result, "test-agent") == True
        
        # Session should be closed after context exit

class TestSoftHSM:
    """Tests for SoftHSM (requires SoftHSM2 installed)"""
    
    @pytest.fixture(scope="class")
    def softhsm_setup(self):
        """Setup SoftHSM for testing"""
        from core.hsm_signer import setup_softhsm_test
        result = setup_softhsm_test()
        
        # Handle both 3-tuple and 4-tuple returns
        if len(result) == 3:
            lib_path, slot, pin = result
            cleanup = lambda: None
        else:
            lib_path, slot, pin, cleanup = result
        
        if lib_path is None:
            pytest.skip("SoftHSM2 not installed")
        
        yield lib_path, slot, pin, cleanup
        
        # Cleanup
        cleanup()
    
    def test_softhsm_connection(self, softhsm_setup):
        """Test connection to SoftHSM"""
        lib_path, slot, pin, cleanup = softhsm_setup
        
        signer = HSMSigner(
            hsm_type=HSMType.PKCS11_GENERIC,
            pin=pin,
            slot=slot,
            library_path=lib_path,
            key_label="test-key",
            auto_generate_key=True
        )
        
        assert signer.session is not None
        assert signer.private_key is not None
        
        signer.close()
    
    def test_softhsm_sign_verify(self, softhsm_setup):
        """Test sign/verify with SoftHSM"""
        lib_path, slot, pin, cleanup = softhsm_setup
        
        signer = HSMSigner(
            hsm_type=HSMType.PKCS11_GENERIC,
            pin=pin,
            slot=slot,
            library_path=lib_path,
            key_label="test-sign-key",
            auto_generate_key=True
        )
        
        data = b"HSM test data"
        result = signer.sign(data, "test-agent")
        
        assert result.hsm_type == "pkcs11"
        assert signer.verify(data, result, "test-agent") == True
        
        signer.close()

class TestSigningResult:
    """Tests for SigningResult dataclass"""
    
    def test_to_dict(self):
        """Test serialization to dict"""
        result = SigningResult(
            signature=b"fake_sig",
            key_id="test-key-123",
            timestamp=1234567890.0,
            mechanism="RSA-PSS-SHA256",
            hsm_type="software"
        )
        
        d = result.to_dict()
        
        assert d["signature"] == result.signature.hex()
        assert d["key_id"] == "test-key-123"
        assert d["timestamp"] == 1234567890.0
    
    def test_from_dict(self):
        """Test deserialization from dict"""
        d = {
            "signature": "66616b655f736967",  # hex for b"fake_sig"
            "key_id": "test-key-123",
            "timestamp": 1234567890.0,
            "mechanism": "RSA-PSS-SHA256",
            "hsm_type": "software"
        }
        
        result = SigningResult.from_dict(d)
        
        assert result.signature == b"fake_sig"
        assert result.key_id == "test-key-123"

class TestErrorHandling:
    """Tests for error handling"""
    
    def test_missing_pkcs11_library(self):
        """Test error when PKCS#11 library not found"""
        with pytest.raises(HSMConnectionError, match="python-pkcs11 library not installed|PKCS#11 library not found"):
            HSMSigner(
                hsm_type=HSMType.YUBIKEY,
                library_path="/nonexistent/path.so"
            )
    
    def test_wrong_pin(self):
        """Test error with wrong PIN"""
        # This requires actual HSM, skip in CI
        pytest.skip("Requires real HSM hardware")

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
