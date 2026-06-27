import os
import sys
import unittest
import sqlite3
import time
import shutil

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app

class TestStorageOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup temporary DB path
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_storage_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        app.DB_PATH = cls.test_db_path
        
        # Setup temporary storage directory
        cls.orig_storage_dir = app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_shared_vault"))
        app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        # Clean up any leftover test files/directories
        cls.cleanup_temp_files()
        
        # Initialize DB and directories
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        # Restore original paths
        database.DB_PATH = cls.orig_db_path
        app.DB_PATH = cls.orig_db_path
        app.ACTIVE_STORAGE_DIR = cls.orig_storage_dir
        cls.cleanup_temp_files()

    @classmethod
    def cleanup_temp_files(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass
        
        # Also remove .last_vacuum file
        last_vacuum = os.path.join(os.path.dirname(cls.test_db_path), ".last_vacuum")
        if os.path.exists(last_vacuum):
            try:
                os.remove(last_vacuum)
            except Exception:
                pass

        if os.path.exists(cls.test_storage_dir):
            try:
                shutil.rmtree(cls.test_storage_dir)
            except Exception:
                pass

    def test_vacuum_execution(self):
        # Ensure vacuum file does not exist initially
        last_vacuum_file = os.path.join(os.path.dirname(app.DB_PATH), ".last_vacuum")
        if os.path.exists(last_vacuum_file):
            os.remove(last_vacuum_file)
            
        # Run optimization
        app.run_storage_optimization()
        
        # Check that .last_vacuum file got created
        self.assertTrue(os.path.exists(last_vacuum_file))
        
        # Run again, it should skip vacuum because it is within 7 days
        # Set timestamp to 8 days ago
        with open(last_vacuum_file, "w") as f:
            f.write(str(time.time() - (8 * 86400)))
            
        app.run_storage_optimization()
        
        # Verify it updated the timestamp
        with open(last_vacuum_file, "r") as f:
            val = float(f.read().strip())
        self.assertAlmostEqual(val, time.time(), delta=10.0)

    def test_file_pruning(self):
        # 1. Create a dummy file that is fresh (should NOT be pruned)
        fresh_filename = "fresh_file.txt"
        fresh_filepath = os.path.join(app.ACTIVE_STORAGE_DIR, fresh_filename)
        with open(fresh_filepath, "w") as f:
            f.write("I am fresh!")
            
        # 2. Create a dummy file that is old (should be pruned)
        old_filename = "old_file.txt"
        old_filepath = os.path.join(app.ACTIVE_STORAGE_DIR, old_filename)
        with open(old_filepath, "w") as f:
            f.write("I am old and dusty.")
            
        # Backdate the old file's modification time by 31 days
        old_time = time.time() - (31 * 86400)
        os.utime(old_filepath, (old_time, old_time))
        
        # 3. Populate database records for both files
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Insert users and chat to satisfy foreign keys
            cursor.execute("INSERT OR IGNORE INTO users (id, username, password_hash, role) VALUES (999, 'test_opt_user', 'hash', 'user')")
            cursor.execute("INSERT OR IGNORE INTO chats (id, type) VALUES (999, 'direct')")
            cursor.execute("INSERT OR IGNORE INTO chat_members (chat_id, user_id) VALUES (999, 999)")
            
            # Insert files references (using correct 4 bindings for 4 columns)
            cursor.execute(
                "INSERT INTO files (filename, filepath, size_bytes, owner_id) VALUES (?, ?, ?, ?)",
                (fresh_filename, fresh_filepath, 10, 999)
            )
            cursor.execute(
                "INSERT INTO files (filename, filepath, size_bytes, owner_id) VALUES (?, ?, ?, ?)",
                (old_filename, old_filepath, 20, 999)
            )
            
            # Insert message references
            cursor.execute(
                "INSERT INTO messages (id, chat_id, sender_id, sender_name, content, type, file_path, size_bytes) VALUES (998, 999, 999, 'test_opt_user', 'fresh', 'document', ?, 10)",
                (f"/api/files/download/{fresh_filename}",)
            )
            cursor.execute(
                "INSERT INTO messages (id, chat_id, sender_id, sender_name, content, type, file_path, size_bytes) VALUES (999, 999, 999, 'test_opt_user', 'old', 'document', ?, 20)",
                (f"/api/files/download/{old_filename}",)
            )
            
            conn.commit()
        finally:
            conn.close()
        
        # Run optimization
        os.environ["PRUNE_THRESHOLD_DAYS"] = "30"
        app.run_storage_optimization()
        
        # 4. Asserts
        # Fresh file should still exist
        self.assertTrue(os.path.exists(fresh_filepath))
        # Old file should be deleted
        self.assertFalse(os.path.exists(old_filepath))
        
        # Query database status
        conn = database.get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Fresh file references should still exist
            cursor.execute("SELECT * FROM files WHERE filename = ?", (fresh_filename,))
            self.assertIsNotNone(cursor.fetchone())
            cursor.execute("SELECT * FROM messages WHERE id = 998")
            fresh_msg = cursor.fetchone()
            self.assertEqual(fresh_msg["file_path"], f"/api/files/download/{fresh_filename}")
            self.assertEqual(fresh_msg["content"], "fresh")
            
            # Old file references should be deleted/updated
            cursor.execute("SELECT * FROM files WHERE filename = ?", (old_filename,))
            self.assertIsNone(cursor.fetchone())
            cursor.execute("SELECT * FROM messages WHERE id = 999")
            old_msg = cursor.fetchone()
            self.assertIsNone(old_msg["file_path"])
            self.assertEqual(old_msg["content"], "[Attachment pruned]")
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
