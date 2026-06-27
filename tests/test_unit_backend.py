import os
import unittest
import sqlite3
import sys

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database

class TestBackendUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB_PATH to a temporary test database
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        # Initialize test database
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        # Restore DB_PATH and remove the test database
        database.DB_PATH = cls.orig_db_path
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception as e:
                print(f"Warning: Could not remove test database: {e}")

    def test_password_hashing(self):
        password = "SecurePassword123"
        hashed = database.hash_password(password)
        self.assertIsNotNone(hashed)
        self.assertIn(":", hashed)
        
        # Test verification
        self.assertTrue(database.verify_password(hashed, password))
        self.assertFalse(database.verify_password(hashed, "WrongPassword"))

    def test_db_connection(self):
        conn = database.get_db_connection()
        self.assertIsInstance(conn, sqlite3.Connection)
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn("users", tables)
        self.assertIn("devices", tables)
        self.assertIn("chats", tables)
        self.assertIn("messages", tables)
        conn.close()

    def test_user_creation_and_query(self):
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        # Insert test user
        username = "unittest_user"
        pw_hash = database.hash_password("test_pass")
        role = "user"
        
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, pw_hash, role)
        )
        conn.commit()
        
        # Query user
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], username)
        self.assertEqual(user["role"], role)
        
        # Clean up
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    unittest.main()
