import os
import sys
import socket
import json
import time
import threading
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

# Setup temporary FastAPI server on port 8081 to act as a mock classmate node
app = FastAPI(title="Mock AetherSync Classmate Node")
received_messages = []

class MessagePayload(BaseModel):
    sender_name: str
    content: str
    type: str
    file_path: Optional[str] = None
    size_bytes: Optional[int] = 0

@app.post("/api/messages/receive")
def receive_message(payload: MessagePayload):
    print(f"\n[Mock Node 8081] RECEIVED MESSAGE FROM PEER:")
    print(f"  Sender: {payload.sender_name}")
    print(f"  Content: {payload.content}")
    print(f"  Type: {payload.type}")
    received_messages.append(payload.dict())
    return {"status": "success", "message_id": 999}

def run_mock_server():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081, log_level="warning")

def send_udp_broadcast():
    # Broadcast on UDP port 8085 to announce the mock node to the primary node (8080)
    print("\n[Mock Node 8081] Sending UDP auto-discovery broadcast on port 8085...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    # We send local IP as 127.0.0.1 since we are running both on the same machine
    payload = {
        "service": "aethersync",
        "username": "Mock-Classmate-8081",
        "ip": "127.0.0.1",
        "port": 8081
    }
    
    # Send broadcast
    message = json.dumps(payload).encode('utf-8')
    sock.sendto(message, ("255.255.255.255", 8085))
    sock.close()
    print("[Mock Node 8081] UDP Broadcast sent successfully.")

if __name__ == "__main__":
    # 1. Start mock server in a daemon thread
    server_thread = threading.Thread(target=run_mock_server, daemon=True)
    server_thread.start()
    time.sleep(1.5) # Let mock server start
    
    # 2. Trigger auto-discovery on main node
    send_udp_broadcast()
    time.sleep(2.0) # Let the main server register the mock user
    
    # 3. Verify if main node registered mock peer
    print("\n[Mock Node 8081] Checking if Main Node (8080) discovered us...")
    try:
        # Check database records or send a P2P message simulation from main node using Python requests
        # We can directly forward a message to main server 8080 as if it was sent by Mock-Classmate-8081
        main_receive_url = "http://127.0.0.1:8080/api/messages/receive"
        payload = {
            "sender_name": "Mock-Classmate-8081",
            "content": "Hello! I am a discovered classmate running on port 8081.",
            "type": "text"
        }
        res = requests.post(main_receive_url, json=payload, timeout=3)
        print(f"[Main Node 8080] Response status: {res.status_code}")
        print(f"[Main Node 8080] Response body: {res.text}")
    except Exception as e:
        print(f"[Error] Failed to communicate with Main Node: {e}")
        print("Make sure your main server app is running on port 8080!")
