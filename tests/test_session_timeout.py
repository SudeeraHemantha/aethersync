import os
import sys
import time
import shutil
import unittest
import threading
import requests
import uvicorn

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app

class TestSessionTimeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB to separate DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_session_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        backend_app.DB_PATH = cls.test_db_path
        
        database.init_db()

        # Start uvicorn server in background thread
        cls.host = "127.0.0.1"
        cls.port = 8093
        cls.base_url = f"http://{cls.host}:{cls.port}"
        
        cls.config = uvicorn.Config(
            backend_app.app,
            host=cls.host,
            port=cls.port,
            log_level="error"
        )
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        # Give server a moment to start
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        # Stop uvicorn server
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        
        # Restore paths and remove test DB
        database.DB_PATH = cls.orig_db_path
        backend_app.DB_PATH = cls.orig_db_path
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def setUp(self):
        # Clear active sessions and rate limit records to prevent 429 collisions
        backend_app.active_sessions.clear()
        backend_app.rate_limit_records.clear()


    def test_session_sliding_window_updates_last_activity(self):
        # 1. Register and log in a user
        username = "timeout_user_1"
        password = "password123"
        
        # Call register endpoint
        requests.post(f"{self.base_url}/api/auth/register", json={
            "username": username,
            "password": password
        })
        
        # Log in
        login_res = requests.post(f"{self.base_url}/api/auth/login", json={
            "username": username,
            "password": password
        })
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        
        # Verify it has a last_activity initialized
        self.assertIn(token, backend_app.active_sessions)
        initial_activity = backend_app.active_sessions[token]["last_activity"]
        self.assertGreater(initial_activity, 0)
        
        # Wait 1.1 seconds and make an authenticated request
        time.sleep(1.1)
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{self.base_url}/api/contacts/list", headers=headers)
        self.assertEqual(res.status_code, 200)
        
        # Verify last_activity got updated (greater than initial)
        updated_activity = backend_app.active_sessions[token]["last_activity"]
        self.assertGreater(updated_activity, initial_activity)

    def test_session_expiration_after_inactivity(self):
        # Temporarily shorten session timeout via environment
        os.environ["SESSION_TIMEOUT_SECONDS"] = "2"
        
        username = "timeout_user_2"
        password = "password123"
        
        requests.post(f"{self.base_url}/api/auth/register", json={
            "username": username,
            "password": password
        })
        
        login_res = requests.post(f"{self.base_url}/api/auth/login", json={
            "username": username,
            "password": password
        })
        token = login_res.json()["token"]
        
        # Wait 3 seconds to exceed the 2-second timeout
        time.sleep(3)
        
        # Request should fail with 401
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(f"{self.base_url}/api/contacts/list", headers=headers)
        self.assertEqual(res.status_code, 401)
        self.assertNotIn(token, backend_app.active_sessions)
        
        # Restore environment
        os.environ.pop("SESSION_TIMEOUT_SECONDS", None)

    def test_background_pruning_removes_expired_sessions(self):
        os.environ["SESSION_TIMEOUT_SECONDS"] = "1"
        
        # Create a fake active session
        fake_token = "fake_token_xyz"
        backend_app.active_sessions[fake_token] = {
            "user_id": 99,
            "username": "fake_user",
            "role": "user",
            "last_activity": time.time() - 2 # 2 seconds ago, i.e. already expired
        }
        
        # Verify it exists in memory
        self.assertIn(fake_token, backend_app.active_sessions)
        
        # Call pruner
        backend_app.prune_stale_sessions()
        
        # Verify it has been pruned from memory
        self.assertNotIn(fake_token, backend_app.active_sessions)
        
        # Restore environment
        os.environ.pop("SESSION_TIMEOUT_SECONDS", None)

if __name__ == "__main__":
    unittest.main()
