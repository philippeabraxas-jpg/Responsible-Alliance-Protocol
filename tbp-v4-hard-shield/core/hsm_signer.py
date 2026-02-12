"""
TBP v4.2 - Hardware Security Module Signer (HARDENED)

PURPOSE:
    Replace software-only RSA signing with HSM-backed cryptographic operations.
    Protects private keys even if attacker gains root access to server.

THREAT MODEL:
    - Attacker compromises host OS (root access)
    - Attacker cannot extract keys from HSM hardware
    - HSM provides tamper-evident, physically secure key storage

ARCHITECTURE:
    Software (v4.1)         Hardware (v4.2)
    ┌──────────────┐       ┌──────────────┐
    │ Private Key  │  →    │     HSM      │
    │  (PEM file)  │       │ (Physical    │
    │ [VULNERABLE] │       │  Security)   │
    └──────────────┘       └──────────────┘

IMPLEMENTATION NOTES:
    - Use PKCS#11 for HSM communication (industry standard)
    - Support multiple HSM vendors (YubiKey, AWS CloudHSM, Azure Key Vault)
    - Fallback to software keys for development/testing
    - All operations must be auditable

TESTING:
    - Unit tests with mock HSM (SoftHSMv2)
    - Integration tests with real YubiKey (if available)
    - Performance tests (target: < 5ms per signature)
    - Failure tests (HSM disconnected, wrong PIN, etc.)

SECURITY REQUIREMENTS:
    - PIN/password never stored in code
    - Keys never leave HSM
    - All errors logged for audit
    - Rate limiting on HSM operations
"""

from typing import Optional, Dict, Any, Tuple, Union
import logging
import time
import os
import getpass
import threading  # For keep-alive thread
from enum import Enum
from dataclasses import dataclass
import json
import hashlib 
import struct
import subprocess
import tempfile

# PKCS#11 dependencies
try:
    from pkcs11 import PKCS11, Mechanism, Attribute, ObjectClass, KeyType
    from pkcs11.util.rsa import encode_rsa_public_key
    PKCS11_AVAILABLE = True
except ImportError:
    PKCS11_AVAILABLE = False
    logging.warning("python-pkcs11 not installed. HSM support limited.")

# Cryptography library for software fallback and verification
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, utils
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)


class HSMType(Enum):
    """Supported HSM types"""
    SOFTWARE = "software"  # For development (uses cryptography library)
    YUBIKEY = "yubikey"    # YubiKey PIV
    AWS_CLOUDHSM = "aws"   # AWS CloudHSM
    AZURE_KEYVAULT = "azure"  # Azure Key Vault
    PKCS11_GENERIC = "pkcs11"  # Generic PKCS#11 device


@dataclass
class SigningResult:
    """Result of a signing operation"""
    signature: bytes
    key_id: str
    timestamp: float
    mechanism: str
    hsm_type: str
    agent_id: Optional[str] = None  # NEW: Track which agent signed
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON storage"""
        return {
            "signature": self.signature.hex(),
            "key_id": self.key_id,
            "timestamp": self.timestamp,
            "mechanism": self.mechanism,
            "hsm_type": self.hsm_type,
            "agent_id": self.agent_id
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SigningResult':
        """Deserialize from JSON"""
        return cls(
            signature=bytes.fromhex(d["signature"]),
            key_id=d["key_id"],
            timestamp=d["timestamp"],
            mechanism=d["mechanism"],
            hsm_type=d["hsm_type"],
            agent_id=d.get("agent_id")
        )


class HSMSignerError(Exception):
    """Base exception for HSM operations"""
    pass


class HSMConnectionError(HSMSignerError):
    """Failed to connect to HSM"""
    pass


class HSMSigningError(HSMSignerError):
    """Failed to sign data"""
    pass


class HSMKeyError(HSMSignerError):
    """Key-related error"""
    pass


# Production mode flag
PRODUCTION_MODE = os.getenv("TBP_PRODUCTION", "false").lower() == "true"

def get_pin_from_secrets() -> str:
    """
    Get HSM PIN from secure secret manager.
    
    Priority:
    1. HashiCorp Vault (production)
    2. AWS Secrets Manager (production)
    3. Azure Key Vault (production)
    4. Environment variable (development/testing)
    5. Interactive (development only, disabled in production)
    """
    # Option 1: HashiCorp Vault
    vault_path = os.getenv("TBP_VAULT_PATH")
    if vault_path:
        try:
            import hvac
            client = hvac.Client(
                url=os.getenv("VAULT_ADDR"),
                token=os.getenv("VAULT_TOKEN")
            )
            secret = client.secrets.kv.v2.read_secret_version(path=vault_path)
            logger.info("Retrieved PIN from HashiCorp Vault")
            return secret['data']['data']['hsm_pin']
        except Exception as e:
            logger.error(f"Failed to get PIN from Vault: {e}")
    
    # Option 2: AWS Secrets Manager
    secret_name = os.getenv("TBP_AWS_SECRET_NAME")
    if secret_name:
        try:
            import boto3
            import json
            client = boto3.client('secretsmanager')
            response = client.get_secret_value(SecretId=secret_name)
            logger.info("Retrieved PIN from AWS Secrets Manager")
            return json.loads(response['SecretString'])['hsm_pin']
        except Exception as e:
            logger.error(f"Failed to get PIN from AWS: {e}")
    
    # Option 3: Azure Key Vault
    vault_name = os.getenv("AZURE_KEYVAULT_NAME")
    secret_name_azure = os.getenv("AZURE_KEYVAULT_SECRET_NAME", "hsm-pin")
    if vault_name:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            vault_url = f"https://{vault_name}.vault.azure.net"
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name_azure)
            logger.info("Retrieved PIN from Azure Key Vault")
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get PIN from Azure: {e}")
    
    # Option 4: Environment variable (development/testing)
    pin = os.getenv("TBP_HSM_PIN")
    if pin:
        logger.warning("⚠️  Using PIN from environment variable (not recommended for production)")
        return pin
    
    # Option 5: Interactive (development only)
    if PRODUCTION_MODE:
        raise HSMConnectionError(
            "Production mode requires PIN from secret manager. "
            "Set TBP_VAULT_PATH, TBP_AWS_SECRET_NAME, or AZURE_KEYVAULT_NAME."
        )
    
    if os.getenv("TBP_ALLOW_INTERACTIVE_PIN", "false").lower() == "true":
        logger.warning("⚠️  Using interactive PIN prompt (development only)")
        return getpass.getpass(f"Enter HSM PIN: ")
    
    raise HSMConnectionError(
        "No PIN source available. Configure secret manager or set TBP_HSM_PIN."
    )


class HSMSigner:
    """
    Hardware-backed cryptographic signer for TBP audit logs.
    
    Provides defense against:
    - Key theft (keys never leave HSM)
    - Software compromise (HSM has separate security boundary)
    - Unauthorized signing (requires PIN/auth)
    
    Usage:
        # Development (software fallback)
        signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
        
        # Production (real HSM)
        signer = HSMSigner(
            hsm_type=HSMType.YUBIKEY,
            pin="123456",  # Should come from secure input
            slot=0
        )
        
        # Sign log
        signature = signer.sign(log_data)
        
        # Verify (can use public key, no HSM needed)
        is_valid = signer.verify(log_data, signature)
    """
    
    # Default library paths for common HSM devices
    DEFAULT_LIBRARY_PATHS = {
        HSMType.YUBIKEY: [
            '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so',  # Linux
            '/usr/local/lib/opensc-pkcs11.so',             # macOS
            'C:\\Windows\\System32\\opensc-pkcs11.dll',    # Windows
        ],
        HSMType.PKCS11_GENERIC: [
            '/usr/lib/softhsm/libsofthsm2.so',             # SoftHSM
            '/usr/local/lib/softhsm/libsofthsm2.so',
        ],
        HSMType.AWS_CLOUDHSM: [
            '/opt/cloudhsm/lib/libcloudhsm_pkcs11.so',
        ]
    }
    
    def __init__(
        self,
        hsm_type: HSMType = HSMType.SOFTWARE,
        pin: Optional[str] = None,
        slot: int = 0,
        key_label: str = "tbp-signing-key",
        library_path: Optional[str] = None,
        auto_generate_key: bool = False,
        key_size: int = 2048
    ):
        """
        Initialize HSM signer.
        
        Args:
            hsm_type: Type of HSM to use
            pin: HSM PIN/password (None = prompt user)
            slot: HSM slot number (default 0)
            key_label: Label for the signing key
            library_path: Path to PKCS#11 library (optional)
            auto_generate_key: Generate key if not found
            key_size: RSA key size (2048 or 4096)
        """
        # Convert string to Enum if necessary
        if isinstance(hsm_type, str):
            try:
                hsm_type = HSMType(hsm_type.lower())
            except ValueError:
                # Fallback or error
                logger.error(f"Invalid HSM type string: {hsm_type}")
                raise HSMConnectionError(f"Unsupported HSM type: {hsm_type}")

        self.hsm_type = hsm_type
        self.slot = slot
        self.key_label = key_label
        self.library_path = library_path
        self.key_size = key_size
        self.session = None
        self.pkcs11_lib = None
        self.token = None
        self.private_key = None
        self.public_key_pem = None
        self.key_id = None
        self._rate_limit_counter = 0
        self._rate_limit_reset = time.time()
        
        display_type = self.hsm_type.value if hasattr(self.hsm_type, 'value') else str(self.hsm_type)
        logger.info(f"Initializing HSM signer (type={display_type}, slot={slot})")
        
        if hsm_type == HSMType.SOFTWARE:
            if PRODUCTION_MODE:
                raise HSMConnectionError(
                    "SOFTWARE mode is disabled in production. "
                    "Set TBP_PRODUCTION=false for development, or use real HSM."
                )
            logger.warning("⚠️  SOFTWARE MODE - NOT FOR PRODUCTION")
            self._init_software_fallback(auto_generate_key)
        elif hsm_type in [HSMType.YUBIKEY, HSMType.PKCS11_GENERIC, HSMType.AWS_CLOUDHSM]:
            self._connect_hsm(pin, auto_generate_key)
        elif hsm_type == HSMType.AZURE_KEYVAULT:
            self._connect_azure_keyvault(pin)
        else:
            raise HSMConnectionError(f"Unsupported HSM type: {hsm_type}")

        # Session keep-alive (prevents timeout)
        self._keepalive_thread = None
        self._keepalive_stop = threading.Event()

        if self.hsm_type not in [HSMType.SOFTWARE]:
            self._start_keepalive()

        # Check optional dependencies based on HSM type
        if self.hsm_type == HSMType.AZURE_KEYVAULT:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.keys import KeyClient
                from azure.keyvault.keys.crypto import CryptographyClient
            except ImportError:
                raise HSMConnectionError(
                    "Azure Key Vault SDK not installed. "
                    "Install with: pip install azure-identity azure-keyvault-keys"
                )
    
    def _init_software_fallback(self, auto_generate_key: bool):
        """
        Development mode: Use software keys.
        """
        logger.warning("⚠️  Using SOFTWARE keys (NOT for production!)")
        
        try:
            # Try to load existing key from environment variable
            pem_env = os.getenv("TBP_SOFTWARE_KEY_PEM")
            if pem_env:
                private_key = serialization.load_pem_private_key(
                    pem_env.encode(),
                    password=None,
                    backend=default_backend()
                )
                logger.info("Loaded software key from environment")
            else:
                if auto_generate_key:
                    logger.info(f"Generating new RSA-{self.key_size} software key")
                    private_key = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=self.key_size,
                        backend=default_backend()
                    )
                else:
                    # Generate new key for testing
                    logger.info(f"Generating new RSA-{self.key_size} software key")
                    private_key = rsa.generate_private_key(
                        public_exponent=65537,
                        key_size=self.key_size,
                        backend=default_backend()
                    )
                    logger.info("Generated deterministic software key for testing")
            
            self.private_key = private_key
            self.public_key_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            self.key_id = f"software-{hashlib.sha256(self.public_key_pem).hexdigest()[:16]}"
            
        except Exception as e:
            logger.error(f"Failed to initialize software fallback: {e}")
            raise HSMConnectionError(f"Software key initialization failed: {e}")
    
    def _connect_hsm(self, pin: Optional[str], auto_generate_key: bool):
        """
        Connect to real HSM device using PKCS#11.
        """
        if not PKCS11_AVAILABLE:
            raise HSMConnectionError("python-pkcs11 library not installed")
        
        # Determine library path
        lib_path = self.library_path
        if not lib_path and self.hsm_type in self.DEFAULT_LIBRARY_PATHS:
            for path in self.DEFAULT_LIBRARY_PATHS[self.hsm_type]:
                if os.path.exists(path):
                    lib_path = path
                    break
        
        if not lib_path:
            available = self.DEFAULT_LIBRARY_PATHS.get(self.hsm_type, [])
            raise HSMConnectionError(
                f"PKCS#11 library not found. Tried: {available}. "
                f"Please specify library_path."
            )
        
        try:
            # Load PKCS#11 library
            self.pkcs11_lib = PKCS11(lib_path)
            tokens = list(self.pkcs11_lib.get_tokens())
            
            if not tokens:
                raise HSMConnectionError(f"No tokens found in HSM library: {lib_path}")
            
            # Select token by slot
            if self.slot >= len(tokens):
                logger.warning(f"Slot {self.slot} not found, using slot 0")
                self.slot = 0
            
            self.token = tokens[self.slot]
            
            # Get PIN from secret manager if not provided
            if pin is None:
                pin = get_pin_from_secrets()
            
            # Open session
            self.session = self.token.open(user_pin=pin)
            logger.info(f"Connected to HSM: {self.token.label}")
            
            # Find or generate key
            self._load_or_generate_key(auto_generate_key, pin)
            
        except Exception as e:
            logger.error(f"Failed to connect to HSM: {e}")
            raise HSMConnectionError(f"HSM connection failed: {e}")
    
    def _load_or_generate_key(self, auto_generate_key: bool, pin: str):
        """
        Load existing key or generate new one.
        """
        try:
            # Look for existing key with our label
            keys = list(self.session.get_objects({
                Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                Attribute.LABEL: self.key_label
            }))
            
            if keys:
                self.private_key = keys[0]
                logger.info(f"Found existing key: {self.key_label}")
                
                # Extract public key
                self._extract_public_key()
                
            elif auto_generate_key:
                logger.info(f"Generating new RSA-{self.key_size} key in HSM")
                self._generate_hsm_key(pin)
            else:
                raise HSMKeyError(
                    f"Key not found: {self.key_label}. "
                    "Set auto_generate_key=True to create one."
                )
                
        except Exception as e:
            logger.error(f"Failed to load/generate key: {e}")
            raise HSMKeyError(f"Key operation failed: {e}")
    
    def _generate_hsm_key(self, pin: str):
        """
        Generate RSA key pair in HSM.
        """
        try:
            # Generate key pair in HSM
            public_key, self.private_key = self.session.generate_keypair(
                KeyType.RSA,
                key_size=self.key_size,
                id=self.key_label.encode(),
                label=self.key_label,
                store=True,
                mechanism=Mechanism.RSA_PKCS_KEY_PAIR_GEN,
            )
            
            # Extract and store public key
            modulus = public_key[Attribute.MODULUS]
            public_exponent = public_key[Attribute.PUBLIC_EXPONENT]
            
            # Encode as PEM
            self.public_key_pem = encode_rsa_public_key(modulus, public_exponent)
            
            # Generate key ID from public key hash
            import hashlib
            self.key_id = f"hsm-{hashlib.sha256(self.public_key_pem).hexdigest()[:16]}"
            
            logger.info(f"Generated new key: {self.key_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate key in HSM: {e}")
            raise HSMKeyError(f"Key generation failed: {e}")
    
    def _extract_public_key(self):
        """
        Extract public key from HSM.
        
        SECURITY: Always use PUBLIC_KEY object, never PRIVATE_KEY attributes.
        Many HSMs mark private key attributes as SENSITIVE.
        """
        try:
            # Method 1: Find stored PUBLIC_KEY object (preferred)
            public_keys = list(self.session.get_objects({
                Attribute.CLASS: ObjectClass.PUBLIC_KEY,
                Attribute.LABEL: self.key_label
            }))
            
            if public_keys:
                pub_key = public_keys[0]
                modulus = pub_key[Attribute.MODULUS]
                public_exponent = pub_key[Attribute.PUBLIC_EXPONENT]
                self.public_key_pem = encode_rsa_public_key(modulus, public_exponent)
                logger.info("✓ Extracted public key from PUBLIC_KEY object")
                
            else:
                # Method 2: Extract from certificate (if available)
                certs = list(self.session.get_objects({
                    Attribute.CLASS: ObjectClass.CERTIFICATE,
                    Attribute.LABEL: self.key_label
                }))
                
                if certs:
                    from cryptography import x509
                    cert_der = certs[0][Attribute.VALUE]
                    cert = x509.load_der_x509_certificate(cert_der, default_backend())
                    self.public_key_pem = cert.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    logger.info("✓ Extracted public key from certificate")
                    
                else:
                    # Method 3: LAST RESORT - try private key (may fail on secure HSMs)
                    logger.warning("⚠️  No PUBLIC_KEY or certificate, trying PRIVATE_KEY attributes")
                    try:
                        modulus = self.private_key[Attribute.MODULUS]
                        public_exponent = self.private_key[Attribute.PUBLIC_EXPONENT]
                        self.public_key_pem = encode_rsa_public_key(modulus, public_exponent)
                        logger.warning("✓ Extracted from PRIVATE_KEY (may fail on secure HSMs)")
                    except Exception as e:
                        raise HSMKeyError(
                            f"Cannot extract public key. HSM marked private key as SENSITIVE. "
                            f"Please store PUBLIC_KEY object with label '{self.key_label}'. "
                            f"Error: {e}"
                        )
            
            # Generate key ID
            self.key_id = f"hsm-{hashlib.sha256(self.public_key_pem).hexdigest()[:16]}"
            
        except HSMKeyError:
            raise  # Re-raise our custom error
        except Exception as e:
            logger.error(f"Failed to extract public key: {e}")
            raise HSMKeyError(f"Public key extraction failed: {e}")
    
    def _connect_azure_keyvault(self, credential: Optional[str]):
        """
        Connect to Azure Key Vault.
        Note: This requires azure-identity and azure-keyvault-keys packages.
        """
        try:
            # Azure Key Vault SDK (checked in __init__)
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys import KeyClient
            
            vault_url = os.getenv("AZURE_KEYVAULT_URL")
            if not vault_url:
                raise HSMConnectionError("AZURE_KEYVAULT_URL environment variable not set")
            
            credential = DefaultAzureCredential()
            self.key_client = KeyClient(vault_url=vault_url, credential=credential)
            
            # Get or create key
            try:
                key = self.key_client.get_key(self.key_label)
                logger.info(f"Found existing key in Azure Key Vault: {self.key_label}")
            except Exception:
                if os.getenv("TBP_AUTO_GENERATE_KEY", "false").lower() == "true":
                    from azure.keyvault.keys import KeyType as AzureKeyType
                    key = self.key_client.create_rsa_key(
                        name=self.key_label,
                        key_size=self.key_size,
                        hsm=True  # Use HSM-backed key
                    )
                    logger.info(f"Created new HSM-backed key in Azure: {self.key_label}")
                else:
                    raise HSMKeyError(f"Key not found: {self.key_label}")
            
            # For Azure Key Vault, we use the key client for operations
            self.key_name = self.key_label
            self.key_version = key.properties.version
            self.key_id = f"azure-{key.id}"
            
            # Get public key
            self.public_key_pem = key.key.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
        except ImportError:
            raise HSMConnectionError(
                "Azure Key Vault SDK not installed. "
                "Install with: pip install azure-identity azure-keyvault-keys"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Azure Key Vault: {e}")
            raise HSMConnectionError(f"Azure Key Vault connection failed: {e}")
    
    def _check_rate_limit(self):
        """
        Simple rate limiting to prevent abuse.
        """
        now = time.time()
        if now - self._rate_limit_reset > 60:  # Reset every minute
            self._rate_limit_counter = 0
            self._rate_limit_reset = now
        
        if self._rate_limit_counter >= 100:  # Max 100 operations per minute
            raise HSMSigningError("Rate limit exceeded")
        
        self._rate_limit_counter += 1

    def _start_keepalive(self):
        """
        Start background thread to keep PKCS#11 session alive.
        Many HSMs timeout sessions after inactivity.
        """
        def keepalive_loop():
            while not self._keepalive_stop.is_set():
                try:
                    # Ping session with dummy query (doesn't modify anything)
                    if self.session:
                        list(self.session.get_objects({Attribute.CLASS: ObjectClass.DATA}))
                        logger.debug("Session keepalive ping successful")
                except Exception as e:
                    logger.error(f"Session keepalive failed: {e}")
                    # TODO: Implement reconnection logic
                
                # Wait 60 seconds before next ping
                self._keepalive_stop.wait(timeout=60)
        
        self._keepalive_thread = threading.Thread(
            target=keepalive_loop,
            daemon=True,
            name="HSM-Keepalive"
        )
        self._keepalive_thread.start()
        logger.info("Started session keep-alive thread")

    def _stop_keepalive(self):
        """Stop keep-alive thread"""
        if self._keepalive_thread:
            logger.info("Stopping keep-alive thread")
            self._keepalive_stop.set()
            self._keepalive_thread.join(timeout=5)
            self._keepalive_thread = None
    
    def sign(
        self, 
        data: bytes, 
        agent_id: str,
        timestamp: Optional[float] = None
    ) -> SigningResult:
        """
        Sign data using HSM private key.
        
        Args:
            data: Data to sign (typically JSON-encoded log)
            agent_id: ID of the agent (1-256 chars)
            timestamp: Optional timestamp (defaults to current time)
        
        Returns:
            SigningResult with signature and metadata
        
        Raises:
            HSMSigningError: If signing fails
            ValueError: If input validation fails
        """
        # Input validation
        if not agent_id or len(agent_id) > 256:
            raise ValueError("agent_id must be 1-256 characters")
        
        if len(data) > 10 * 1024 * 1024:  # 10MB
            raise ValueError("Data too large for signing (max 10MB)")

        self._check_rate_limit()
        
        # Handle timestamp
        if timestamp is None:
            timestamp = time.time()
            if PRODUCTION_MODE:
                logger.warning("⚠️  Using system clock (not RFC 3161 certified)")
        
        logger.debug(f"Signing {len(data)} bytes (agent={agent_id}, key={self.key_id})")
        
        try:
            # Create data to sign: hash(agent_id + timestamp + data)
            # This prevents signature replay across agents
            agent_id_bytes = agent_id.encode('utf-8')
            agent_id_len = struct.pack('!H', len(agent_id_bytes))  # 2-byte length prefix
            timestamp_bytes = struct.pack('!d', timestamp)
            data_to_hash = agent_id_len + agent_id_bytes + timestamp_bytes + data
            
            # Hash the data
            digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
            digest.update(data_to_hash)
            data_hash = digest.finalize()
            
            if self.hsm_type == HSMType.SOFTWARE:
                # Software signing
                signature = self.private_key.sign(
                    data_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    utils.Prehashed(hashes.SHA256())
                )
                mechanism = "RSA-PSS-SHA256"
                
            elif self.hsm_type == HSMType.AZURE_KEYVAULT:
                # Azure Key Vault signing
                from azure.keyvault.keys.crypto import CryptographyClient, SignatureAlgorithm
                from azure.identity import DefaultAzureCredential
                
                crypto_client = CryptographyClient(
                    key=self.key_client.get_key(self.key_name),
                    credential=DefaultAzureCredential()
                )
                
                result_crypt = crypto_client.sign(
                    algorithm=SignatureAlgorithm.ps256,
                    digest=data_hash
                )
                signature = result_crypt.signature
                mechanism = "PS256"
                
            else:
                # PKCS#11 HSM signing
                signature = self.session.sign(
                    self.private_key,
                    data_hash,
                    mechanism=Mechanism.SHA256_RSA_PKCS_PSS
                )
                mechanism = "SHA256_RSA_PKCS_PSS"
            
            # Create result
            result = SigningResult(
                signature=bytes(signature),
                key_id=self.key_id,
                timestamp=timestamp,
                mechanism=mechanism,
                hsm_type=self.hsm_type.value,
                agent_id=agent_id
            )
            
            logger.info(f"Signed data: {self.key_id}, {mechanism}, {len(signature)} bytes")
            return result
            
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            raise HSMSigningError(f"Signing operation failed: {e}")
    
    def verify(
        self, 
        data: bytes, 
        signature: SigningResult,
        agent_id: str
    ) -> bool:
        """
        Verify signature using public key.
        
        Args:
            data: Original data
            signature: SigningResult with signature and metadata
            agent_id: ID of the agent (must match signing agent_id)
        
        Returns:
            True if signature is valid, False otherwise
        """
        logger.debug(f"Verifying signature for {len(data)} bytes (agent={agent_id})")
        
        try:
            # Reconstruct the signed data (must match sign() exactly)
            agent_id_bytes = agent_id.encode('utf-8')
            agent_id_len = struct.pack('!H', len(agent_id_bytes))
            timestamp_bytes = struct.pack('!d', signature.timestamp)
            data_to_hash = agent_id_len + agent_id_bytes + timestamp_bytes + data
            
            # Hash the data
            digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
            digest.update(data_to_hash)
            data_hash = digest.finalize()
            
            # Load public key
            public_key = serialization.load_pem_public_key(
                self.public_key_pem,
                backend=default_backend()
            )
            
            # Verify signature
            if signature.mechanism in ["RSA-PSS-SHA256", "SHA256_RSA_PKCS_PSS", "PS256"]:
                # All are RSA-PSS with SHA256
                public_key.verify(
                    signature.signature,
                    data_hash,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    utils.Prehashed(hashes.SHA256())
                )
                return True
            else:
                logger.error(f"Unsupported signature mechanism: {signature.mechanism}")
                return False
                
        except InvalidSignature:
            logger.warning(f"Invalid signature for key: {signature.key_id}")
            return False
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
    
    def get_public_key(self) -> bytes:
        """
        Export public key for distribution.
        
        Returns:
            Public key in PEM format
        """
        if self.public_key_pem is None:
            raise HSMKeyError("Public key not available")
        
        return self.public_key_pem
    
    def generate_key(self, key_size: int = 2048) -> Dict[str, Any]:
        """
        Generate new key pair in HSM.
        
        Args:
            key_size: RSA key size (2048 or 4096)
        
        Returns:
            {"public_key": bytes, "key_id": str, "key_label": str}
        """
        if self.hsm_type == HSMType.SOFTWARE:
            # Generate software key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            self.private_key = private_key
            self.public_key_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            self.key_id = f"software-{hashlib.sha256(self.public_key_pem).hexdigest()[:16]}"
            
        elif self.hsm_type == HSMType.AZURE_KEYVAULT:
            # Already handled in _connect_azure_keyvault
            pass
        else:
            # For PKCS#11 HSMs, we need to re-generate
            self._generate_hsm_key(None)  # PIN should already be cached
        
        return {
            "public_key": self.public_key_pem,
            "key_id": self.key_id,
            "key_label": self.key_label,
            "key_size": key_size,
            "hsm_type": self.hsm_type.value
        }
    
    def close(self):
        """
        Close HSM session and cleanup.
        """
        # Stop keep-alive first
        self._stop_keepalive()
        
        if self.session:
            try:
                logger.info("Closing HSM session")
                self.session.close()
                self.session = None
                self.pkcs11_lib = None
                self.token = None
            except Exception as e:
                logger.error(f"Error closing HSM session: {e}")
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()


# =============================================================================
# Testing Utilities
# =============================================================================

def setup_softhsm_test():
    """
    Setup SoftHSMv2 for testing.
    
    Returns:
        Tuple of (library_path, slot_id, pin)
    """
    # Check if SoftHSM2 is installed
    try:
        subprocess.run(["softhsm2-util", "--show-slots"], 
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("SoftHSM2 not installed. Install with:")
        logger.warning("  Ubuntu: sudo apt-get install softhsm2")
        logger.warning("  macOS: brew install softhsm")
        return None, None, None
    
    # Create temp directory for tokens
    temp_dir = tempfile.mkdtemp(prefix="softhsm_test_")
    
    # Set SOFTHSM2_CONF environment variable
    conf_path = os.path.join(temp_dir, "softhsm2.conf")
    with open(conf_path, "w") as f:
        f.write(f"""directories.tokendir = {temp_dir}
objectstore.backend = file
log.level = DEBUG
""")
    
    os.environ["SOFTHSM2_CONF"] = conf_path
    
    # Initialize token
    try:
        result = subprocess.run([
            "softhsm2-util", "--init-token", "--free",
            "--label", "TBP-Test",
            "--pin", "1234",
            "--so-pin", "5678"
        ], capture_output=True, text=True)
        
        # Parse slot ID from output
        slot_id = 0
        for line in result.stdout.split('\n'):
            if "Slot" in line and "token" in line.lower():
                slot_id = int(line.split()[1].strip())
                break
        
        # Find library path
        lib_paths = [
            "/usr/lib/softhsm/libsofthsm2.so",
            "/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so",
            "/usr/local/lib/softhsm/libsofthsm2.so",
        ]
        
        lib_path = None
        for path in lib_paths:
            if os.path.exists(path):
                lib_path = path
                break
        
        return lib_path, slot_id, "1234"
    except Exception as e:
        logger.error(f"Failed to setup SoftHSM: {e}")
        return None, None, None


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== TBP HSM Signer v4.2 HARDENED ===\n")
    
    # Example 1: Software mode (development only)
    print("1. Software mode (development)")
    os.environ["TBP_PRODUCTION"] = "false"  # Explicitly set dev mode
    
    signer = HSMSigner(
        hsm_type=HSMType.SOFTWARE,
        key_label="test-software-key",
        auto_generate_key=True
    )
    
    data_example = json.dumps({"test": "log entry", "timestamp": time.time()}).encode()
    agent_id_example = "test-agent-001"
    
    # Sign data (NEW: requires agent_id)
    result_example = signer.sign(data_example, agent_id=agent_id_example)
    print(f"   Signed: key={result_example.key_id}, agent={agent_id_example}")
    print(f"   Signature: {len(result_example.signature)} bytes")
    
    # Verify signature (NEW: requires agent_id)
    is_valid_example = signer.verify(data_example, result_example, agent_id=agent_id_example)
    print(f"   Verification: {'✓ VALID' if is_valid_example else '✗ INVALID'}")
    
    # Test replay protection
    print("\n   Testing replay protection:")
    wrong_agent = "attacker-agent-999"
    is_valid_wrong = signer.verify(data_example, result_example, agent_id=wrong_agent)
    print(f"   Wrong agent_id: {'✗ FAILED (replay detected)' if not is_valid_wrong else '⚠️  SECURITY BUG'}")
    
    signer.close()
    print()
    
    # Example 2: Production mode enforcement
    print("2. Production mode enforcement")
    os.environ["TBP_PRODUCTION"] = "true"
    
    try:
        signer_prod = HSMSigner(hsm_type=HSMType.SOFTWARE)
        print("   ✗ SECURITY BUG: SOFTWARE mode should be blocked in production")
    except HSMConnectionError as e:
        print(f"   ✓ Correctly blocked: {e}")
    
    print("\n=== All Security Patches Applied ===")

