import os
import sqlite3
import hashlib

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aethersync.db"))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA cache_size=-2000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
    except Exception as e:
        print(f"[DB PRAGMA Warning] Could not apply performance tuning: {e}")
    return conn

def hash_password(password: str, salt: bytes = None) -> str:
    if not salt:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + key.hex()

def verify_password(stored_password: str, provided_password: str) -> bool:
    try:
        salt_hex, key_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table (with online status and profile status message)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
        avatar_url TEXT,
        status_text TEXT DEFAULT 'Hey there! I am using AetherLink.',
        is_online INTEGER DEFAULT 0,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        remote_ip TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Devices Table (For PWA mobile/web client pairings)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        device_name TEXT NOT NULL,
        pairing_pin TEXT,
        pairing_token TEXT UNIQUE,
        is_authorized INTEGER DEFAULT 0,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    
    # 3. Chats Table (For listing private direct chats and groups)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        type TEXT NOT NULL CHECK(type IN ('direct', 'group')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 4. Chat Members Table (Link users to chats)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_members (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY(chat_id, user_id),
        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    
    # 5. Messages Table (AetherLink messaging schema supporting media)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        sender_id INTEGER,
        sender_name TEXT NOT NULL,
        content TEXT NOT NULL,
        type TEXT DEFAULT 'text' CHECK(type IN ('text', 'image', 'video', 'document', 'audio')),
        file_path TEXT,
        size_bytes INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0,
        is_delivered INTEGER DEFAULT 0,
        FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
        FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)
    
    # 6. Legacy Files Table (For backwards compatibility with vault files)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        filepath TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        owner_id INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)
    
    # Migrate database: add remote_ip to users if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN remote_ip TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN is_delivered INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Create query performance optimization indexes
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_members_chat_user ON chat_members(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)")
    except sqlite3.OperationalError:
        pass

    # Commit changes
    conn.commit()
    
    # 7. Create default admin account if it does not exist
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        admin_pass_hash = hash_password("admin123")
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, avatar_url) VALUES (?, ?, ?, ?)",
                ("admin", admin_pass_hash, "admin", "https://api.dicebear.com/7.x/bottts/svg?seed=admin")
            )
            conn.commit()
            print("[DB] Default admin account created: admin/admin123")
        except sqlite3.IntegrityError:
            pass
            
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"[DB] Database initialized successfully at: {DB_PATH}")
