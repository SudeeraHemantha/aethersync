import os
import sys
import time
import shutil
import unittest
import threading
import requests

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app
import uvicorn

class TestBackendIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB to a separate integration test DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_integration_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        # Point active storage dir to a separate test folder
        cls.orig_storage_dir = backend_app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_shared_vault"))
        backend_app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        # Initialize test environment
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)
        
        # Start uvicorn server in a background thread
        cls.host = "127.0.0.1"
        cls.port = 8089
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

    def test_full_auth_and_upload_flow(self):
        # 1. Register a test user
        register_url = f"{self.base_url}/api/auth/register"
        register_data = {"username": "integration_user", "password": "integration_password"}
        res = requests.post(register_url, json=register_data)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")

        # 2. Login to get a token
        login_url = f"{self.base_url}/api/auth/login"
        login_data = {"username": "integration_user", "password": "integration_password"}
        res = requests.post(login_url, json=login_data)
        self.assertEqual(res.status_code, 200)
        token = res.json().get("token")
        self.assertIsNotNone(token)

        # 3. Upload a dummy audio file using the token
        upload_url = f"{self.base_url}/api/media/upload"
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a mock WAV file content
        dummy_wav_content = b"RIFF....WAVEfmt ....data...."
        files = {"file": ("test_voice_note.wav", dummy_wav_content, "audio/wav")}
        
        res = requests.post(upload_url, headers=headers, files=files)
        self.assertEqual(res.status_code, 200)
        
        # Verify the file was saved to the test storage directory
        saved_file_path = os.path.join(self.test_storage_dir, "test_voice_note.wav")
        self.assertTrue(os.path.exists(saved_file_path))
        with open(saved_file_path, "rb") as f:
            content = f.read()
            self.assertEqual(content, dummy_wav_content)

        # 4. Logout and verify token is cleared
        logout_url = f"{self.base_url}/api/auth/logout"
        res = requests.post(logout_url, headers=headers)
        self.assertEqual(res.status_code, 200)
        
        # Verify that upload fails with logged out token
        res = requests.post(upload_url, headers=headers, files=files)
        self.assertEqual(res.status_code, 401)

    def test_rate_limiting_triggers_429(self):
        login_url = f"{self.base_url}/api/auth/login"
        login_data = {"username": "nonexistent_user", "password": "wrong_password"}
        
        # Clear existing logs for this test run IP to make sure test is clean
        from app import rate_limit_records
        rate_limit_records.clear()
        
        # We make up to 5 login attempts, which should return 401 (Unauthorized)
        for i in range(5):
            res = requests.post(login_url, json=login_data)
            self.assertEqual(res.status_code, 401)
            
        # The 6th attempt should trigger rate limiting (429 Too Many Requests)
        res = requests.post(login_url, json=login_data)
        self.assertEqual(res.status_code, 429)
        self.assertIn("Too many requests", res.json().get("detail", ""))

if __name__ == "__main__":
    unittest.main()
