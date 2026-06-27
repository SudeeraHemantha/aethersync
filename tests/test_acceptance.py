import os
import sys
import time
import shutil
import unittest
import threading
import requests
import json
import websockets
import asyncio

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import database
import app as backend_app
import uvicorn

class TestSystemAcceptance(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Point to acceptance test DB
        cls.orig_db_path = database.DB_PATH
        cls.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_acceptance_aethersync.db"))
        database.DB_PATH = cls.test_db_path
        
        cls.orig_storage_dir = backend_app.ACTIVE_STORAGE_DIR
        cls.test_storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_acceptance_shared_vault"))
        backend_app.ACTIVE_STORAGE_DIR = cls.test_storage_dir
        
        database.init_db()
        os.makedirs(cls.test_storage_dir, exist_ok=True)
        
        # Start server
        cls.host = "127.0.0.1"
        cls.port = 8091
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

    async def test_acceptance_voice_note_flow(self):
        # Clear rate limits for clean test run
        from app import rate_limit_records
        rate_limit_records.clear()

        """
        Acceptance Test:
        1. User 'sender' registers & logs in.
        2. User 'recipient' registers & logs in.
        3. User 'sender' initiates a direct chat room with 'recipient'.
        4. User 'sender' uploads a recorded voice note (duration 5s).
        5. User 'sender' broadcasts the voice note message to 'recipient' over WebSocket.
        6. User 'recipient' receives the voice note successfully.
        """
        # Step 1 & 2: Auth Flow
        requests.post(f"{self.base_url}/api/auth/register", json={"username": "acc_sender", "password": "password"})
        requests.post(f"{self.base_url}/api/auth/register", json={"username": "acc_recipient", "password": "password"})
        
        login_sender = requests.post(f"{self.base_url}/api/auth/login", json={"username": "acc_sender", "password": "password"}).json()
        login_recipient = requests.post(f"{self.base_url}/api/auth/login", json={"username": "acc_recipient", "password": "password"}).json()
        
        token_s = login_sender["token"]
        token_r = login_recipient["token"]
        
        # Step 3: Create Chat
        headers_s = {"Authorization": f"Bearer {token_s}"}
        chat_res = requests.post(
            f"{self.base_url}/api/chats/create",
            headers=headers_s,
            json={"type": "direct", "recipient_username": "acc_recipient"}
        ).json()
        chat_id = chat_res["chat_id"]
        
        # Step 4: Upload Voice Note (Simulate MediaRecorder onstop upload)
        dummy_voice_data = b"MOCK_WAV_AUDIO_DATA_FOR_ACCEPTANCE_TESTING"
        upload_res = requests.post(
            f"{self.base_url}/api/media/upload",
            headers=headers_s,
            files={"file": ("voice_note_1781446000000.wav", dummy_voice_data, "audio/wav")}
        )
        self.assertEqual(upload_res.status_code, 200)
        
        # Step 5: Connect recipient to Websocket and listen
        uri_r = f"{self.ws_url}?token={token_r}"
        uri_s = f"{self.ws_url}?token={token_s}"
        
        async with websockets.connect(uri_r) as ws_r, websockets.connect(uri_s) as ws_s:
            # Sender sends audio note details
            audio_msg = {
                "type": "audio",
                "chat_id": chat_id,
                "content": "Voice Note (0:05)",
                "file_path": "voice_note_1781446000000.wav",
                "size_bytes": len(dummy_voice_data)
            }
            await ws_s.send(json.dumps(audio_msg))
            
            # Recipient receives it
            msg_received = None
            for _ in range(5):
                response = await asyncio.wait_for(ws_r.recv(), timeout=3.0)
                data = json.loads(response)
                if data.get("type") == "message":
                    msg_received = data
                    break
            
            # Verify Acceptance Criteria
            self.assertIsNotNone(msg_received)
            self.assertEqual(msg_received["msg_type"], "audio")
            self.assertEqual(msg_received["content"], "Voice Note (0:05)")
            self.assertEqual(msg_received["file_path"], "voice_note_1781446000000.wav")
            self.assertEqual(msg_received["size_bytes"], len(dummy_voice_data))

if __name__ == "__main__":
    unittest.main()
