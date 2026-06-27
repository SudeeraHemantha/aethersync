import os
import sys
import time
import shutil
import unittest
import threading
import requests
import hashlib
import uuid

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app
import uvicorn

class TestSecureAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB to a separate integration test DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_secure_auth_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        # Point active storage dir to a separate test folder
        cls.orig_storage_dir = backend_app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_secure_auth_vault"))
        backend_app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        # Initialize test environment
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)
        
        # Start uvicorn server in a background thread
        cls.host = "127.0.0.1"
        cls.port = 8092
        cls.base_url = f"http://{cls.host}:{cls.port}"
        
        cls.config = uvicorn.Config(
            backend_app.app,
            host=cls.host,
            port=cls.port,
            log_level="error",
            ws="auto"
        )
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        # Give the server a moment to start
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        # Stop uvicorn server
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        
        # Restore paths
        database.DB_PATH = cls.orig_db_path
        backend_app.ACTIVE_STORAGE_DIR = cls.orig_storage_dir
        
        # Remove test files and database
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception as e:
                print(f"Warning: Could not remove test database: {e}")
                
        if os.path.exists(cls.test_storage_dir):
            try:
                shutil.rmtree(cls.test_storage_dir)
            except Exception as e:
                print(f"Warning: Could not remove test storage dir: {e}")

    def setUp(self):
        # Clear rate limits and active nonces
        from app import rate_limit_records, active_nonces
        rate_limit_records.clear()
        active_nonces.clear()

    def test_challenge_nonexistent_user(self):
        # Challenge endpoint for nonexistent user should return a fake salt and valid nonce
        url = f"{self.base_url}/api/auth/challenge"
        username = f"nonexistent_{uuid.uuid4().hex[:8]}"
        res = requests.post(url, json={"username": username})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("salt", data)
        self.assertIn("nonce", data)
        self.assertEqual(len(data["salt"]), 32)
        self.assertEqual(len(data["nonce"]), 32)

        # Confirm the fake salt is deterministically derived from username to prevent scanning
        expected_fake_salt = hashlib.sha256(username.encode('utf-8')).hexdigest()[:32]
        self.assertEqual(data["salt"], expected_fake_salt)

    def test_challenge_existing_user(self):
        # Register user with client salt and hash
        register_url = f"{self.base_url}/api/auth/register"
        username = "challenge_test_user"
        salt = uuid.uuid4().hex[:32]
        # Simulate client hashing
        password = "test_password"
        salt_bytes = bytes.fromhex(salt)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000, 32).hex()
        
        res = requests.post(register_url, json={
            "username": username,
            "salt": salt,
            "password_hash": password_hash
        })
        self.assertEqual(res.status_code, 200)

        # Request challenge
        challenge_url = f"{self.base_url}/api/auth/challenge"
        res = requests.post(challenge_url, json={"username": username})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["salt"], salt)
        self.assertIsNotNone(data["nonce"])

    def test_zero_knowledge_registration_and_login_flow(self):
        username = "zk_user"
        password = "zk_password"
        salt = uuid.uuid4().hex[:32]
        salt_bytes = bytes.fromhex(salt)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000, 32).hex()

        # 1. Zero-knowledge registration
        register_url = f"{self.base_url}/api/auth/register"
        res = requests.post(register_url, json={
            "username": username,
            "salt": salt,
            "password_hash": password_hash
        })
        self.assertEqual(res.status_code, 200)

        # 2. Challenge request
        challenge_url = f"{self.base_url}/api/auth/challenge"
        res = requests.post(challenge_url, json={"username": username})
        self.assertEqual(res.status_code, 200)
        challenge_data = res.json()
        self.assertEqual(challenge_data["salt"], salt)
        nonce = challenge_data["nonce"]

        # 3. Client challenge response calculation
        client_hash = hashlib.sha256((password_hash + nonce).encode('utf-8')).hexdigest()

        # 4. Login verification
        login_url = f"{self.base_url}/api/auth/login"
        res = requests.post(login_url, json={
            "username": username,
            "nonce": nonce,
            "client_hash": client_hash
        })
        self.assertEqual(res.status_code, 200)
        login_data = res.json()
        self.assertIn("token", login_data)
        self.assertEqual(login_data["username"], username)

    def test_login_nonce_one_time_use(self):
        username = "once_user"
        password = "once_password"
        salt = uuid.uuid4().hex[:32]
        salt_bytes = bytes.fromhex(salt)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000, 32).hex()

        # Register
        register_url = f"{self.base_url}/api/auth/register"
        requests.post(register_url, json={
            "username": username,
            "salt": salt,
            "password_hash": password_hash
        })

        # Challenge
        challenge_url = f"{self.base_url}/api/auth/challenge"
        challenge_data = requests.post(challenge_url, json={"username": username}).json()
        nonce = challenge_data["nonce"]

        # First Login (should succeed)
        client_hash = hashlib.sha256((password_hash + nonce).encode('utf-8')).hexdigest()
        login_url = f"{self.base_url}/api/auth/login"
        res1 = requests.post(login_url, json={
            "username": username,
            "nonce": nonce,
            "client_hash": client_hash
        })
        self.assertEqual(res1.status_code, 200)

        # Second Login with same nonce (should fail because nonce was invalidated upon use)
        res2 = requests.post(login_url, json={
            "username": username,
            "nonce": nonce,
            "client_hash": client_hash
        })
        self.assertEqual(res2.status_code, 401)
        self.assertIn("Invalid or expired challenge nonce", res2.json()["detail"])

    def test_login_nonce_expiration(self):
        username = "expired_user"
        password = "expired_password"
        salt = uuid.uuid4().hex[:32]
        salt_bytes = bytes.fromhex(salt)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 100000, 32).hex()

        # Register
        register_url = f"{self.base_url}/api/auth/register"
        requests.post(register_url, json={
            "username": username,
            "salt": salt,
            "password_hash": password_hash
        })

        # Challenge
        challenge_url = f"{self.base_url}/api/auth/challenge"
        challenge_data = requests.post(challenge_url, json={"username": username}).json()
        nonce = challenge_data["nonce"]

        # Backdate the nonce directly in backend's memory to simulate expiration (>60 seconds ago)
        backend_app.active_nonces[username][nonce] = time.time() - 65

        # Attempt Login (should fail due to expired nonce)
        client_hash = hashlib.sha256((password_hash + nonce).encode('utf-8')).hexdigest()
        login_url = f"{self.base_url}/api/auth/login"
        res = requests.post(login_url, json={
            "username": username,
            "nonce": nonce,
            "client_hash": client_hash
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid or expired challenge nonce", res.json()["detail"])

    def test_legacy_login_fallback(self):
        username = "legacy_user"
        password = "legacy_password"

        # Register using legacy/plaintext mode
        register_url = f"{self.base_url}/api/auth/register"
        res = requests.post(register_url, json={
            "username": username,
            "password": password
        })
        self.assertEqual(res.status_code, 200)

        # Login using legacy/plaintext mode
        login_url = f"{self.base_url}/api/auth/login"
        res = requests.post(login_url, json={
            "username": username,
            "password": password
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

if __name__ == "__main__":
    unittest.main()
