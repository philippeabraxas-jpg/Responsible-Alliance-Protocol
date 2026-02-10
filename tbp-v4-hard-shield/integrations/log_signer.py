"""
TBP Log Signer - RSA Cryptographic Signatures for Audit Logs

This module provides RSA-PSS signing and verification for TBP audit logs.
Used alongside HMAC signatures from OPA for dual-signature audit trail.

Key Features:
- RSA-PSS-SHA256 signatures (2048-bit keys)
- Canonical JSON serialization for consistent hashing
- Key persistence (save/load PEM files)
- Signature verification for audit

Usage:
    signer = TBPLogSigner()
    signed_log = signer.sign_log({"action": "transfer", "amount": 5000})
    is_valid = signer.verify_log(signed_log)
"""

import json
import hashlib
from typing import Dict, Any, Optional

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class TBPLogSigner:
    """
    RSA-PSS signer for TBP audit logs
    
    Generates RSA key pair on initialization or loads from files.
    Signs logs with RSA-PSS-SHA256 and verifies signatures.
    """
    
    def __init__(
        self,
        private_key_path: Optional[str] = None,
        public_key_path: Optional[str] = None
    ):
        """
        Initialize the log signer
        
        Args:
            private_key_path: Path to PEM file with private key (for signing)
            public_key_path: Path to PEM file with public key (for verification only)
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography library required. Install with: pip install cryptography"
            )
        
        self.private_key = None
        self.public_key = None
        
        if private_key_path:
            self._load_private_key(private_key_path)
        elif public_key_path:
            self._load_public_key(public_key_path)
        else:
            self._generate_key_pair()
    
    def _generate_key_pair(self):
        """Generate a new RSA key pair"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
    
    def _load_private_key(self, path: str):
        """Load private key from PEM file"""
        with open(path, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        self.public_key = self.private_key.public_key()
    
    def _load_public_key(self, path: str):
        """Load public key from PEM file (verification only)"""
        with open(path, "rb") as f:
            self.public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        # No private key - can only verify, not sign
    
    def save_private_key(self, path: str):
        """Save private key to PEM file"""
        if not self.private_key:
            raise ValueError("No private key to save")
        
        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(path, "wb") as f:
            f.write(pem)
    
    def save_public_key(self, path: str):
        """Save public key to PEM file"""
        if not self.public_key:
            raise ValueError("No public key to save")
        
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(path, "wb") as f:
            f.write(pem)
    
    def _canonical_json(self, data: Dict[str, Any]) -> bytes:
        """
        Convert dict to canonical JSON bytes for consistent hashing
        
        - Keys sorted alphabetically
        - No whitespace
        - UTF-8 encoding
        """
        # Remove signature fields before hashing
        data_copy = {k: v for k, v in data.items() 
                     if k not in ("signature", "signature_algorithm")}
        return json.dumps(data_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
    
    def sign_log(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign a log entry with RSA-PSS
        
        Args:
            log: Log entry dict to sign
            
        Returns:
            Log dict with added signature and signature_algorithm fields
        """
        if not self.private_key:
            raise AttributeError("No private key available for signing")
        
        # Get canonical JSON representation
        canonical = self._canonical_json(log)
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            canonical,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Return log with signature
        signed_log = dict(log)
        signed_log["signature"] = signature.hex()
        signed_log["signature_algorithm"] = "RSA-PSS-SHA256"
        
        return signed_log
    
    def verify_log(self, log: Dict[str, Any]) -> bool:
        """
        Verify the RSA signature on a log entry
        
        Args:
            log: Signed log entry dict
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.public_key:
            raise ValueError("No public key available for verification")
        
        # Check signature exists
        if "signature" not in log:
            return False
        
        try:
            # Get signature bytes
            signature = bytes.fromhex(log["signature"])
        except (ValueError, TypeError):
            return False
        
        # Get canonical JSON (excludes signature fields)
        canonical = self._canonical_json(log)
        
        try:
            self.public_key.verify(
                signature,
                canonical,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False
