"""
Unit tests for blockchain node functionality.
Run with: pytest test_node.py -v
"""

import pytest
import json
import os
import hashlib
import time
import tempfile
import shutil

# Import functions to test
from node import (
    hash_block,
    get_chain,
    get_last_hash,
    add_to_chain,
    block_exists,
    get_data,
    save_data,
    get_pending,
    save_pending,
    add_pending,
    clear_pending,
    create_block,
    apply_block,
    CHAIN_FILE,
    DATA_FILE,
    PENDING_FILE,
    chain_lock,
    data_lock,
    pending_lock,
)


class TestHashBlock:
    """Tests for block hashing functionality"""

    def test_hash_block_deterministic(self):
        """Same block content produces same hash"""
        block = {
            "timestamp": 1234567890.0,
            "prev": "abc123",
            "data": {"example_data1": 1000}
        }
        hash1 = hash_block(block)
        hash2 = hash_block(block)
        assert hash1 == hash2

    def test_hash_block_different_content(self):
        """Different block content produces different hash"""
        block1 = {
            "timestamp": 1234567890.0,
            "prev": "abc123",
            "data": {"example_data1": 1000}
        }
        block2 = {
            "timestamp": 1234567891.0,
            "prev": "abc123",
            "data": {"example_data1": 1000}
        }
        assert hash_block(block1) != hash_block(block2)

    def test_hash_block_sha256_format(self):
        """Hash is valid SHA-256 (64 hex characters)"""
        block = {
            "timestamp": 1234567890.0,
            "prev": "abc123",
            "data": {"example_data1": 1000}
        }
        hash_val = hash_block(block)
        assert len(hash_val) == 64
        assert all(c in '0123456789abcdef' for c in hash_val)


class TestChainOperations:
    """Tests for blockchain operations"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        # Backup original files
        self.backup_chain = None
        self.backup_data = None
        self.backup_pending = None

        if os.path.exists(CHAIN_FILE):
            with open(CHAIN_FILE, "r") as f:
                self.backup_chain = f.read()
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                self.backup_data = f.read()
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r") as f:
                self.backup_pending = f.read()

        # Clear files for testing
        for f in [CHAIN_FILE, DATA_FILE, PENDING_FILE]:
            if os.path.exists(f):
                os.remove(f)

        yield

        # Restore original files
        if self.backup_chain:
            with open(CHAIN_FILE, "w") as f:
                f.write(self.backup_chain)
        if self.backup_data:
            with open(DATA_FILE, "w") as f:
                f.write(self.backup_data)
        if self.backup_pending:
            with open(PENDING_FILE, "w") as f:
                f.write(self.backup_pending)

    def test_get_chain_empty(self):
        """Get chain returns empty list when no chain exists"""
        chain = get_chain()
        assert chain == []

    def test_get_last_hash_empty(self):
        """Get last hash returns '0' for empty chain"""
        last_hash = get_last_hash()
        assert last_hash == "0"

    def test_add_and_get_chain(self):
        """Add block and retrieve chain"""
        block = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "test_hash_1"
        }
        add_to_chain(block)

        chain = get_chain()
        assert len(chain) == 1
        assert chain[0]["hash"] == "test_hash_1"

    def test_block_exists(self):
        """Check if block exists in chain"""
        block = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "test_hash_exists"
        }
        add_to_chain(block)

        assert block_exists("test_hash_exists") is True
        assert block_exists("nonexistent_hash") is False

    def test_get_last_hash_with_blocks(self):
        """Get last hash returns hash of latest block"""
        block1 = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "hash_1"
        }
        block2 = {
            "timestamp": time.time() + 1,
            "prev": "hash_1",
            "data": {"example_data2": 500},
            "hash": "hash_2"
        }
        add_to_chain(block1)
        add_to_chain(block2)

        last_hash = get_last_hash()
        assert last_hash == "hash_2"


class TestDataOperations:
    """Tests for data/pending operations"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        self.backup_data = None
        self.backup_pending = None

        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                self.backup_data = f.read()
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE, "r") as f:
                self.backup_pending = f.read()

        for f in [DATA_FILE, PENDING_FILE]:
            if os.path.exists(f):
                os.remove(f)

        yield

        if self.backup_data:
            with open(DATA_FILE, "w") as f:
                f.write(self.backup_data)
        if self.backup_pending:
            with open(PENDING_FILE, "w") as f:
                f.write(self.backup_pending)

    def test_get_data_creates_default(self):
        """Get data creates default ledger if file doesn't exist"""
        data = get_data()
        assert "example_data1" in data
        assert "example_data2" in data
        assert "example_data3" in data
        assert "example_data4" in data

    def test_save_and_get_data(self):
        """Save and retrieve data"""
        test_data = {"example_data1": 500, "example_data2": 300}
        save_data(test_data)

        retrieved = get_data()
        assert retrieved["example_data1"] == 500
        assert retrieved["example_data2"] == 300

    def test_get_pending_empty(self):
        """Get pending returns empty list when no pending transactions"""
        pending = get_pending()
        assert pending == []

    def test_add_and_get_pending(self):
        """Add and retrieve pending transaction"""
        block = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "pending_hash"
        }
        add_pending(block)

        pending = get_pending()
        assert len(pending) == 1
        assert pending[0]["hash"] == "pending_hash"

    def test_add_pending_duplicate(self):
        """Adding duplicate pending block is ignored"""
        block = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "duplicate_hash"
        }
        add_pending(block)
        add_pending(block)

        pending = get_pending()
        assert len(pending) == 1

    def test_clear_pending(self):
        """Clear pending removes all pending transactions"""
        block = {
            "timestamp": time.time(),
            "prev": "0",
            "data": {"example_data1": 1000},
            "hash": "to_clear"
        }
        add_pending(block)
        clear_pending()

        pending = get_pending()
        assert len(pending) == 0


class TestBlockCreation:
    """Tests for block creation"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        self.backup_chain = None
        if os.path.exists(CHAIN_FILE):
            with open(CHAIN_FILE, "r") as f:
                self.backup_chain = f.read()
        else:
            # Create empty chain file for genesis block tests
            with open(CHAIN_FILE, "w") as f:
                pass

        yield

        if self.backup_chain:
            with open(CHAIN_FILE, "w") as f:
                f.write(self.backup_chain)

    def test_create_block_structure(self):
        """Created block has required fields"""
        delta = {"example_data1": 1000}
        block = create_block(delta)

        assert "timestamp" in block
        assert "prev" in block
        assert "data" in block
        assert "hash" in block
        assert block["data"] == delta

    def test_create_block_hash_valid(self):
        """Block hash is correctly computed"""
        delta = {"example_data1": 1000}
        block = create_block(delta)

        # Verify hash matches content
        content = f"{block['timestamp']}{block['prev']}{block['data']}"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        assert block["hash"] == expected_hash

    def test_create_block_prev_genesis(self):
        """First block has '0' as prev hash"""
        # Clear chain first
        with open(CHAIN_FILE, "w") as f:
            pass

        delta = {"example_data1": 1000}
        block = create_block(delta)

        assert block["prev"] == "0"


class TestThreadSafety:
    """Tests for thread safety with locks"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        for f in [CHAIN_FILE, DATA_FILE, PENDING_FILE]:
            if os.path.exists(f):
                os.remove(f)

        yield

    def test_concurrent_data_access(self):
        """Multiple threads can safely access data"""
        import threading

        errors = []

        def modify_data():
            try:
                for i in range(10):
                    data = get_data()
                    data["example_data1"] = data.get("example_data1", 0) + 1
                    save_data(data)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=modify_data) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        data = get_data()
        assert data["example_data1"] == 50  # 5 threads * 10 increments

    def test_concurrent_chain_access(self):
        """Multiple threads can safely access chain"""
        import threading

        errors = []

        def add_blocks(thread_id):
            try:
                for i in range(5):
                    block = {
                        "timestamp": time.time(),
                        "prev": "0",
                        "data": {"thread": thread_id},
                        "hash": f"hash_{thread_id}_{i}"
                    }
                    add_to_chain(block)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_blocks, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        chain = get_chain()
        assert len(chain) == 15  # 3 threads * 5 blocks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
