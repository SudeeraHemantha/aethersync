import os
import sqlite3
import hashlib
import time

DB_PATH = os.environ.get("AETHERSYNC_DB_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "aethersync.db")))

# Try importing sqlcipher3 for transparent at-rest encryption
db_module = sqlite3
use_encryption = False

try:
    import sqlcipher3
    db_module = sqlcipher3
    use_encryption = True
except ImportError:
    print("[DB Crypt Warning] sqlcipher3 not found. Falling back to standard unencrypted sqlite3.")

def get_db_key():
    if not use_encryption:
        return None
    key_path = os.environ.get("AETHERSYNC_KEY_PATH", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".db_key")))
    if not os.path.exists(key_path):
        import secrets
        new_key = secrets.token_hex(32)
        try:
            with open(key_path, "w", encoding="utf-8") as f:
                f.write(new_key)
        except Exception as e:
            print(f"[DB Crypt Warning] Could not write secret key file: {e}")
            
    db_key = ""
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            db_key = f.read().strip()
    except Exception as e:
        print(f"[DB Crypt Error] Could not read secret key file: {e}")
    return db_key

def get_db_connection():
    db_key = get_db_key()
    
    # If the file exists, check if it's currently in plaintext and needs migration
    if use_encryption and os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
        test_conn = None
        is_plaintext = False
        try:
            test_conn = db_module.connect(DB_PATH, timeout=5.0)
            if db_key:
                test_conn.execute(f"PRAGMA key = '{db_key}';")
            test_conn.execute("SELECT count(*) FROM sqlite_master;")
        except (db_module.DatabaseError, sqlite3.DatabaseError):
            is_plaintext = True
        finally:
            if test_conn:
                test_conn.close()
                
        if is_plaintext:
            # Decryption failed -> It is a plaintext database!
            print("[DB Crypt Migration] Plaintext database detected. Migrating to SQLCipher encrypted format...")
            plain_tmp = DB_PATH + ".plain"
            if os.path.exists(plain_tmp):
                os.remove(plain_tmp)
            
            try:
                # Rename the plaintext file
                os.rename(DB_PATH, plain_tmp)
                
                # Open plaintext database, attach encrypted database, and export
                conn_migrate = db_module.connect(plain_tmp)
                conn_migrate.execute(f"ATTACH DATABASE '{DB_PATH}' AS encrypted KEY '{db_key}'")
                conn_migrate.execute("SELECT sqlcipher_export('encrypted')")
                conn_migrate.execute("DETACH DATABASE encrypted")
                conn_migrate.close()
                
                # Verify the new encrypted database opens correctly
                verify_conn = db_module.connect(DB_PATH)
                verify_conn.execute(f"PRAGMA key = '{db_key}'")
                verify_conn.execute("SELECT count(*) FROM sqlite_master;")
                verify_conn.close()
                
                # Delete old plaintext file
                os.remove(plain_tmp)
                print("[DB Crypt Migration] Database encrypted successfully.")
            except Exception as migrate_err:
                print(f"[DB Crypt Migration Error] Migration failed: {migrate_err}")
                # Restore original file if failed
                if os.path.exists(plain_tmp) and not os.path.exists(DB_PATH):
                    os.rename(plain_tmp, DB_PATH)

    conn = db_module.connect(DB_PATH, timeout=30.0)
    conn.row_factory = db_module.Row if hasattr(db_module, "Row") else sqlite3.Row
    
    if use_encryption and db_key:
        conn.execute(f"PRAGMA key = '{db_key}';")
        
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
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN is_delivered INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN reply_to_id INTEGER DEFAULT NULL")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN deleted_by TEXT DEFAULT ''")
    except Exception:
        pass

    # Create query performance optimization indexes
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_members_chat_user ON chat_members(chat_id, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)")
    except Exception:
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
