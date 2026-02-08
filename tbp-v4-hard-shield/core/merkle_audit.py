"""
TBP v4.2 - Merkle Tree Audit Chain

PURPOSE:
    Create tamper-evident audit trail for TBP decisions.
    Even if attacker gains access, cannot modify past logs without detection.

THREAT MODEL:
    - Attacker modifies historical logs
    - Attacker deletes inconvenient logs
    - Attacker tries to forge audit trail

PROTECTION:
    ✅ Each log entry includes hash of previous entry (blockchain-style)
    ✅ All hashes combined into Merkle tree root
    ✅ Root published publicly (can't be changed without detection)
    ✅ Anyone can verify integrity with just the root hash

ARCHITECTURE:
    
    Log Entry 1       Log Entry 2       Log Entry 3
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │ Data    │      │ Data    │      │ Data    │
    │ Hash    │─────▶│ Prev    │─────▶│ Prev    │
    │ Sign    │      │ Hash    │      │ Hash    │
    └────┬────┘      │ Sign    │      │ Sign    │
         │           └────┬────┘      └────┬────┘
         │                │                │
         └────────┬───────┴────────┬───────┘
                  │                │
             ┌────▼────┐      ┌────▼────┐
             │ Hash 1-2│      │ Hash 3  │
             └────┬────┘      └────┬────┘
                  │                │
                  └────────┬───────┘
                           │
                      ┌────▼────┐
                      │ Root    │  ← Published publicly
                      │ Hash    │
                      └─────────┘

BENEFITS:
    1. Tamper Detection: Changing any log invalidates all subsequent hashes
    2. Deletion Detection: Missing entry breaks chain
    3. Public Verification: Anyone can verify integrity
    4. Efficient: Only need root hash to verify tree integrity

TODO (Caetano):
    1. Implement MerkleTree class
    2. Implement chain linking (prev_hash)
    3. Implement root computation
    4. Implement verification
    5. Add persistence (store to disk/database)
    6. Write tests (tests/test_merkle_audit.py)

TESTING:
    - Create chain of 1000 entries
    - Attempt to modify entry #500 → should detect
    - Attempt to delete entry #500 → should detect
    - Verify entire chain integrity → should pass
    - Performance: target < 1ms per entry
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MerkleTreeError(Exception):
    """Base exception for Merkle tree operations"""
    pass


class ChainIntegrityError(MerkleTreeError):
    """Chain integrity violated (tampering detected)"""
    pass


class AuditEntry:
    """
    Single entry in the audit chain.
    
    Each entry contains:
    - The actual log data
    - Hash of previous entry (chain linking)
    - Its own hash
    - Timestamp
    - Signature (from HSM)
    """
    
    def __init__(
        self,
        data: Dict[str, Any],
        previous_hash: Optional[str] = None,
        signature: Optional[bytes] = None
    ):
        """
        Create new audit entry.
        
        Args:
            data: Log data (decision, agent_id, timestamp, etc.)
            previous_hash: Hash of previous entry (None for genesis)
            signature: HSM signature of this entry
        
        TODO (Caetano):
            1. Store data, previous_hash, signature
            2. Compute own hash (compute_hash method)
            3. Add timestamp
        """
        self.data = data
        self.previous_hash = previous_hash or "0" * 64  # Genesis
        self.signature = signature
        self.timestamp = datetime.utcnow().isoformat()
        self.hash = self.compute_hash()
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of this entry.
        
        Hash includes:
        - Entry data (canonical JSON)
        - Previous entry hash
        - Timestamp
        
        Returns:
            Hex-encoded SHA-256 hash
        
        TODO (Caetano):
            1. Create canonical representation (sorted JSON)
            2. Include previous_hash
            3. Include timestamp
            4. Compute SHA-256
            5. Return hex string
        
        Example:
            canonical = {
                "data": sorted_json(self.data),
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp
            }
            hash_input = json.dumps(canonical, sort_keys=True)
            return hashlib.sha256(hash_input.encode()).hexdigest()
        """
        # TODO: Implement hash computation
        return "0" * 64  # Placeholder
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize entry to dictionary"""
        return {
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "timestamp": self.timestamp,
            "signature": self.signature.hex() if self.signature else None
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'AuditEntry':
        """Deserialize entry from dictionary"""
        entry = cls(
            data=d["data"],
            previous_hash=d["previous_hash"],
            signature=bytes.fromhex(d["signature"]) if d.get("signature") else None
        )
        entry.timestamp = d["timestamp"]
        entry.hash = d["hash"]
        return entry


class MerkleAuditChain:
    """
    Tamper-evident audit chain for TBP.
    
    Features:
    - Chain linking (each entry references previous)
    - Merkle tree (efficient integrity verification)
    - Public root (anyone can verify)
    - Incremental updates (don't recompute entire tree)
    
    Usage:
        # Create chain
        chain = MerkleAuditChain()
        
        # Add entries
        chain.append({"agent_id": "bot-001", "allowed": False})
        chain.append({"agent_id": "bot-002", "allowed": True})
        
        # Get root hash (publish this publicly)
        root = chain.get_root()
        
        # Verify integrity
        assert chain.verify_integrity()
        
        # Detect tampering
        chain.entries[0].data["allowed"] = True  # Attacker modifies
        assert not chain.verify_integrity()  # Detected!
    """
    
    def __init__(self):
        """
        Initialize empty audit chain.
        
        TODO (Caetano):
            1. Initialize empty entries list
            2. Set genesis hash
            3. Initialize Merkle tree
        """
        self.entries: List[AuditEntry] = []
        self.merkle_tree: Optional['MerkleTree'] = None
        logger.info("Initialized Merkle audit chain")
    
    def append(self, data: Dict[str, Any], signature: Optional[bytes] = None):
        """
        Append new entry to chain.
        
        Args:
            data: Log data
            signature: HSM signature (optional)
        
        TODO (Caetano):
            1. Get hash of last entry (or genesis if empty)
            2. Create new AuditEntry with previous_hash
            3. Append to entries list
            4. Update Merkle tree
            5. Log operation
        """
        # Get previous hash
        previous_hash = self.entries[-1].hash if self.entries else None
        
        # Create entry
        entry = AuditEntry(data, previous_hash, signature)
        
        # TODO: Add to chain and update Merkle tree
        self.entries.append(entry)
        logger.debug(f"Added entry #{len(self.entries)}: {entry.hash[:8]}...")
    
    def verify_integrity(self) -> bool:
        """
        Verify entire chain integrity.
        
        Checks:
        1. Each entry's hash is correct
        2. Each entry's previous_hash matches actual previous
        3. Merkle tree root is correct
        
        Returns:
            True if chain is intact, False if tampered
        
        TODO (Caetano):
            1. Iterate through entries
            2. Recompute each hash, compare to stored
            3. Verify previous_hash linkage
            4. Recompute Merkle root, compare to stored
            5. Return True only if ALL checks pass
        """
        if not self.entries:
            return True
        
        # TODO: Implement integrity verification
        logger.info("Verifying chain integrity...")
        
        # Check chain linkage
        for i, entry in enumerate(self.entries):
            # Verify hash
            computed_hash = entry.compute_hash()
            if computed_hash != entry.hash:
                logger.error(f"Entry #{i} hash mismatch")
                return False
            
            # Verify chain linkage
            if i > 0:
                expected_prev = self.entries[i-1].hash
                if entry.previous_hash != expected_prev:
                    logger.error(f"Entry #{i} chain broken")
                    return False
        
        logger.info("✅ Chain integrity verified")
        return True
    
    def get_root(self) -> str:
        """
        Get Merkle tree root hash.
        
        This is the single hash that represents entire chain.
        Publish this publicly for verification.
        
        Returns:
            Hex-encoded root hash
        
        TODO (Caetano):
            1. Build Merkle tree from all entry hashes
            2. Return root hash
        """
        if not self.entries:
            return "0" * 64
        
        # TODO: Compute Merkle root
        return "0" * 64  # Placeholder
    
    def get_proof(self, index: int) -> List[str]:
        """
        Get Merkle proof for specific entry.
        
        Proof allows verifying single entry without entire chain.
        
        Args:
            index: Entry index
        
        Returns:
            List of hashes forming Merkle proof
        
        TODO (Caetano):
            1. Get path from entry to root
            2. Collect sibling hashes
            3. Return proof
        
        Usage:
            # Auditor wants to verify entry #500
            proof = chain.get_proof(500)
            # Auditor can now verify entry with just proof + root
        """
        # TODO: Implement Merkle proof generation
        return []
    
    def verify_proof(self, entry: AuditEntry, proof: List[str], root: str) -> bool:
        """
        Verify Merkle proof for entry.
        
        Args:
            entry: Entry to verify
            proof: Merkle proof (from get_proof)
            root: Published root hash
        
        Returns:
            True if entry is in tree with this root
        
        TODO (Caetano):
            1. Start with entry hash
            2. Compute path up tree using proof
            3. Compare computed root to provided root
            4. Return True if match
        """
        # TODO: Implement proof verification
        return False
    
    def save(self, filepath: str):
        """
        Save chain to file.
        
        TODO (Caetano):
            1. Serialize all entries
            2. Write to JSON file
            3. Log save operation
        """
        # TODO: Implement persistence
        pass
    
    def load(self, filepath: str):
        """
        Load chain from file.
        
        TODO (Caetano):
            1. Read JSON file
            2. Deserialize entries
            3. Verify integrity after load
            4. Log load operation
        """
        # TODO: Implement loading
        pass


class MerkleTree:
    """
    Merkle tree implementation.
    
    Binary tree where:
    - Leaves = entry hashes
    - Internal nodes = hash of children
    - Root = single hash representing all leaves
    
    TODO (Caetano):
        1. Build tree from list of hashes
        2. Compute root hash
        3. Generate proofs
        4. Verify proofs
    
    Resources:
        - https://en.wikipedia.org/wiki/Merkle_tree
        - https://brilliant.org/wiki/merkle-tree/
    """
    
    def __init__(self, leaves: List[str]):
        """
        Build Merkle tree from leaf hashes.
        
        Args:
            leaves: List of hex-encoded hashes
        
        TODO (Caetano):
            1. Pad leaves to power of 2 (duplicate last if needed)
            2. Build tree bottom-up
            3. Store tree structure
        """
        self.leaves = leaves
        self.tree = []
        self.root = self._build_tree()
    
    def _build_tree(self) -> str:
        """
        Build Merkle tree bottom-up.
        
        Algorithm:
            1. Start with leaves as level 0
            2. For each pair of nodes, compute parent hash
            3. Repeat until single root node
        
        Returns:
            Root hash
        
        TODO (Caetano):
            Implement tree building algorithm
        """
        # TODO: Implement tree building
        return "0" * 64  # Placeholder
    
    def _hash_pair(self, left: str, right: str) -> str:
        """
        Hash two child hashes to create parent.
        
        Args:
            left: Left child hash
            right: Right child hash
        
        Returns:
            Parent hash
        
        TODO (Caetano):
            return hashlib.sha256((left + right).encode()).hexdigest()
        """
        # TODO: Implement pair hashing
        return "0" * 64


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=== Merkle Audit Chain Demo ===\n")
    
    # Create chain
    chain = MerkleAuditChain()
    
    # Add some entries
    print("Adding entries...")
    chain.append({"agent": "bot-001", "action": "trade", "allowed": False})
    chain.append({"agent": "bot-002", "action": "transfer", "allowed": True})
    chain.append({"agent": "bot-003", "action": "read", "allowed": True})
    
    # Get root
    root = chain.get_root()
    print(f"Root hash: {root[:16]}...")
    
    # Verify integrity
    print(f"\nIntegrity check: {chain.verify_integrity()}")
    
    # Simulate tampering
    print("\n⚠️  Simulating tampering...")
    # chain.entries[1].data["allowed"] = False  # Attacker changes log
    # print(f"Integrity check after tampering: {chain.verify_integrity()}")
    
    print("\n⚠️  Implementation pending. See TODO comments above.")
