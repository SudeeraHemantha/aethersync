# AetherLink - Decentralized P2P LAN Messenger & Collaborative Vault

AetherLink is a premium, secure, real-time local network (LAN) communication and file sharing platform built with FastAPI, SQLite, and WebSockets. It operates with **zero internet reliance** over local Wi-Fi, featuring a decentralized Peer-to-Peer (P2P) network architecture.

---

## ⚡ Key Features

1. **Decentralized UDP Auto-Discovery & P2P Bridging**:
   - Auto-detects other classmates running AetherLink on the same Wi-Fi using UDP broadcasts on port `8085`.
   - Establishes direct HTTP/WebSocket peer-to-peer message forwarding bridges without any central internet servers.
2. **Zero-Knowledge Challenge-Response Authentication**:
   - Plaintext passwords are never transmitted. The client derives a PBKDF2 hash (100,000 iterations) locally.
   - Utilizes time-bounded nonces to authenticate users via a secure cryptographic challenge handshake.
3. **Pure JS LAN Cryptographic Fallback**:
   - Automatically detects non-secure browser origins (unencrypted local LAN IPs like `http://10.38.67.130:8080` where native Web Crypto `window.crypto.subtle` is blocked) and falls back to pure JavaScript cryptographic engines for PBKDF2 and SHA-256 operations.
4. **End-to-End Encryption (E2EE)**:
   - Secure private channels encrypted inside the browser using AES-GCM (256-bit). Toggling E2EE alerts users in non-secure context environments for safety.
5. **Offline Message Queuing & Reconnection**:
   - Caches message queues in IndexedDB (`AetherSyncOfflineDB`) when offline.
   - Reconnects automatically using exponential backoff (up to 16s) and flushes the queue immediately on connection recovery.
6. **Smart Image Compression**:
   - Prompts to compress images >1.5MB (Canvas-based 1920px max dimension, 75% quality JPEG) or send original to conserve local LAN bandwidth.
7. **Offline Synthesized Audio & Media Vault**:
   - Web Audio API notification alerts and HTML5 voice notes recorder.
   - Upload and download large media directly to/from the mounted external storage drive.
8. **Performance & Cleanups (WAL, GZIP, Vacuuming, Pruning)**:
   - Optimized SQLite Write-Ahead Logging (`WAL`) mode for concurrent reads/writes.
   - Asynchronous weekly database `VACUUM` and automatic file vault pruning of attachments older than 30 days.
   - Gzip compression for API payloads larger than 1KB.
   - Automatic session inactivity timeout after 24 hours.
9. **Password Visibility Toggle**:
   - Reveal password input button (`👁️` / `🙈`) to verify typed credentials.

---

## 📁 Project Structure

```
aethersync/
├── aethersync.db          # Local SQLite Database
├── requirements.txt       # Python package dependencies
├── setup.bat              # Quick environment setups
├── backend/
│   ├── app.py             # FastAPI App, UDP Discovery, P2P Message Receiver, Cleanups
│   └── database.py        # Database init, schema models, performance indexes
├── desktop/
│   ├── launcher.py        # CustomTkinter Desktop Controller Hub & Pairing Approvals
│   └── messenger.py       # PyWebView client browser container
└── frontend/
    ├── templates/
    │   └── index.html     # Web Client layout & modals
    └── static/
        ├── app.js         # Real-time WebSocket handlers, offline queues, and JS cryptos
        ├── style.css      # Cyber-dark neon theme styling & E2EE/banner animations
        ├── manifest.json  # PWA installation settings
        ├── sw.js          # Service Worker caching rules (v3)
        └── icon.png       # Glowing app icon
```

---

## 🚀 Installation & Startup

### Prerequisites
- Python 3.10+ installed.

### Setup Dependencies
Run `setup.bat` or install requirements manually:
```bash
pip install -r requirements.txt
```

### Running the App
Start the controller GUI:
```bash
py desktop/launcher.py
```
1. Click **Mount External Vault Folder** to choose your folder.
2. Click **Start Hub Service**.
3. Open any browser (Chrome recommended) and navigate to the address shown (e.g., `http://localhost:8080` or the LAN IP like `http://10.38.67.130:8080`).

---

## 🌐 Network Architecture

AetherLink runs on a **Decentralized P2P** network topology:
- Multiple classmates run `launcher.py` on their own machines.
- The app automatically broadcasts presence payloads on UDP port `8085`.
- Instances discover each other and auto-register direct peer chatting endpoints to exchange encrypted messages and vault files locally with zero configuration.
