import os
import sys
import time
import shutil
import unittest
import threading
import asyncio
import json
import requests
import websockets

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app
import uvicorn

class TestSystemWebSocket(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Setup separate DB for system tests
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_system_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        cls.orig_storage_dir = backend_app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_system_shared_vault"))
        backend_app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)
        
        # Start server
        cls.host = "127.0.0.1"
        cls.port = 8090
        cls.base_url = f"http://{cls.host}:{cls.port}"
        cls.ws_url = f"ws://{cls.host}:{cls.port}/api/chat/ws"
        
        cls.config = uvicorn.Config(
            backend_app.app,
            host=cls.host,
            port=cls.port,
            log_level="error",
            ws="websockets"
        )
        cls.server = uvicorn.Server(cls.config)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.server_thread.join(timeout=5)
        
        database.DB_PATH = cls.orig_db_path
        backend_app.ACTIVE_STORAGE_DIR = cls.orig_storage_dir
        
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

    async def test_websocket_message_exchange(self):
        # Clear rate limits for clean test run
        from app import rate_limit_records
        rate_limit_records.clear()

        # 1. Register and Login user1
        user1_name = "sys_user1"
        user2_name = "sys_user2"
        pw = "password123"
        
        requests.post(f"{self.base_url}/api/auth/register", json={"username": user1_name, "password": pw})
        requests.post(f"{self.base_url}/api/auth/register", json={"username": user2_name, "password": pw})
        
        r1 = requests.post(f"{self.base_url}/api/auth/login", json={"username": user1_name, "password": pw}).json()
        r2 = requests.post(f"{self.base_url}/api/auth/login", json={"username": user2_name, "password": pw}).json()
        
        token1 = r1["token"]
        token2 = r2["token"]
        
        # 2. Create direct chat room
        headers1 = {"Authorization": f"Bearer {token1}"}
        chat_res = requests.post(
            f"{self.base_url}/api/chats/create",
            headers=headers1,
            json={"type": "direct", "recipient_username": user2_name}
        ).json()
        
        chat_id = chat_res["chat_id"]
        self.assertIsNotNone(chat_id)
        
        # 3. Connect both users to WebSocket
        uri1 = f"{self.ws_url}?token={token1}"
        uri2 = f"{self.ws_url}?token={token2}"
        
        async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
            # Send dynamic message from user1 representing finished voice note recording
            audio_msg = {
                "type": "audio",
                "chat_id": chat_id,
                "content": "Voice Note (0:05)",
                "file_path": "voice_note_1234.wav",
                "size_bytes": 45000
            }
            await ws1.send(json.dumps(audio_msg))
            
            # Wait and receive on ws2, filtering out presence messages
            msg_data = None
            try:
                for _ in range(5):
                    response = await asyncio.wait_for(ws2.recv(), timeout=3.0)
                    temp_data = json.loads(response)
                    if temp_data.get("type") == "message":
                        msg_data = temp_data
                        break
                
                self.assertIsNotNone(msg_data, "Did not receive the chat message")
                self.assertEqual(msg_data["type"], "message")
                self.assertEqual(msg_data["chat_id"], chat_id)
                self.assertEqual(msg_data["sender_name"], user1_name)
                self.assertEqual(msg_data["msg_type"], "audio")
                self.assertEqual(msg_data["content"], "Voice Note (0:05)")
                self.assertEqual(msg_data["file_path"], "voice_note_1234.wav")
                self.assertEqual(msg_data["size_bytes"], 45000)
            except asyncio.TimeoutError:
                self.fail("WebSocket message receive timed out")

if __name__ == "__main__":
    unittest.main()
