import os
import sys
import time
import shutil
import unittest
import threading
import asyncio
import requests
import websockets

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app
import uvicorn

class TestConnectionGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point DB to a separate test DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_guard_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        # Point active storage dir to a separate test folder
        cls.orig_storage_dir = backend_app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_guard_shared_vault"))
        backend_app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        # Initialize test environment
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)
        
        # Set max concurrent users limit to 2 dynamically for testing
        backend_app.MAX_ACTIVE_USERS = 2
        
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
        # Clear rate limits and active connections before each test to ensure a clean state
        from app import rate_limit_records, manager
        rate_limit_records.clear()
        manager.active_connections.clear()

    def test_max_active_users_websocket_enforcement(self):
        # 1. Register 3 users
        requests.post(f"{self.base_url}/api/auth/register", json={"username": "user_guard1", "password": "password123"})
        requests.post(f"{self.base_url}/api/auth/register", json={"username": "user_guard2", "password": "password123"})
        requests.post(f"{self.base_url}/api/auth/register", json={"username": "user_guard3", "password": "password123"})

        # 2. Login to get session tokens
        token1 = requests.post(f"{self.base_url}/api/auth/login", json={"username": "user_guard1", "password": "password123"}).json()["token"]
        token2 = requests.post(f"{self.base_url}/api/auth/login", json={"username": "user_guard2", "password": "password123"}).json()["token"]
        token3 = requests.post(f"{self.base_url}/api/auth/login", json={"username": "user_guard3", "password": "password123"}).json()["token"]

        async def run_ws_guard_test():
            uri1 = f"ws://{self.host}:{self.port}/api/chat/ws?token={token1}"
            uri2 = f"ws://{self.host}:{self.port}/api/chat/ws?token={token2}"
            uri3 = f"ws://{self.host}:{self.port}/api/chat/ws?token={token3}"

            # Establish first 2 connections (which reaches limit of 2)
            ws1 = await websockets.connect(uri1)
            ws2 = await websockets.connect(uri2)

            close_code = None
            try:
                # Try to establish 3rd connection, should be rejected with 4010
                async with websockets.connect(uri3) as ws3:
                    try:
                        await ws3.recv()
                    except websockets.exceptions.ConnectionClosed as e:
                        close_code = e.code
            except websockets.exceptions.ConnectionClosed as e:
                close_code = e.code
            except Exception as e:
                if hasattr(e, 'code'):
                    close_code = e.code
                elif hasattr(e, 'status_code'):
                    close_code = e.status_code

            # Cleanup active connections
            await ws1.close()
            await ws2.close()

            return close_code

        # Run async test using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            close_code = loop.run_until_complete(run_ws_guard_test())
        finally:
            loop.close()

        # Assert connection was rejected with status code 4010
        self.assertEqual(close_code, 4010)

if __name__ == "__main__":
    unittest.main()
