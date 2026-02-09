"""
Tests for merkle_audit.py - Tamper-Evident Audit Chain

Test coverage:
- Entry creation and hashing
- Chain linking
- Merkle tree construction
- Tampering detection
- Persistence (save/load)
- Merkle proofs
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta

from core.merkle_audit import (
    AuditEntry,
    MerkleTree,
    MerkleAuditChain,
    MerkleTreeError,
    ChainIntegrityError
)


class TestAuditEntry:
    """Tests for AuditEntry class"""
    
    def test_entry_creation(self):
        """Test creating basic entry"""
        data = {"agent": "bot-001", "action": "trade"}
        entry = AuditEntry(data)
        
        assert entry.data == data
        assert entry.previous_hash == "0" * 64  # Genesis
        assert entry.hash is not None
        assert len(entry.hash) == 64  # SHA-256 hex
        assert entry.timestamp.tzinfo is not None  # UTC aware
    
    def test_hash_deterministic(self):
        """Test hash is deterministic"""
        data = {"agent": "bot-001", "action": "trade"}
        
        entry1 = AuditEntry(data, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
        entry2 = AuditEntry(data, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
        
        # Same data + timestamp = same hash
        assert entry1.hash == entry2.hash
    
    def test_hash_changes_with_data(self):
        """Test hash changes when data changes"""
        entry1 = AuditEntry({"value": 1})
        entry2 = AuditEntry({"value": 2})
        
        assert entry1.hash != entry2.hash
    
    def test_hash_includes_previous(self):
        """Test hash includes previous_hash"""
        data = {"test": "data"}
        
        entry1 = AuditEntry(data, previous_hash="abc")
        entry2 = AuditEntry(data, previous_hash="def")
        
        assert entry1.hash != entry2.hash
    
    def test_signature_not_in_hash(self):
        """
        CRITICAL TEST (Gemini's fix):
        Signature should NOT be included in hash computation.
        """
        data = {"test": "data"}
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        
        # Entry without signature
        entry1 = AuditEntry(data, timestamp=timestamp)
        hash_without_sig = entry1.hash
        
        # Entry with signature
        entry2 = AuditEntry(data, timestamp=timestamp, signature=b"fake_signature")
        hash_with_sig = entry2.hash
        
        # Hashes should be IDENTICAL (signature not in hash)
        assert hash_without_sig == hash_with_sig
    
    def test_verify_hash(self):
        """Test hash verification"""
        entry = AuditEntry({"test": "data"})
        
        assert entry.verify_hash() == True
        
        # Corrupt hash
        entry.hash = "corrupted"
        assert entry.verify_hash() == False
    
    def test_serialization(self):
        """Test to_dict / from_dict"""
        original = AuditEntry(
            {"agent": "bot-001", "action": "trade"},
            previous_hash="abc123",
            signature=b"fake_sig"
        )
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = AuditEntry.from_dict(data)
        
        assert restored.data == original.data
        assert restored.previous_hash == original.previous_hash
        assert restored.hash == original.hash
        assert restored.signature == original.signature


class TestMerkleTree:
    """Tests for MerkleTree class"""
    
    def test_single_leaf(self):
        """Test tree with single leaf"""
        tree = MerkleTree(["abc123"])
        
        assert tree.get_root() == "abc123"
    
    def test_two_leaves(self):
        """Test tree with two leaves"""
        tree = MerkleTree(["aaa", "bbb"])
        
        root = tree.get_root()
        assert root is not None
        assert len(root) == 64  # SHA-256 hex
    
    def test_odd_leaves(self):
        """
        Test tree with odd number of leaves.
        Gemini's fix: Should duplicate last leaf.
        """
        tree = MerkleTree(["aaa", "bbb", "ccc"])
        
        # Should not crash (duplicates "ccc")
        root = tree.get_root()
        assert root is not None
    
    def test_merkle_proof(self):
        """Test Merkle proof generation"""
        leaves = ["aaa", "bbb", "ccc", "ddd"]
        tree = MerkleTree(leaves)
        
        # Get proof for leaf 1
        proof = tree.get_proof(1)
        
        # Proof should have entries (one per level)
        assert len(proof) > 0
        
        # Verify proof
        root = tree.get_root()
        is_valid = tree.verify_proof(leaves[1], proof, root)
        assert is_valid == True
    
    def test_proof_verification_fails_wrong_leaf(self):
        """Test proof verification fails for wrong leaf"""
        leaves = ["aaa", "bbb", "ccc", "ddd"]
        tree = MerkleTree(leaves)
        
        proof = tree.get_proof(1)
        root = tree.get_root()
        
        # Try to verify wrong leaf with this proof
        wrong_leaf = "zzz"
        is_valid = tree.verify_proof(wrong_leaf, proof, root)
        assert is_valid == False


class TestMerkleAuditChain:
    """Tests for MerkleAuditChain"""
    
    def test_chain_creation(self):
        """Test creating empty chain"""
        chain = MerkleAuditChain()
        
        assert len(chain) == 0
        assert chain.get_root() == "0" * 64
    
    def test_append_entry(self):
        """Test appending entry"""
        chain = MerkleAuditChain()
        
        data = {"agent": "bot-001", "action": "trade"}
        entry_hash = chain.append(data)
        
        assert len(chain) == 1
        assert entry_hash == chain.entries[0].hash
    
    def test_chain_linking(self):
        """Test entries are linked"""
        chain = MerkleAuditChain()
        
        chain.append({"entry": 1})
        chain.append({"entry": 2})
        chain.append({"entry": 3})
        
        # Each entry should reference previous
        assert chain.entries[0].previous_hash == "0" * 64  # Genesis
        assert chain.entries[1].previous_hash == chain.entries[0].hash
        assert chain.entries[2].previous_hash == chain.entries[1].hash
    
    def test_merkle_root_updates(self):
        """Test Merkle root updates after append"""
        chain = MerkleAuditChain()
        
        root1 = chain.get_root()
        
        chain.append({"entry": 1})
        root2 = chain.get_root()
        
        chain.append({"entry": 2})
        root3 = chain.get_root()
        
        # Each root should be different
        assert root1 != root2
        assert root2 != root3
    
    def test_verify_integrity_empty(self):
        """Test verification of empty chain"""
        chain = MerkleAuditChain()
        
        is_valid, errors = chain.verify_integrity()
        assert is_valid == True
        assert len(errors) == 0
    
    def test_verify_integrity_valid(self):
        """Test verification of valid chain"""
        chain = MerkleAuditChain()
        
        for i in range(5):
            chain.append({"entry": i})
        
        is_valid, errors = chain.verify_integrity()
        assert is_valid == True
        assert len(errors) == 0
    
    def test_detect_data_tampering(self):
        """Test detection of data tampering"""
        chain = MerkleAuditChain()
        
        chain.append({"value": 100})
        chain.append({"value": 200})
        
        # Tamper with data
        chain.entries[0].data["value"] = 999
        
        # Should detect
        is_valid, errors = chain.verify_integrity()
        assert is_valid == False
        assert len(errors) > 0
    
    def test_detect_chain_break(self):
        """Test detection of broken chain link"""
        chain = MerkleAuditChain()
        
        chain.append({"entry": 1})
        chain.append({"entry": 2})
        chain.append({"entry": 3})
        
        # Break chain
        chain.entries[2].previous_hash = "corrupted"
        
        # Should detect
        is_valid, errors = chain.verify_integrity()
        assert is_valid == False
        assert any("chain break" in e.lower() for e in errors)
    
    def test_detect_merkle_root_mismatch(self):
        """Test detection of Merkle root manipulation"""
        chain = MerkleAuditChain()
        
        for i in range(3):
            chain.append({"entry": i})
        
        # Manually corrupt Merkle tree root
        if chain.merkle_tree:
            chain.merkle_tree.root = "corrupted"
        
        # Should detect
        is_valid, errors = chain.verify_integrity()
        assert is_valid == False
        assert any("merkle" in e.lower() for e in errors)
    
    def test_merkle_proof_for_entry(self):
        """Test Merkle proof for specific entry"""
        chain = MerkleAuditChain()
        
        for i in range(4):
            chain.append({"entry": i})
        
        # Get proof for entry 2
        proof = chain.get_proof(2)
        assert len(proof) > 0
        
        # Verify entry
        is_valid = chain.verify_entry(2)
        assert is_valid == True
    
    def test_persistence(self):
        """Test save/load"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create and save chain
            chain1 = MerkleAuditChain(storage_path=temp_path, auto_save=False)
            
            for i in range(3):
                chain1.append({"entry": i})
            
            root1 = chain1.get_root()
            chain1.save()
            
            # Load into new chain
            chain2 = MerkleAuditChain()
            assert chain2.load(temp_path) == True
            
            # Should be identical
            assert len(chain2) == len(chain1)
            assert chain2.get_root() == root1
            
            # Verify integrity after load
            is_valid, errors = chain2.verify_integrity()
            assert is_valid == True
            
        finally:
            os.unlink(temp_path)
    
    def test_auto_save(self):
        """Test auto-save functionality"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create chain with auto-save
            chain = MerkleAuditChain(storage_path=temp_path, auto_save=True)
            
            chain.append({"entry": 1})
            
            # Should have auto-saved
            assert os.path.exists(temp_path)
            
            # Should be loadable
            chain2 = MerkleAuditChain()
            assert chain2.load(temp_path) == True
            assert len(chain2) == 1
            
        finally:
            os.unlink(temp_path)


class TestRootPublication:
    """Tests for root publication feature (Gemini's recommendation)"""
    
    def test_root_publisher_callback(self):
        """Test root publisher is called"""
        published_roots = []
        
        def publisher(root: str):
            published_roots.append(root)
        
        chain = MerkleAuditChain(root_publisher=publisher)
        
        chain.append({"entry": 1})
        
        # Should have published
        assert len(published_roots) == 1
        assert published_roots[0] == chain.get_root()
    
    def test_published_roots_tracked(self):
        """Test published roots are tracked"""
        chain = MerkleAuditChain(root_publisher=lambda r: None)
        
        chain.append({"entry": 1})
        chain.append({"entry": 2})
        
        # Should have 2 published roots
        assert len(chain.published_roots) == 2
    
    def test_verify_against_published_root(self):
        """Test verification checks published roots"""
        chain = MerkleAuditChain(root_publisher=lambda r: None)
        
        chain.append({"entry": 1})
        
        # Integrity should pass
        is_valid, errors = chain.verify_integrity()
        assert is_valid == True
        
        # Manually change data
        chain.entries[0].data = {"corrupted": True}
        chain.entries[0].hash = chain.entries[0].compute_hash()
        chain._update_merkle_tree()
        
        # Verification should fail (root doesn't match published)
        is_valid, errors = chain.verify_integrity()
        assert is_valid == False
        assert any("published" in e.lower() for e in errors)


class TestIntegrationWithHSM:
    """Tests for integration with HSMSigner"""
    
    def test_append_with_signature(self):
        """Test appending entry with HSM signature"""
        chain = MerkleAuditChain()
        
        fake_signature = b"fake_hsm_signature"
        
        chain.append(
            {"agent": "bot-001", "action": "trade"},
            signature=fake_signature
        )
        
        assert chain.entries[0].signature == fake_signature
    
    def test_signature_preserved_after_save(self):
        """Test signature is saved and loaded"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            chain1 = MerkleAuditChain(storage_path=temp_path, auto_save=False)
            
            chain1.append(
                {"test": "data"},
                signature=b"test_signature"
            )
            
            chain1.save()
            
            # Load
            chain2 = MerkleAuditChain()
            chain2.load(temp_path)
            
            # Signature should be preserved
            assert chain2.entries[0].signature == b"test_signature"
            
        finally:
            os.unlink(temp_path)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
