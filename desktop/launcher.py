import os
import sys
import time
import socket
import threading
import sqlite3
import uvicorn
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Set up paths to import backend modules
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(BACKEND_DIR)

import app as backend_module
from database import get_db_connection, init_db, hash_password

# Initialize CustomTkinter themes
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Theme colors (matching AetherSync neon style)
COLOR_BG_DARK = "#090f1d"
COLOR_PANEL = "#0f172a"
COLOR_NEON_BLUE = "#ef4444" # Redefine to Red for cyberpunk theme
COLOR_NEON_GREEN = "#10b981"
COLOR_NEON_AMBER = "#fbbf24"
COLOR_NEON_RED = "#ef4444"
COLOR_GRAY_MUTED = "#64748b"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class UvicornServerThread(threading.Thread):
    def __init__(self, fastapi_app, host="0.0.0.0", port=8080):
        super().__init__()
        self.daemon = True
        self.fastapi_app = fastapi_app
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        try:
            config = uvicorn.Config(
                self.fastapi_app,
                host=self.host,
                port=self.port,
                log_level="info",
                ws="auto"
            )
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception as e:
            print(f"[Server Error] {e}")

    def stop(self):
        if self.server:
            self.server.should_exit = True

class BrowserSelectorDialog(ctk.CTkToplevel):
    def __init__(self, parent, url):
        super().__init__(parent)
        self.title("Select Browser")
        self.geometry("300x260")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)
        
        # Bring to front and keep focus
        self.attributes("-topmost", True)
        self.focus_force()
        
        # Center dialog relative to parent
        self.update_idletasks()
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (300 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (260 // 2)
        self.geometry(f"+{x}+{y}")
        
        self.transient(parent)
        self.grab_set()
        
        # Label
        lbl = ctk.CTkLabel(
            self, 
            text="OPEN CLIENT IN:", 
            font=("Space Grotesk", 13, "bold"),
            text_color="#ef4444"
        )
        lbl.pack(pady=(20, 15))
        
        def launch(browser_choice):
            import subprocess
            try:
                if browser_choice == "default":
                    import webbrowser
                    webbrowser.open(url)
                elif browser_choice == "chrome":
                    subprocess.Popen(["cmd.exe", "/c", "start", "chrome", url], shell=True)
                elif browser_choice == "brave":
                    subprocess.Popen(["cmd.exe", "/c", "start", "brave", url], shell=True)
                elif browser_choice == "edge":
                    subprocess.Popen(["cmd.exe", "/c", "start", "msedge", url], shell=True)
            except Exception:
                import webbrowser
                webbrowser.open(url)
            self.destroy()

        btn_style = {
            "width": 200,
            "height": 34,
            "font": ("Space Grotesk", 11, "bold"),
            "fg_color": "#0f172a",
            "border_color": "#ef4444",
            "border_width": 1,
            "text_color": "#f8fafc",
            "hover_color": "#ef4444"
        }
        
        # Default Browser Button
        btn_default = ctk.CTkButton(self, text="🌐 Default Browser", command=lambda: launch("default"), **btn_style)
        btn_default.pack(pady=5)
        
        # Google Chrome Button
        btn_chrome = ctk.CTkButton(self, text="🔴 Google Chrome", command=lambda: launch("chrome"), **btn_style)
        btn_chrome.pack(pady=5)
        
        # Brave Browser Button
        btn_brave = ctk.CTkButton(self, text="🦁 Brave Browser", command=lambda: launch("brave"), **btn_style)
        btn_brave.pack(pady=5)
        
        # Microsoft Edge Button
        btn_edge = ctk.CTkButton(self, text="🌀 Microsoft Edge", command=lambda: launch("edge"), **btn_style)
        btn_edge.pack(pady=5)

class AetherSyncHub(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AETHERSYNC HUB CONTROLLER")
        self.geometry("680x700")
        self.configure(fg_color=COLOR_BG_DARK)
        self.resizable(False, False)

        # Set custom window icon
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "icon.ico"))
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        
        # Ensure database is initialized
        init_db()
        
        # Server thread state
        self.server_thread = None
        self.server_active = False
        
        # Selected Vault directory
        self.vault_path = backend_module.ACTIVE_STORAGE_DIR
        
        # Build UI
        self.create_widgets()
        
        # Start background UI polling
        self.start_log_polling()
        
        # Auto-start the server on startup
        self.after(500, self.toggle_server)


    def create_widgets(self):
        # 1. Header Area
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=24, pady=(24, 12))
        
        self.logo_lbl = ctk.CTkLabel(
            self.header_frame,
            text="⚡ AETHERSYNC",
            font=ctk.CTkFont(family="Courier New", size=24, weight="bold"),
            text_color=COLOR_NEON_BLUE
        )
        self.logo_lbl.pack(anchor="w")
        
        self.subtitle_lbl = ctk.CTkLabel(
            self.header_frame,
            text="CLASSROOM LOCAL FILE VAULT & SYNC CORE",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=COLOR_GRAY_MUTED
        )
        self.subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # 2. Server Status Panel
        self.status_panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_width=1, border_color=COLOR_NEON_BLUE)
        self.status_panel.pack(fill="x", padx=24, pady=12)
        
        self.status_title = ctk.CTkLabel(
            self.status_panel,
            text="● SERVICE OFFLINE",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            text_color=COLOR_NEON_RED
        )
        self.status_title.pack(anchor="w", padx=16, pady=(16, 4))
        
        self.ip_box = ctk.CTkEntry(
            self.status_panel,
            placeholder_text="Server IP URL will appear here",
            font=ctk.CTkFont(family="Courier New", size=12),
            state="readonly",
            height=32,
            fg_color=COLOR_BG_DARK,
            border_color="#1e293b"
        )
        self.ip_box.pack(fill="x", padx=16, pady=8)
        
        self.toggle_srv_btn = ctk.CTkButton(
            self.status_panel,
            text="▶ START HUB SERVICE",
            command=self.toggle_server,
            fg_color=COLOR_NEON_BLUE,
            hover_color="#b91c1c",
            text_color="white",
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            height=36
        )
        self.toggle_srv_btn.pack(fill="x", padx=16, pady=(8, 8))

        self.open_web_btn = ctk.CTkButton(
            self.status_panel,
            text="🌐 OPEN WEB CLIENT",
            command=self.open_web_client,
            fg_color="#000000",
            hover_color="#111111",
            border_color=COLOR_NEON_BLUE,
            border_width=1,
            text_color=COLOR_NEON_BLUE,
            font=ctk.CTkFont(family="Courier New", size=12, weight="bold"),
            height=36,
            state="disabled"
        )
        self.open_web_btn.pack(fill="x", padx=16, pady=(0, 16))



        # 3. Storage Mount Panel
        self.storage_panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_width=1, border_color="#1e293b")
        self.storage_panel.pack(fill="x", padx=24, pady=12)
        
        self.storage_lbl = ctk.CTkLabel(
            self.storage_panel,
            text="📁 ACTIVE EXCHANGE VAULT (HDD)",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            text_color=COLOR_GRAY_MUTED
        )
        self.storage_lbl.pack(anchor="w", padx=16, pady=(12, 4))
        
        self.storage_path_entry = ctk.CTkEntry(
            self.storage_panel,
            font=ctk.CTkFont(family="Courier New", size=10),
            height=30,
            fg_color=COLOR_BG_DARK,
            border_color="#1e293b"
        )
        self.storage_path_entry.insert(0, self.vault_path)
        self.storage_path_entry.configure(state="readonly")
        self.storage_path_entry.pack(fill="x", padx=16, pady=4)
        
        self.browse_btn = ctk.CTkButton(
            self.storage_panel,
            text="MOUNT EXTERNAL VAULT FOLDER",
            command=self.browse_vault_path,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_NEON_RED,
            text_color=COLOR_NEON_RED,
            hover_color="#210d0f",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            height=32
        )
        self.browse_btn.pack(fill="x", padx=16, pady=(6, 12))

        # 4. Device Pairing Approval Panel
        self.pairing_panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_width=1, border_color="#1e293b")
        self.pairing_panel.pack(fill="x", padx=24, pady=12)
        
        self.pair_lbl = ctk.CTkLabel(
            self.pairing_panel,
            text="🔗 AUTHORIZE DEVICE (ENTER CLIENT PIN)",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            text_color=COLOR_NEON_AMBER
        )
        self.pair_lbl.pack(anchor="w", padx=16, pady=(12, 4))
        
        self.pin_input_row = ctk.CTkFrame(self.pairing_panel, fg_color="transparent")
        self.pin_input_row.pack(fill="x", padx=16, pady=(4, 12))
        
        self.pin_entry = ctk.CTkEntry(
            self.pin_input_row,
            placeholder_text="Enter 6-digit PIN",
            font=ctk.CTkFont(family="Courier New", size=13, weight="bold"),
            justify="center",
            width=200,
            height=32,
            border_color="#1e293b",
            fg_color=COLOR_BG_DARK
        )
        self.pin_entry.pack(side="left", padx=(0, 12))
        
        self.pair_approve_btn = ctk.CTkButton(
            self.pin_input_row,
            text="APPROVE PIN",
            command=self.approve_client_pin,
            fg_color=COLOR_NEON_AMBER,
            hover_color="#d97706",
            text_color=COLOR_BG_DARK,
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            height=32
        )
        self.pair_approve_btn.pack(side="right", fill="x", expand=True)

        # 5. Live Logs & Network Map Split Panel
        self.logs_panel = ctk.CTkFrame(self, fg_color=COLOR_PANEL, border_width=1, border_color="#1e293b")
        self.logs_panel.pack(fill="both", expand=True, padx=24, pady=(12, 24))
        
        # Split Frame inside logs panel
        self.split_frame = ctk.CTkFrame(self.logs_panel, fg_color="transparent")
        self.split_frame.pack(fill="both", expand=True, padx=16, pady=12)
        
        # Left side: Logs
        self.left_col = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))
        
        self.logs_lbl = ctk.CTkLabel(
            self.left_col,
            text="⚡ REAL-TIME ACTIVITY LOGS",
            font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
            text_color=COLOR_NEON_RED
        )
        self.logs_lbl.pack(anchor="w", pady=(0, 4))
        
        self.log_box = ctk.CTkTextbox(
            self.left_col,
            fg_color=COLOR_BG_DARK,
            border_width=1,
            border_color="#1e293b",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#cbd5e1",
            state="disabled"
        )
        self.log_box.pack(fill="both", expand=True)
        
        # Right side: Network Map
        self.right_col = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.right_col.pack(side="right", fill="both", expand=True, padx=(8, 0))
        
        self.map_lbl = ctk.CTkLabel(
            self.right_col,
            text="🌐 LIVE LAN NETWORK MAP",
            font=ctk.CTkFont(family="Courier New", size=10, weight="bold"),
            text_color=COLOR_NEON_RED
        )
        self.map_lbl.pack(anchor="w", pady=(0, 4))
        
        self.map_box = ctk.CTkTextbox(
            self.right_col,
            fg_color=COLOR_BG_DARK,
            border_width=1,
            border_color="#1e293b",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color="#cbd5e1",
            state="disabled"
        )
        self.map_box.pack(fill="both", expand=True)


    # -------------------------------------------------------------
    # ACTION HANDLERS
    # -------------------------------------------------------------
    def toggle_server(self):
        if not self.server_active:
            # Start Server
            local_ip = get_local_ip()
            port = 8080
            
            self.server_thread = UvicornServerThread(backend_module.app, host="0.0.0.0", port=port)
            self.server_thread.start()
            
            self.server_active = True
            self.status_title.configure(text=f"● SERVICE ACTIVE", text_color=COLOR_NEON_GREEN)
            
            # Show connection address
            url_str = f"http://{local_ip}:{port}"
            self.ip_box.configure(state="normal")
            self.ip_box.delete(0, "end")
            self.ip_box.insert(0, url_str)
            self.ip_box.configure(state="readonly")
            
            self.toggle_srv_btn.configure(
                text="⏹ STOP HUB SERVICE",
                fg_color="#000000",
                hover_color="#111111",
                border_color=COLOR_NEON_RED,
                border_width=1,
                text_color=COLOR_NEON_RED
            )
            self.open_web_btn.configure(
                state="normal",
                fg_color=COLOR_NEON_BLUE,
                hover_color="#b91c1c",
                border_width=0,
                text_color="white"
            )
            self.write_log(f"[SYSTEM] Hub Service started at {url_str}")
            self.write_log(f"[SYSTEM] Client access address: http://{local_ip}:{port}")

        else:
            # Stop Server
            if self.server_thread:
                self.server_thread.stop()
                self.server_thread = None
                
            self.server_active = False
            self.status_title.configure(text="● SERVICE OFFLINE", text_color=COLOR_NEON_RED)
            
            self.ip_box.configure(state="normal")
            self.ip_box.delete(0, "end")
            self.ip_box.configure(state="readonly")
            
            self.toggle_srv_btn.configure(
                text="▶ START HUB SERVICE",
                fg_color=COLOR_NEON_BLUE,
                hover_color="#b91c1c",
                border_width=0,
                text_color="white"
            )
            self.open_web_btn.configure(
                state="disabled",
                fg_color="#000000",
                hover_color="#111111",
                border_color=COLOR_NEON_BLUE,
                border_width=1,
                text_color=COLOR_NEON_BLUE
            )
            self.write_log("[SYSTEM] Hub Service stopped.")

    def open_web_client(self):
        url = self.ip_box.get()
        if url:
            BrowserSelectorDialog(self, url)



    def browse_vault_path(self):
        # Open directory browser
        folder = filedialog.askdirectory(initialdir=self.vault_path, title="Select Vault Storage Directory")
        if folder:
            self.vault_path = os.path.abspath(folder)
            
            # Configure backend memory path directly
            backend_module.ACTIVE_STORAGE_DIR = self.vault_path
            
            # Update UI
            self.storage_path_entry.configure(state="normal")
            self.storage_path_entry.delete(0, "end")
            self.storage_path_entry.insert(0, self.vault_path)
            self.storage_path_entry.configure(state="readonly")
            
            self.write_log(f"[STORAGE] Vault directory changed to: {self.vault_path}")

    def approve_client_pin(self):
        pin = self.pin_entry.get().strip()
        if not pin or len(pin) != 6 or not pin.isdigit():
            messagebox.showerror("Error", "Please enter a valid 6-digit client pairing PIN.")
            return
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if PIN exists
        cursor.execute("SELECT device_id, device_name FROM devices WHERE pairing_pin = ? AND is_authorized = 0", (pin,))
        device = cursor.fetchone()
        
        if not device:
            conn.close()
            messagebox.showerror("Error", "PIN not found or already approved.")
            return
            
        # Generate session token and associate to user 1 (default admin)
        session_token = uuid_token()
        active_sessions_ref = backend_module.active_sessions
        
        # Link default admin account (user_id = 1, username = 'admin')
        cursor.execute("SELECT id, username FROM users WHERE id = 1")
        admin = cursor.fetchone()
        
        if not admin:
            conn.close()
            messagebox.showerror("Error", "Host administrator account not found in database.")
            return
            
        active_sessions_ref[session_token] = {
            "user_id": admin["id"],
            "username": admin["username"],
            "role": "admin"
        }
        
        cursor.execute("""
            UPDATE devices 
            SET is_authorized = 1, 
                user_id = ?, 
                pairing_token = ?,
                pairing_pin = NULL
            WHERE pairing_pin = ?
        """, (admin["id"], session_token, pin))
        
        conn.commit()
        conn.close()
        
        # Update log and notify
        self.pin_entry.delete(0, "end")
        self.write_log(f"[AUTH] Device '{device['device_name']}' successfully paired to '{admin['username']}'")
        messagebox.showinfo("Success", f"Device '{device['device_name']}' successfully authorized!")

    # Helper: Write log line directly
    def write_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # -------------------------------------------------------------
    # LOG POLLING LOOP (FROM DB)
    # -------------------------------------------------------------
    def start_log_polling(self):
        self.last_log_id = 0
        self.last_chat_id = 0
        self.poll_logs()

    def poll_logs(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Poll new file uploads/deletions from DB
            cursor.execute("SELECT id, filename, owner_id, uploaded_at FROM files WHERE id > ? ORDER BY id ASC", (self.last_log_id,))
            new_files = cursor.fetchall()
            for nf in new_files:
                self.last_log_id = nf["id"]
                # Query owner name
                cursor.execute("SELECT username FROM users WHERE id = ?", (nf["owner_id"],))
                user = cursor.fetchone()
                uname = user["username"] if user else "Guest"
                self.write_log(f"[VAULT] File uploaded: '{nf['filename']}' by '{uname}' at {nf['uploaded_at']}")
                
            # Poll new chats from messages
            cursor.execute("SELECT id, sender_name, content, timestamp FROM messages WHERE id > ? ORDER BY id ASC", (self.last_chat_id,))
            new_chats = cursor.fetchall()
            for nc in new_chats:
                self.last_chat_id = nc["id"]
                # Format time
                t_str = nc["timestamp"].split(" ")[1] if " " in nc["timestamp"] else nc["timestamp"]
                self.write_log(f"[{t_str}] <{nc['sender_name']}> {nc['content']}")
                
            # Update Live Network Map
            self.update_network_map(cursor)
                
            conn.close()
        except Exception:
            pass
            
        # Poll again in 1200ms
        self.after(1200, self.poll_logs)

    def update_network_map(self, cursor):
        try:
            self.map_box.configure(state="normal")
            self.map_box.delete("1.0", "end")
            
            # 1. Local admin/users status
            self.map_box.insert("end", "=== LOCAL INSTANCE ===\n")
            cursor.execute("SELECT username, is_online FROM users WHERE remote_ip IS NULL")
            local_users = cursor.fetchall()
            for u in local_users:
                status = "Online" if u["is_online"] == 1 else "Offline"
                self.map_box.insert("end", f"👤 {u['username']} ({status})\n")
                
            # 2. LAN Neighbors
            self.map_box.insert("end", "\n=== LAN NEIGHBORS ===\n")
            cursor.execute("SELECT username, remote_ip FROM users WHERE remote_ip IS NOT NULL AND is_online = 1")
            discovered_users = cursor.fetchall()
            if not discovered_users:
                self.map_box.insert("end", "No peers detected yet...\n")
            for u in discovered_users:
                self.map_box.insert("end", f"🖥️ {u['username']}\n   ({u['remote_ip']})\n")
                
            # 3. Synced Devices
            self.map_box.insert("end", "\n=== SYNCED DEVICES ===\n")
            cursor.execute("SELECT device_name, is_authorized FROM devices")
            synced_devices = cursor.fetchall()
            if not synced_devices:
                self.map_box.insert("end", "No paired devices.\n")
            for d in synced_devices:
                auth_status = "Approved" if d["is_authorized"] == 1 else "Pending"
                self.map_box.insert("end", f"📱 {d['device_name']}\n   [{auth_status}]\n")
                
            self.map_box.configure(state="disabled")
        except Exception:
            pass


    # Clean stop on exit
    def destroy(self):
        if self.server_thread:
            self.server_thread.stop()
        super().destroy()

# Inline UUID Helper
def uuid_token():
    import uuid
    return uuid.uuid4().hex

if __name__ == "__main__":
    # Force taskbar grouping with custom icon on Windows
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lnbti.aethersync.hub.1.0")
    except Exception:
        pass

    app = AetherSyncHub()
    app.mainloop()
