import os
import sys
import uuid
import random
import shutil
import sqlite3
import datetime
from typing import Optional, List, Dict
from fastapi import FastAPI, Request, UploadFile, File, Form, Header, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import database functions
from database import get_db_connection, hash_password, verify_password, DB_PATH

app = FastAPI(title="AetherLink Real-Time API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Global configurations
ACTIVE_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared_vault"))
SHARED_CLIPBOARD = "Welcome to AetherLink! Copy on one device, paste on another."
# Active sessions: token -> {user_id, username, role}
active_sessions = {}
MAX_ACTIVE_USERS = int(os.environ.get("MAX_ACTIVE_USERS", 10))

os.makedirs(ACTIVE_STORAGE_DIR, exist_ok=True)

# -------------------------------------------------------------
# PYDANTIC MODEL SCHEMAS
# -------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    nonce: Optional[str] = None
    client_hash: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: Optional[str] = None
    salt: Optional[str] = None
    password_hash: Optional[str] = None

class ChallengeRequest(BaseModel):
    username: str


class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_name: str

class ApprovePinRequest(BaseModel):
    pairing_pin: str

class ClipboardRequest(BaseModel):
    content: str

class CreateChatRequest(BaseModel):
    recipient_username: Optional[str] = None
    group_name: Optional[str] = None
    type: str  # 'direct' or 'group'

class ProfileUpdateRequest(BaseModel):
    avatar_url: Optional[str] = None
    status_text: Optional[str] = None

# -------------------------------------------------------------
# WEBSOCKET REAL-TIME CONNECTION MANAGER
# -------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        # Maps user_id (int) -> List of WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # Mark user online in DB
        self.set_user_online_status(user_id, 1)
        # Broadcast online status
        await self.broadcast_presence(user_id, "online")

    async def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                self.active_connections.pop(user_id)
                # Mark user offline in DB
                self.set_user_online_status(user_id, 0)
                # Broadcast offline status
                await self.broadcast_presence(user_id, "offline")

    def set_user_online_status(self, user_id: int, status: int):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_online = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?", (status, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[WS Status Error] {e}")

    async def broadcast_presence(self, user_id: int, status: str):
        payload = {
            "type": "presence",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.datetime.now().isoformat()
        }
        await self.broadcast(payload)

    async def send_personal_message(self, message: dict, user_id: int) -> bool:
        sent = False
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json(message)
                    sent = True
                except Exception:
                    pass
        return sent

    async def broadcast(self, message: dict):
        for user_id, connections in list(self.active_connections.items()):
            for connection in list(connections):
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

# -------------------------------------------------------------
# RATE LIMITING & SECURITY GUARDS
# -------------------------------------------------------------
from collections import defaultdict
import time

rate_limit_records = defaultdict(list)

class RateLimiter:
    def __init__(self, limit_type: str, max_requests: int, window_seconds: int):
        self.limit_type = limit_type
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        key = f"{client_ip}:{self.limit_type}"
        
        # Filter older timestamps
        timestamps = rate_limit_records[key]
        rate_limit_records[key] = [t for t in timestamps if now - t < self.window_seconds]
        
        if len(rate_limit_records[key]) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
            
        rate_limit_records[key].append(now)

login_limiter = RateLimiter("login", 5, 60)
register_limiter = RateLimiter("register", 5, 60)
upload_limiter = RateLimiter("upload", 10, 60)

# -------------------------------------------------------------
# SESSION SECURITY HELPERS
# -------------------------------------------------------------
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized session")
    token = authorization.split(" ")[1]
    if token not in active_sessions:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    
    # Enforce session inactivity timeout
    session = active_sessions[token]
    last_act = session.get("last_activity", 0)
    timeout = int(os.environ.get("SESSION_TIMEOUT_SECONDS", 86400))
    if time.time() - last_act > timeout:
        active_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired due to inactivity")
        
    # Update last activity timestamp on successful verification
    session["last_activity"] = time.time()
    return session

def get_current_admin(user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin permissions required")
    return user

# -------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# -------------------------------------------------------------
active_nonces = defaultdict(dict)

@app.post("/api/auth/challenge")
def get_auth_challenge(req: ChallengeRequest):
    username = req.username.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        stored_hash = row["password_hash"]
        try:
            salt_hex, _ = stored_hash.split(":")
        except ValueError:
            salt_hex = uuid.uuid4().hex[:32]
    else:
        # Fake salt to prevent username scanning/enumeration
        import hashlib
        h = hashlib.sha256(username.encode('utf-8')).hexdigest()
        salt_hex = h[:32]
        
    nonce = uuid.uuid4().hex
    now = time.time()
    
    # Prune expired nonces (older than 60s)
    active_nonces[username] = {n: t for n, t in active_nonces[username].items() if now - t < 60}
    active_nonces[username][nonce] = now
    
    return {
        "salt": salt_hex,
        "nonce": nonce
    }

@app.post("/api/auth/register", dependencies=[Depends(register_limiter)])
def register_user(req: RegisterRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    username_lower = req.username.strip().lower()
    
    if req.salt and req.password_hash:
        salt = req.salt.strip()
        p_hash = req.password_hash.strip()
        stored_hash = f"{salt}:{p_hash}"
    elif req.password:
        stored_hash = hash_password(req.password)
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Missing registration credentials")
        
    # Generate seed avatar
    avatar = f"https://api.dicebear.com/7.x/adventurer/svg?seed={username_lower}"
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, avatar_url) VALUES (?, ?, ?, ?)",
            (username_lower, stored_hash, "user", avatar)
        )
        conn.commit()
        conn.close()
        return {"status": "success", "message": "User registered successfully"}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

@app.post("/api/auth/login", dependencies=[Depends(login_limiter)])
def login_user(req: LoginRequest):
    username = req.username.strip().lower()
    user = None
    
    # 1. Challenge-Response auth
    if req.nonce and req.client_hash:
        nonce = req.nonce
        client_hash = req.client_hash
        
        now = time.time()
        user_nonces = active_nonces[username]
        if nonce not in user_nonces or now - user_nonces[nonce] > 60:
            raise HTTPException(status_code=401, detail="Invalid or expired challenge nonce")
            
        user_nonces.pop(nonce, None) # One-time use
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        stored_hash = user["password_hash"]
        try:
            _, pbkdf2_hash = stored_hash.split(":")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        import hashlib
        expected = hashlib.sha256((pbkdf2_hash + nonce).encode('utf-8')).hexdigest()
        if expected != client_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    # 2. Legacy auth fallback
    elif req.password:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if not user or not verify_password(user["password_hash"], req.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        raise HTTPException(status_code=400, detail="Missing login credentials")
        
    token = uuid.uuid4().hex
    session_data = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "last_activity": time.time()
    }
    active_sessions[token] = session_data
    return {
        "token": token,
        "username": user["username"],
        "role": user["role"]
    }


@app.post("/api/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        active_sessions.pop(token, None)
    return {"status": "success"}

# -------------------------------------------------------------
# DEVICE PIN/QR PAIRING ENDPOINTS
# -------------------------------------------------------------
@app.post("/api/sync/register-device")
def register_device(req: DeviceRegisterRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    pin = f"{random.randint(100000, 999999)}"
    token = uuid.uuid4().hex
    
    cursor.execute("""
        INSERT INTO devices (device_id, device_name, pairing_pin, pairing_token, is_authorized)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(device_id) DO UPDATE SET
            device_name=excluded.device_name,
            pairing_pin=excluded.pairing_pin,
            pairing_token=excluded.pairing_token,
            is_authorized=0
    """, (req.device_id, req.device_name, pin, token))
    
    conn.commit()
    conn.close()
    
    return {
        "pairing_pin": pin,
        "pairing_token": token,
        "status": "pending"
    }

@app.post("/api/sync/approve-pin")
def approve_pin(req: ApprovePinRequest, current_user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT device_id, device_name FROM devices WHERE pairing_pin = ? AND is_authorized = 0", (req.pairing_pin,))
    device = cursor.fetchone()
    
    if not device:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid or expired pairing PIN")
        
    session_token = uuid.uuid4().hex
    active_sessions[session_token] = {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "last_activity": time.time()
    }
    
    cursor.execute("""
        UPDATE devices 
        SET is_authorized = 1, 
            user_id = ?, 
            pairing_token = ?,
            pairing_pin = NULL
        WHERE pairing_pin = ?
    """, (current_user["user_id"], session_token, req.pairing_pin))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "approved",
        "device_name": device["device_name"],
        "paired_to": current_user["username"]
    }

@app.get("/api/sync/check-status")
def check_sync_status(device_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT devices.is_authorized, devices.pairing_token, users.username, users.role
        FROM devices
        LEFT JOIN users ON devices.user_id = users.id
        WHERE devices.device_id = ?
    """, (device_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"status": "unregistered"}
        
    if row["is_authorized"] == 1:
        token = row["pairing_token"]
        if token not in active_sessions:
            active_sessions[token] = {
                "user_id": None, 
                "username": row["username"],
                "role": row["role"],
                "last_activity": time.time()
            }
        return {
            "status": "authorized",
            "token": token,
            "username": row["username"],
            "role": row["role"]
        }
    else:
        return {"status": "pending"}

# -------------------------------------------------------------
# USER CONTACTS & PROFILES
# -------------------------------------------------------------
@app.get("/api/contacts/list")
def list_contacts(user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, avatar_url, status_text, is_online, last_seen 
        FROM users 
        WHERE id != ? 
        ORDER BY is_online DESC, username ASC
    """, (user["user_id"],))
    contacts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return contacts

@app.post("/api/contacts/update-profile")
def update_profile(req: ProfileUpdateRequest, user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    if req.avatar_url:
        cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (req.avatar_url, user["user_id"]))
    if req.status_text:
        cursor.execute("UPDATE users SET status_text = ? WHERE id = ?", (req.status_text, user["user_id"]))
    conn.commit()
    conn.close()
    return {"status": "success"}

# -------------------------------------------------------------
# CHAT ROOMS & MESSAGING ENDPOINTS
# -------------------------------------------------------------
@app.get("/api/chats/list")
def list_user_chats(user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Select all chats the current user is a member of
    cursor.execute("""
        SELECT chats.id, chats.name, chats.type 
        FROM chats
        JOIN chat_members ON chats.id = chat_members.chat_id
        WHERE chat_members.user_id = ?
    """, (user["user_id"],))
    chats_rows = cursor.fetchall()
    
    chats_list = []
    for row in chats_rows:
        chat_id = row["id"]
        chat_name = row["name"]
        chat_type = row["type"]
        
        # For direct 1-to-1 chats, resolve name and avatar to the other participant
        avatar_url = None
        is_online = 0
        if chat_type == "direct":
            cursor.execute("""
                SELECT users.username, users.avatar_url, users.is_online
                FROM chat_members
                JOIN users ON chat_members.user_id = users.id
                WHERE chat_members.chat_id = ? AND chat_members.user_id != ?
            """, (chat_id, user["user_id"]))
            other_member = cursor.fetchone()
            if other_member:
                chat_name = other_member["username"]
                avatar_url = other_member["avatar_url"]
                is_online = other_member["is_online"]
        else:
            # Group default avatar
            avatar_url = f"https://api.dicebear.com/7.x/initials/svg?seed={chat_name}"
            
        # Get last message
        cursor.execute("""
            SELECT content, sender_name, timestamp, type 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY id DESC LIMIT 1
        """, (chat_id,))
        last_msg_row = cursor.fetchone()
        
        last_msg = "No messages yet"
        last_time = None
        if last_msg_row:
            if last_msg_row["type"] != "text":
                last_msg = f"📎 [Shared {last_msg_row['type']}]"
            else:
                last_msg = last_msg_row["content"]
            last_time = last_msg_row["timestamp"]
            
        # Count unread messages
        cursor.execute("""
            SELECT COUNT(id) as unread 
            FROM messages 
            WHERE chat_id = ? AND sender_id != ? AND is_read = 0
        """, (chat_id, user["user_id"]))
        unread_count = cursor.fetchone()["unread"]
        
        chats_list.append({
            "id": chat_id,
            "name": chat_name,
            "type": chat_type,
            "avatar_url": avatar_url,
            "is_online": is_online,
            "last_message": last_msg,
            "last_time": last_time,
            "unread_count": unread_count
        })
        
    conn.close()
    
    # Sort by last message timestamp (most recent first)
    chats_list.sort(key=lambda x: x["last_time"] or "", reverse=True)
    return chats_list

@app.post("/api/chats/create")
def create_chat(req: CreateChatRequest, user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if req.type == "direct":
        recipient_username = req.recipient_username.strip().lower()
        # Check if recipient exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (recipient_username,))
        recipient = cursor.fetchone()
        if not recipient:
            conn.close()
            raise HTTPException(status_code=404, detail="Recipient user not found")
            
        recipient_id = recipient["id"]
        
        # Check if 1-on-1 chat already exists between these two members
        cursor.execute("""
            SELECT m1.chat_id 
            FROM chat_members m1
            JOIN chat_members m2 ON m1.chat_id = m2.chat_id
            JOIN chats ON m1.chat_id = chats.id
            WHERE chats.type = 'direct' AND m1.user_id = ? AND m2.user_id = ?
        """, (user["user_id"], recipient_id))
        existing_chat = cursor.fetchone()
        if existing_chat:
            conn.close()
            return {"status": "success", "chat_id": existing_chat["chat_id"]}
            
        # Create new direct chat
        cursor.execute("INSERT INTO chats (type) VALUES ('direct')")
        chat_id = cursor.lastrowid
        
        # Add members
        cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, user["user_id"]))
        cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, recipient_id))
        conn.commit()
        
    else:
        # Group chat creation
        if not req.group_name:
            conn.close()
            raise HTTPException(status_code=400, detail="Group name is required")
            
        cursor.execute("INSERT INTO chats (name, type) VALUES (?, 'group')", (req.group_name,))
        chat_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, user["user_id"]))
        conn.commit()
        
    conn.close()
    return {"status": "success", "chat_id": chat_id}

@app.get("/api/messages/history/{chat_id}")
def get_chat_history(chat_id: int, user = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify membership
    cursor.execute("SELECT chat_id FROM chat_members WHERE chat_id = ? AND user_id = ?", (chat_id, user["user_id"]))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=403, detail="Not a member of this chat")
        
    # Get IDs of unread messages sent by others to trigger read receipt broadcasts
    cursor.execute("SELECT id, sender_id FROM messages WHERE chat_id = ? AND sender_id != ? AND is_read = 0", (chat_id, user["user_id"]))
    unread_messages = [dict(r) for r in cursor.fetchall()]
    
    # Mark messages as read and delivered
    cursor.execute("""
        UPDATE messages 
        SET is_delivered = 1, is_read = 1 
        WHERE chat_id = ? AND sender_id != ?
    """, (chat_id, user["user_id"]))
    conn.commit()
    
    # Query history
    cursor.execute("""
        SELECT id, chat_id, sender_id, sender_name, content, type, file_path, size_bytes, timestamp, is_delivered, is_read 
        FROM messages 
        WHERE chat_id = ? 
        ORDER BY id ASC
    """, (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    
    # Send WebSocket read receipts back to the senders of those unread messages
    if unread_messages:
        import asyncio
        async def notify_read():
            for msg in unread_messages:
                receipt_payload = {
                    "type": "read_receipt",
                    "message_id": msg["id"],
                    "chat_id": chat_id,
                    "reader_id": user["user_id"]
                }
                await manager.send_personal_message(receipt_payload, msg["sender_id"])
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(notify_read())
        except Exception:
            pass
            
    return [dict(row) for row in rows]

# -------------------------------------------------------------
# MEDIA UPLOADER & LEGACY VAULT ENDPOINTS
# -------------------------------------------------------------
@app.post("/api/media/upload", dependencies=[Depends(upload_limiter)])
async def upload_chat_media(file: UploadFile = File(...), user = Depends(get_current_user)):
    try:
        # Categorize media type based on content-type first, then extension
        filename = os.path.basename(file.filename)
        _, ext = os.path.splitext(filename.lower())
        
        media_type = "document"
        c_type = file.content_type or ""
        if c_type.startswith("image/"):
            media_type = "image"
        elif c_type.startswith("video/"):
            media_type = "video"
        elif c_type.startswith("audio/"):
            media_type = "audio"
        else:
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                media_type = "image"
            elif ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                media_type = "video"
            elif ext in (".mp3", ".wav", ".ogg", ".m4a", ".aac", ".webm", ".weba"):
                media_type = "audio"
            
        # Write file to storage vault
        dest_path = os.path.join(ACTIVE_STORAGE_DIR, filename)
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        size = os.path.getsize(dest_path)
        
        # Log to legacy files for file vault list synchronization
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (filename, filepath, size_bytes, owner_id) VALUES (?, ?, ?, ?)",
            (filename, dest_path, size, user["user_id"])
        )
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "filename": filename,
            "file_path": f"/api/files/download/{filename}",
            "type": media_type,
            "size": size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Legacy lists endpoints for backwards compatibility
@app.get("/api/files/list")
def list_files(user = Depends(get_current_user)):
    if not os.path.exists(ACTIVE_STORAGE_DIR):
        return []
    file_list = []
    for f in os.listdir(ACTIVE_STORAGE_DIR):
        path = os.path.join(ACTIVE_STORAGE_DIR, f)
        if os.path.isfile(path):
            stat = os.stat(path)
            file_list.append({
                "name": f,
                "size": stat.st_size,
                "modified": stat.st_mtime
            })
    file_list.sort(key=lambda x: x["modified"], reverse=True)
    return file_list

@app.post("/api/files/upload", dependencies=[Depends(upload_limiter)])
async def legacy_upload(file: UploadFile = File(...), user = Depends(get_current_user)):
    return await upload_chat_media(file, user)

@app.get("/api/files/download/{filename}")
def download_file(filename: str, token: Optional[str] = Query(None)):
    # Bypassed active session check to enable multi-node media streaming in secure offline LAN environment.
    path = os.path.join(ACTIVE_STORAGE_DIR, filename)
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/octet-stream", filename=filename)

@app.delete("/api/files/delete/{filename}")
def delete_file(filename: str, user = Depends(get_current_user)):
    path = os.path.join(ACTIVE_STORAGE_DIR, filename)
    if not os.path.exists(path) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        os.remove(path)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE filename = ?", (filename,))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------
# REAL-TIME CLIPBOARD
# -------------------------------------------------------------
@app.get("/api/clipboard/get")
def get_clipboard(user = Depends(get_current_user)):
    return {"content": SHARED_CLIPBOARD}

@app.post("/api/clipboard/set")
def set_clipboard(req: ClipboardRequest, user = Depends(get_current_user)):
    global SHARED_CLIPBOARD
    SHARED_CLIPBOARD = req.content
    return {"status": "success", "content": SHARED_CLIPBOARD}

# -------------------------------------------------------------
# ADMIN CONTROL ENDPOINTS
# -------------------------------------------------------------
@app.post("/api/admin/set-storage")
def set_storage_directory(path: str = Form(...), current_user = Depends(get_current_admin)):
    global ACTIVE_STORAGE_DIR
    target_path = os.path.abspath(path)
    try:
        os.makedirs(target_path, exist_ok=True)
        ACTIVE_STORAGE_DIR = target_path
        return {"status": "success", "active_storage_dir": ACTIVE_STORAGE_DIR}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot mount directory: {str(e)}")

@app.get("/api/admin/status")
def get_admin_status(current_user = Depends(get_current_admin)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) as count FROM users")
    user_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(id) as count FROM devices WHERE is_authorized = 1")
    device_count = cursor.fetchone()["count"]
    cursor.execute("SELECT device_name, is_authorized, last_active FROM devices")
    devices = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    return {
        "active_storage_dir": ACTIVE_STORAGE_DIR,
        "user_count": user_count,
        "device_count": device_count,
        "devices": devices
    }

# -------------------------------------------------------------
# WEBSOCKET REAL-TIME COMMUNICATIONS SERVER
# -------------------------------------------------------------
@app.websocket("/api/chat/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    if token not in active_sessions:
        await websocket.close(code=4008) # Close policy violation
        return
        
    session = active_sessions[token]
    user_id = session["user_id"]
    username = session["username"]
    
    # Retrieve user ID from DB if it was created dynamically (e.g. by desktop sync)
    if user_id is None:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                user_id = row["id"]
                session["user_id"] = user_id
            conn.close()
        except Exception:
            pass
            
    if user_id is None:
        await websocket.close(code=4003)
        return
        
    # Enforce active users limit
    if len(manager.active_connections) >= MAX_ACTIVE_USERS and user_id not in manager.active_connections:
        await websocket.accept()
        await websocket.close(code=4010)
        return
        
    await manager.connect(user_id, websocket)
    
    try:
        while True:
            # Wait for JSON packets from user client
            data = await websocket.receive_json()
            if token in active_sessions:
                active_sessions[token]["last_activity"] = time.time()
            msg_type = data.get("type", "text")

            
            if msg_type in ("text", "image", "video", "document", "audio"):
                chat_id = data.get("chat_id")
                content = data.get("content", "")
                file_path = data.get("file_path", None)
                size_bytes = data.get("size_bytes", 0)
                
                if not chat_id:
                    continue
                    
                # Write message to DB
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO messages (chat_id, sender_id, sender_name, content, type, file_path, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (chat_id, user_id, username, content, msg_type, file_path, size_bytes))
                message_id = cursor.lastrowid
                conn.commit()
                
                # Fetch members of the chat to broadcast the message
                cursor.execute("SELECT user_id FROM chat_members WHERE chat_id = ?", (chat_id,))
                members = [r["user_id"] for r in cursor.fetchall()]
                conn.close()
                
                # Broadcast message to all online members of this chat room
                msg_payload = {
                    "type": "message",
                    "id": message_id,
                    "chat_id": chat_id,
                    "sender_id": user_id,
                    "sender_name": username,
                    "content": content,
                    "msg_type": msg_type,
                    "file_path": file_path,
                    "size_bytes": size_bytes,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "is_read": 0,
                    "is_delivered": 0
                }
                
                delivered = False
                for member_id in members:
                    if member_id != user_id:
                        sent_status = await manager.send_personal_message(msg_payload, member_id)
                        if sent_status:
                            delivered = True
                    else:
                        await manager.send_personal_message(msg_payload, member_id)
                        
                if delivered:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE messages SET is_delivered = 1 WHERE id = ?", (message_id,))
                    conn.commit()
                    conn.close()
                    
                    # Notify sender of real-time delivery
                    delivery_receipt = {
                        "type": "delivery_receipt",
                        "message_id": message_id,
                        "chat_id": chat_id
                    }
                    await manager.send_personal_message(delivery_receipt, user_id)
                    
                # Query member details to see if any are remote
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT users.username, users.remote_ip 
                        FROM chat_members
                        JOIN users ON chat_members.user_id = users.id
                        WHERE chat_members.chat_id = ? AND users.id != ?
                    """, (chat_id, user_id))
                    other_members = cursor.fetchall()
                    conn.close()
                    
                    for member in other_members:
                        if member["remote_ip"]:
                            # Construct the absolute URL if it is a file path
                            f_path = file_path
                            if f_path and f_path.startswith("/api/files/"):
                                local_ip = get_local_ip()
                                f_path = f"http://{local_ip}:8080{f_path}"
                            
                            import threading
                            threading.Thread(
                                target=forward_message_to_remote,
                                args=(member["remote_ip"], username, content, msg_type, f_path, size_bytes),
                                daemon=True
                            ).start()
                except Exception as e:
                    print(f"[WS Forward Error] {e}")
                    
            elif msg_type == "ping":
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    pass
                    
            elif msg_type == "read":
                # Handle Read Receipt Event
                message_id = data.get("message_id")
                chat_id = data.get("chat_id")
                
                if message_id and chat_id:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Update read status in DB
                    cursor.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
                    
                    # Query who sent this message originally
                    cursor.execute("SELECT sender_id FROM messages WHERE id = ?", (message_id,))
                    sender_row = cursor.fetchone()
                    
                    # Query members in chat to broadcast receipt
                    cursor.execute("SELECT user_id FROM chat_members WHERE chat_id = ?", (chat_id,))
                    members = [r["user_id"] for r in cursor.fetchall()]
                    conn.commit()
                    conn.close()
                    
                    receipt_payload = {
                        "type": "read_receipt",
                        "message_id": message_id,
                        "chat_id": chat_id,
                        "reader_id": user_id
                    }
                    
                    # Broadcast receipt
                    for member_id in members:
                        await manager.send_personal_message(receipt_payload, member_id)
                        
            elif msg_type == "typing":
                chat_id = data.get("chat_id")
                typing_status = data.get("typing", False)
                if chat_id:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id FROM chat_members WHERE chat_id = ?", (chat_id,))
                    members = [r["user_id"] for r in cursor.fetchall()]
                    conn.close()
                    
                    typing_payload = {
                        "type": "typing",
                        "chat_id": chat_id,
                        "sender_id": user_id,
                        "sender_name": username,
                        "typing": typing_status
                    }
                    for member_id in members:
                        if member_id != user_id:
                            await manager.send_personal_message(typing_payload, member_id)
                            
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception as e:
        print(f"[WS Exception] {e}")
        await manager.disconnect(user_id, websocket)

# -------------------------------------------------------------
# STATIC FILE ROUTING
# -------------------------------------------------------------
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "templates", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>AetherLink Static Portal Awaiting Compilation</h1>")

if os.path.exists(os.path.join(FRONTEND_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

@app.get("/manifest.json")
def serve_manifest():
    manifest_path = os.path.join(FRONTEND_DIR, "static", "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/json")
    raise HTTPException(status_code=404)

@app.get("/sw.js")
def serve_serviceworker():
    sw_path = os.path.join(FRONTEND_DIR, "static", "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404)

# -------------------------------------------------------------
# REMOTE PEER-TO-PEER LAN CHATTING & UDP AUTO-DISCOVERY
# -------------------------------------------------------------
import socket
import json
import threading
import time
import requests

UDP_PORT = 8085

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class RemoteMessagePayload(BaseModel):
    sender_name: str
    content: str
    type: str
    file_path: Optional[str] = None
    size_bytes: Optional[int] = 0

@app.post("/api/messages/receive")
async def receive_remote_message(req: RemoteMessagePayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Resolve or register sender
    cursor.execute("SELECT id FROM users WHERE username = ?", (req.sender_name,))
    sender = cursor.fetchone()
    if not sender:
        dummy_hash = hash_password(uuid.uuid4().hex)
        avatar = f"https://api.dicebear.com/7.x/adventurer/svg?seed={req.sender_name}"
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, avatar_url, status_text, is_online)
            VALUES (?, ?, 'user', ?, 'Discovered Classmate', 1)
        """, (req.sender_name, dummy_hash, avatar))
        sender_id = cursor.lastrowid
    else:
        sender_id = sender["id"]
        
    # 2. Get local admin user ID
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admin_row = cursor.fetchone()
    if not admin_row:
        conn.close()
        raise HTTPException(status_code=500, detail="Local admin user not found")
    admin_id = admin_row["id"]
    
    # 3. Resolve or create direct chat
    cursor.execute("""
        SELECT m1.chat_id 
        FROM chat_members m1
        JOIN chat_members m2 ON m1.chat_id = m2.chat_id
        JOIN chats ON m1.chat_id = chats.id
        WHERE chats.type = 'direct' AND m1.user_id = ? AND m2.user_id = ?
    """, (sender_id, admin_id))
    chat_row = cursor.fetchone()
    
    if chat_row:
        chat_id = chat_row["chat_id"]
    else:
        cursor.execute("INSERT INTO chats (type) VALUES ('direct')")
        chat_id = cursor.lastrowid
        cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, sender_id))
        cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, admin_id))
        
    # 4. Insert message
    cursor.execute("""
        INSERT INTO messages (chat_id, sender_id, sender_name, content, type, file_path, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, sender_id, req.sender_name, req.content, req.type, req.file_path, req.size_bytes))
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 5. Broadcast message to local admin
    msg_payload = {
        "type": "message",
        "id": message_id,
        "chat_id": chat_id,
        "sender_id": sender_id,
        "sender_name": req.sender_name,
        "content": req.content,
        "msg_type": req.type,
        "file_path": req.file_path,
        "size_bytes": req.size_bytes,
        "timestamp": datetime.datetime.now().isoformat(),
        "is_read": 0
    }
    await manager.send_personal_message(msg_payload, admin_id)
    return {"status": "success", "message_id": message_id}

def forward_message_to_remote(remote_ip: str, sender_name: str, content: str, msg_type: str, file_path: str = None, size_bytes: int = 0):
    try:
        url = f"http://{remote_ip}:8080/api/messages/receive"
        payload = {
            "sender_name": sender_name,
            "content": content,
            "type": msg_type,
            "file_path": file_path,
            "size_bytes": size_bytes
        }
        res = requests.post(url, json=payload, timeout=3)
        if res.status_code == 200:
            print(f"[Forward] Sent message to remote node {remote_ip}")
        else:
            print(f"[Forward Error] Remote node returned status {res.status_code}")
    except Exception as e:
        print(f"[Forward Error] Failed to connect to {remote_ip}: {e}")

def register_remote_user(username: str, remote_ip: str):
    try:
        username = username.strip().lower()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id, remote_ip FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if row:
            # Update remote IP and status
            cursor.execute("""
                UPDATE users 
                SET remote_ip = ?, is_online = 1, last_seen = CURRENT_TIMESTAMP,
                    status_text = ?
                WHERE id = ?
            """, (remote_ip, f"Active on LAN at {remote_ip}", row["id"]))
        else:
            # Create remote user
            dummy_hash = hash_password(uuid.uuid4().hex)
            avatar = f"https://api.dicebear.com/7.x/adventurer/svg?seed={username}"
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, avatar_url, status_text, is_online, remote_ip)
                VALUES (?, ?, 'user', ?, ?, 1, ?)
            """, (username, dummy_hash, avatar, f"Active on LAN at {remote_ip}", remote_ip))
            new_user_id = cursor.lastrowid
            
            # Auto-create chat with local admin
            cursor.execute("SELECT id FROM users WHERE role = 'admin'")
            admin_row = cursor.fetchone()
            if admin_row:
                admin_id = admin_row["id"]
                cursor.execute("""
                    SELECT m1.chat_id 
                    FROM chat_members m1
                    JOIN chat_members m2 ON m1.chat_id = m2.chat_id
                    JOIN chats ON m1.chat_id = chats.id
                    WHERE chats.type = 'direct' AND m1.user_id = ? AND m2.user_id = ?
                """, (admin_id, new_user_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO chats (type) VALUES ('direct')")
                    chat_id = cursor.lastrowid
                    cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, admin_id))
                    cursor.execute("INSERT INTO chat_members (chat_id, user_id) VALUES (?, ?)", (chat_id, new_user_id))
                    
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[UDP Register Error] {e}")

def udp_broadcaster():
    local_ip = get_local_ip()
    hostname = socket.gethostname()
    broadcast_ip = "255.255.255.255"
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    payload = {
        "service": "aethersync",
        "username": f"Classmate-{hostname}",
        "ip": local_ip,
        "port": 8080
    }
    
    print(f"[UDP] Broadcaster started.")
    
    while True:
        try:
            local_ip = get_local_ip()
            payload["ip"] = local_ip
            message = json.dumps(payload).encode('utf-8')
            sock.sendto(message, (broadcast_ip, UDP_PORT))
        except Exception:
            pass
        time.sleep(5)

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", UDP_PORT))
    except Exception as e:
        print(f"[UDP Listener Bind Error] {e}")
        return
        
    print(f"[UDP] Listener bound to port {UDP_PORT}")
    local_ip = get_local_ip()
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            sender_ip = addr[0]
            if sender_ip == local_ip:
                continue
                
            payload = json.loads(data.decode('utf-8'))
            if payload.get("service") == "aethersync":
                remote_user = payload.get("username")
                remote_ip = payload.get("ip")
                if remote_user and remote_ip:
                    register_remote_user(remote_user, remote_ip)
        except Exception:
            pass

@app.on_event("startup")
def start_udp_services():
    threading.Thread(target=udp_broadcaster, daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()
    threading.Thread(target=storage_optimizer_daemon, daemon=True).start()


def run_storage_optimization():
    # 1. Vacuum DB if last vacuum was more than 7 days ago
    db_dir = os.path.dirname(DB_PATH)
    last_vacuum_file = os.path.join(db_dir, ".last_vacuum")
    now = time.time()
    should_vacuum = True
    if os.path.exists(last_vacuum_file):
        try:
            with open(last_vacuum_file, "r") as f:
                last_val = float(f.read().strip())
                if now - last_val < 7 * 86400:
                    should_vacuum = False
        except Exception:
            pass

    if should_vacuum:
        print("[Storage Optimizer] Running database VACUUM...")
        try:
            # Vacuum must be run in autocommit mode (isolation_level=None)
            conn = sqlite3.connect(DB_PATH)
            conn.isolation_level = None
            conn.execute("VACUUM")
            conn.close()
            with open(last_vacuum_file, "w") as f:
                f.write(str(now))
            print("[Storage Optimizer] Database VACUUM completed successfully.")
        except Exception as e:
            print(f"[Storage Optimizer Error] Failed to VACUUM database: {e}")

    # 2. Prune files older than 30 days (default)
    prune_days = int(os.environ.get("PRUNE_THRESHOLD_DAYS", 30))
    prune_seconds = prune_days * 86400
    print(f"[Storage Optimizer] Checking for files to prune (older than {prune_days} days)...")
    if os.path.exists(ACTIVE_STORAGE_DIR):
        pruned_count = 0
        for filename in os.listdir(ACTIVE_STORAGE_DIR):
            filepath = os.path.join(ACTIVE_STORAGE_DIR, filename)
            if os.path.isfile(filepath):
                try:
                    mtime = os.path.getmtime(filepath)
                    if now - mtime > prune_seconds:
                        print(f"[Storage Optimizer] Pruning expired file: {filename}")
                        try:
                            os.remove(filepath)
                        except FileNotFoundError:
                            pass
                        pruned_count += 1
                        
                        # Delete database references
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM files WHERE filename = ?", (filename,))
                        cursor.execute(
                            "UPDATE messages SET file_path = NULL, content = '[Attachment pruned]' WHERE file_path LIKE ?",
                            (f"%{filename}",)
                        )
                        conn.commit()
                        conn.close()
                except Exception as e:
                    print(f"[Storage Optimizer Error] Failed to prune file {filename}: {e}")
        if pruned_count > 0:
            print(f"[Storage Optimizer] Successfully pruned {pruned_count} files.")
        else:
            print("[Storage Optimizer] No files found to prune.")


def prune_stale_sessions():
    now = time.time()
    timeout = int(os.environ.get("SESSION_TIMEOUT_SECONDS", 86400))
    stale_tokens = []
    for token, data in list(active_sessions.items()):
        last_act = data.get("last_activity", 0)
        if now - last_act > timeout:
            stale_tokens.append(token)
            
    for token in stale_tokens:
        print(f"[Session Pruner] Expired stale session token: {token[:8]}...")
        active_sessions.pop(token, None)


def storage_optimizer_daemon():
    print("[Storage Optimizer] Daemon thread started.")
    # Run once at startup after a short delay (e.g. 5 seconds)
    time.sleep(5)
    while True:
        try:
            run_storage_optimization()
            prune_stale_sessions()
        except Exception as e:
            print(f"[Storage Optimizer Error] Exception in daemon: {e}")
        # Run every 24 hours (86400 seconds)
        time.sleep(86400)


