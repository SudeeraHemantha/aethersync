// AetherLink Client Application Logic

const KEY_TOKEN = 'aethersync_token';
const KEY_USERNAME = 'aethersync_username';
const KEY_DEVICE_ID = 'aethersync_device_id';
const KEY_DEVICE_NAME = 'aethersync_device_name';

let socket = null;
let activeChatId = null;
let currentUserId = null;
let activeIntervals = [];
let pollingDeviceSync = null;
let pendingUploadFile = null;
let heartbeatInterval = null;
let db = null;
let reconnectDelay = 1000;
const maxReconnectDelay = 16000;

// Local search cache
let contactsData = [];
let chatsData = [];

// Audio recording states
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// Typing indicator states
let activeChatOnline = false;
let typingTimeout = null;
let isTypingStateSent = false;

window.addEventListener('DOMContentLoaded', () => {
    initIndexedDB();
    initDevice();
    checkExistingAuth();
    
    // Trigger Cyberpunk Boot Diagnostic Sequence
    runBootDiagnosticSequence();
    
    // Restore theme accent on startup
    const savedAccent = localStorage.getItem('aethersync_accent_name') || 'red';
    setThemeAccent(savedAccent);

    // Bind image quality prompt option buttons
    const btnCompress = document.getElementById('btn-compress-send');
    if (btnCompress) {
        btnCompress.addEventListener('click', async () => {
            if (!pendingUploadFile) return;
            const fileToUpload = pendingUploadFile;
            closeCompressModal();
            try {
                const compressed = await compressImage(fileToUpload);
                uploadFile(compressed);
            } catch (err) {
                console.error("Compression failed, uploading original:", err);
                uploadFile(fileToUpload);
            }
        });
    }

    const btnOriginal = document.getElementById('btn-original-send');
    if (btnOriginal) {
        btnOriginal.addEventListener('click', () => {
            if (!pendingUploadFile) return;
            const fileToUpload = pendingUploadFile;
            closeCompressModal();
            uploadFile(fileToUpload);
        });
    }

    // Bind typing indicator input listener
    const chatInput = document.getElementById('chat-text-input');
    if (chatInput) {
        chatInput.addEventListener('input', handleTypingIndicator);
    }

    // Bind drag-and-drop file sharing events
    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragover', handleDragOver);
    
    const dragOverlay = document.getElementById('drag-drop-overlay');
    if (dragOverlay) {
        dragOverlay.addEventListener('dragleave', handleDragLeave);
        dragOverlay.addEventListener('drop', handleDrop);
    }
});

// Device Details Initialization
function initDevice() {
    let deviceId = localStorage.getItem(KEY_DEVICE_ID);
    if (!deviceId) {
        deviceId = 'dev_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        localStorage.setItem(KEY_DEVICE_ID, deviceId);
    }
    
    let deviceName = localStorage.getItem(KEY_DEVICE_NAME);
    if (!deviceName) {
        const ua = navigator.userAgent;
        let browser = "Browser";
        let os = "Device";
        if (ua.indexOf("Firefox") > -1) browser = "Firefox";
        else if (ua.indexOf("Chrome") > -1) browser = "Chrome";
        else if (ua.indexOf("Safari") > -1) browser = "Safari";
        else if (ua.indexOf("Edge") > -1) browser = "Edge";
        
        if (ua.indexOf("Windows") > -1) os = "PC";
        else if (ua.indexOf("Mac") > -1) os = "Mac";
        else if (ua.indexOf("Android") > -1) os = "Android";
        else if (ua.indexOf("iPhone") > -1) os = "iPhone";
        
        deviceName = `${browser} (${os})`;
        localStorage.setItem(KEY_DEVICE_NAME, deviceName);
    }
    
    document.getElementById('device-name-lbl').textContent = deviceName;
}

// Authentication Check
function checkExistingAuth() {
    const token = localStorage.getItem(KEY_TOKEN);
    const username = localStorage.getItem(KEY_USERNAME);
    
    if (token && username) {
        showDashboard(username);
    } else {
        showScreen('auth-screen');
    }
}

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

// -------------------------------------------------------------
// AUTHENTICATION AND DEVICE PAIRING
// -------------------------------------------------------------
function switchAuthTab(type) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.auth-panel').forEach(p => p.classList.remove('active'));
    
    if (type === 'login') {
        document.getElementById('tab-login').classList.add('active');
        document.getElementById('credentials-panel').classList.add('active');
        stopDeviceSyncPolling();
    } else {
        document.getElementById('tab-pair').classList.add('active');
        document.getElementById('pairing-panel').classList.add('active');
        startDeviceSyncPolling();
    }
}

function stopDeviceSyncPolling() {
    if (pollingDeviceSync) {
        clearInterval(pollingDeviceSync);
        pollingDeviceSync = null;
    }
}

async function startDeviceSyncPolling() {
    stopDeviceSyncPolling();
    const deviceId = localStorage.getItem(KEY_DEVICE_ID);
    const deviceName = localStorage.getItem(KEY_DEVICE_NAME);
    
    try {
        const res = await fetch('/api/sync/register-device', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId, device_name: deviceName })
        });
        if (!res.ok) throw new Error("Pairing registration failed");
        
        const data = await res.json();
        const pin = data.pairing_pin;
        
        if (pin && pin.length === 6) {
            document.getElementById('d1').textContent = pin[0];
            document.getElementById('d2').textContent = pin[1];
            document.getElementById('d3').textContent = pin[2];
            document.getElementById('d4').textContent = pin[3];
            document.getElementById('d5').textContent = pin[4];
            document.getElementById('d6').textContent = pin[5];
        }
        
        pollingDeviceSync = setInterval(async () => {
            try {
                const checkRes = await fetch(`/api/sync/check-status?device_id=${deviceId}`);
                const statusData = await checkRes.json();
                
                if (statusData.status === 'authorized') {
                    stopDeviceSyncPolling();
                    localStorage.setItem(KEY_TOKEN, statusData.token);
                    localStorage.setItem(KEY_USERNAME, statusData.username);
                    showDashboard(statusData.username);
                }
            } catch (err) {
                console.error("Error checking sync status:", err);
            }
        }, 1200);
        
    } catch (e) {
        console.error(e);
        document.getElementById('auth-error').textContent = "Failed to start device sync session.";
    }
}

function sha256_pure(bytes) {
    function rightRotate(value, amount) {
        return (value >>> amount) | (value << (32 - amount));
    }
    const h = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];
    const k = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];
    const len = bytes.length;
    const words = new Uint32Array(((len + 8) >> 6) + 1 << 4);
    for (let i = 0; i < len; i++) {
        words[i >> 2] |= bytes[i] << (24 - (i & 3) * 8);
    }
    words[len >> 2] |= 0x80 << (24 - (len & 3) * 8);
    words[words.length - 1] = len * 8;

    const w = new Uint32Array(64);
    for (let i = 0; i < words.length; i += 16) {
        let a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], _h = h[7];
        for (let j = 0; j < 64; j++) {
            if (j < 16) {
                w[j] = words[i + j];
            } else {
                const w15 = w[j - 15];
                const w2 = w[j - 2];
                const s0 = rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3);
                const s1 = rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10);
                w[j] = (w[j - 16] + s0 + w[j - 7] + s1) | 0;
            }
            const s1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
            const ch = (e & f) ^ (~e & g);
            const temp1 = (_h + s1 + ch + k[j] + w[j]) | 0;
            const s0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
            const maj = (a & b) ^ (a & c) ^ (b & c);
            const temp2 = (s0 + maj) | 0;
            _h = g; g = f; f = e; e = (d + temp1) | 0; d = c; c = b; b = a; a = (temp1 + temp2) | 0;
        }
        h[0] = (h[0] + a) | 0; h[1] = (h[1] + b) | 0; h[2] = (h[2] + c) | 0; h[3] = (h[3] + d) | 0;
        h[4] = (h[4] + e) | 0; h[5] = (h[5] + f) | 0; h[6] = (h[6] + g) | 0; h[7] = (h[7] + _h) | 0;
    }
    const out = new Uint8Array(32);
    for (let i = 0; i < 8; i++) {
        out[i * 4] = (h[i] >>> 24) & 0xff;
        out[i * 4 + 1] = (h[i] >>> 16) & 0xff;
        out[i * 4 + 2] = (h[i] >>> 8) & 0xff;
        out[i * 4 + 3] = h[i] & 0xff;
    }
    return out;
}

function hmac_sha256_pure(keyBytes, msgBytes) {
    let key = new Uint8Array(keyBytes);
    if (key.length > 64) key = sha256_pure(key);
    const paddedKey = new Uint8Array(64);
    paddedKey.set(key);
    const ipad = new Uint8Array(64);
    const opad = new Uint8Array(64);
    for (let i = 0; i < 64; i++) {
        ipad[i] = paddedKey[i] ^ 0x36;
        opad[i] = paddedKey[i] ^ 0x5c;
    }
    const innerMsg = new Uint8Array(64 + msgBytes.length);
    innerMsg.set(ipad);
    innerMsg.set(msgBytes, 64);
    const innerHash = sha256_pure(innerMsg);
    const outerMsg = new Uint8Array(64 + innerHash.length);
    outerMsg.set(opad);
    outerMsg.set(innerHash, 64);
    return sha256_pure(outerMsg);
}

function pbkdf2_sha256_pure(passwordStr, saltBytes, iterations, keyLen) {
    const passwordBytes = new TextEncoder().encode(passwordStr);
    const result = new Uint8Array(keyLen);
    const numBlocks = Math.ceil(keyLen / 32);
    for (let blockNum = 1; blockNum <= numBlocks; blockNum++) {
        const blockSalt = new Uint8Array(saltBytes.length + 4);
        blockSalt.set(saltBytes);
        blockSalt[saltBytes.length] = (blockNum >>> 24) & 0xff;
        blockSalt[saltBytes.length + 1] = (blockNum >>> 16) & 0xff;
        blockSalt[saltBytes.length + 2] = (blockNum >>> 8) & 0xff;
        blockSalt[saltBytes.length + 3] = blockNum & 0xff;
        let u = hmac_sha256_pure(passwordBytes, blockSalt);
        const f = new Uint8Array(u);
        for (let i = 2; i <= iterations; i++) {
            u = hmac_sha256_pure(passwordBytes, u);
            for (let j = 0; j < 32; j++) {
                f[j] ^= u[j];
            }
        }
        const offset = (blockNum - 1) * 32;
        const copyLen = Math.min(32, keyLen - offset);
        for (let j = 0; j < copyLen; j++) {
            result[offset + j] = f[j];
        }
    }
    return result;
}

async function hashPasswordClient(password, saltHex) {
    if (!window.crypto || !window.crypto.subtle) {
        const salt = new Uint8Array(saltHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
        const hashBytes = pbkdf2_sha256_pure(password, salt, 100000, 32);
        return Array.from(hashBytes).map(b => b.toString(16).padStart(2, '0')).join('');
    }
    const encoder = new TextEncoder();
    const passwordKey = await window.crypto.subtle.importKey(
        'raw',
        encoder.encode(password),
        { name: 'PBKDF2' },
        false,
        ['deriveBits']
    );
    
    // Parse salt hex string to Uint8Array
    const salt = new Uint8Array(saltHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const pbkdf2Bits = await window.crypto.subtle.deriveBits(
        {
            name: 'PBKDF2',
            salt: salt,
            iterations: 100000,
            hash: 'SHA-256'
        },
        passwordKey,
        256
    );
    
    const hashBuffer = new Uint8Array(pbkdf2Bits);
    return Array.from(hashBuffer).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function sha256Client(messageText) {
    const encoder = new TextEncoder();
    const data = encoder.encode(messageText);
    if (!window.crypto || !window.crypto.subtle) {
        const hashBytes = sha256_pure(data);
        return Array.from(hashBytes).map(b => b.toString(16).padStart(2, '0')).join('');
    }
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function generateRandomSaltHex() {
    const array = new Uint8Array(16);
    window.crypto.getRandomValues(array);
    return Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('');
}

function togglePasswordVisibility() {
    const pwdInput = document.getElementById('password');
    const toggleBtn = document.getElementById('password-toggle-btn');
    if (pwdInput && toggleBtn) {
        if (pwdInput.type === 'password') {
            pwdInput.type = 'text';
            toggleBtn.textContent = '🙈';
        } else {
            pwdInput.type = 'password';
            toggleBtn.textContent = '👁️';
        }
    }
}

function formatErrorMessage(errData, defaultMsg) {
    if (errData && errData.detail) {
        if (Array.isArray(errData.detail)) {
            return errData.detail.map(e => {
                const field = e.loc ? e.loc[e.loc.length - 1] : null;
                return field ? `${field.toUpperCase()}: ${e.msg}` : e.msg;
            }).join(", ");
        } else if (typeof errData.detail === 'string') {
            return errData.detail;
        } else {
            return JSON.stringify(errData.detail);
        }
    }
    return defaultMsg;
}

async function handleLogin(e) {
    e.preventDefault();
    document.getElementById('auth-error').textContent = "";
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        // 1. Fetch challenge nonce/salt
        const challengeRes = await fetch('/api/auth/challenge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const challengeData = await challengeRes.json().catch(() => ({}));
        if (!challengeRes.ok) {
            throw new Error(formatErrorMessage(challengeData, "Failed to get authorization challenge"));
        }
        const { salt, nonce } = challengeData;
        
        // 2. Hash password and calculate response
        const p_hash = await hashPasswordClient(password, salt);
        const client_hash = await sha256Client(p_hash + nonce);
        
        // 3. Login with challenge response
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, nonce, client_hash })
        });
        const loginData = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(formatErrorMessage(loginData, "Authentication failed"));
        }
        localStorage.setItem(KEY_TOKEN, loginData.token);
        localStorage.setItem(KEY_USERNAME, loginData.username);
        showDashboard(loginData.username);
    } catch (err) {
        document.getElementById('auth-error').textContent = err.message;
    }
}

async function handleRegister() {
    document.getElementById('auth-error').textContent = "";
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    if (!username || !password) {
        document.getElementById('auth-error').textContent = "Please enter both username and password.";
        return;
    }
    
    try {
        // 1. Register with client hashed password
        const salt = generateRandomSaltHex();
        const password_hash = await hashPasswordClient(password, salt);
        
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, salt, password_hash })
        });
        const registerData = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(formatErrorMessage(registerData, "Registration failed"));
        }
        
        // 2. Auto login via challenge response
        const challengeRes = await fetch('/api/auth/challenge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const challengeData = await challengeRes.json().catch(() => ({}));
        if (!challengeRes.ok) {
            throw new Error(formatErrorMessage(challengeData, "Failed to get authorization challenge"));
        }
        const { nonce } = challengeData;
        
        const client_hash = await sha256Client(password_hash + nonce);
        
        const loginRes = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, nonce, client_hash })
        });
        const loginData = await loginRes.json().catch(() => ({}));
        if (!loginRes.ok) {
            throw new Error(formatErrorMessage(loginData, "Auto-login failed"));
        }
        localStorage.setItem(KEY_TOKEN, loginData.token);
        localStorage.setItem(KEY_USERNAME, loginData.username);
        showDashboard(loginData.username);
    } catch (err) {
        document.getElementById('auth-error').textContent = err.message;
    }
}

function handleLogout() {
    const token = localStorage.getItem(KEY_TOKEN);
    fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (socket) {
        socket.close();
        socket = null;
    }
    
    localStorage.removeItem(KEY_TOKEN);
    localStorage.removeItem(KEY_USERNAME);
    
    activeIntervals.forEach(clearInterval);
    activeIntervals = [];
    
    document.getElementById('username').value = "";
    document.getElementById('password').value = "";
    document.getElementById('auth-error').textContent = "";
    
    // Close panel states
    activeChatId = null;
    document.getElementById('chat-placeholder').classList.add('active');
    document.getElementById('active-chat-container').classList.remove('chat-active');
    
    showScreen('auth-screen');
    switchAuthTab('login');
}

// -------------------------------------------------------------
// REAL-TIME WEBSOCKET SYSTEM
// -------------------------------------------------------------
function startHeartbeat() {
    stopHeartbeat();
    heartbeatInterval = setInterval(() => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
        }
    }, 10000);
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

function initWebSocket() {
    const token = localStorage.getItem(KEY_TOKEN);
    if (!token) return;
    
    if (socket) {
        socket.close();
    }
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/chat/ws?token=${token}`;
    
    socket = new WebSocket(wsUrl);
    const badge = document.getElementById('ws-status-badge');
    
    socket.onopen = () => {
        console.log("[WS] Linked to Real-Time Router.");
        if (badge) {
            badge.textContent = "online";
            badge.className = "status-badge connected";
        }
        
        // Hide warning / show success banner if we were previously disconnected
        if (reconnectDelay > 1000) {
            showConnectionSuccessBanner();
        }
        reconnectDelay = 1000; // Reset backoff
        
        startHeartbeat();
        // Flush offline messages
        flushOfflineMessages();
    };
    
    socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'pong') {
            return;
        }
        handleWSMessage(payload);
    };
    
    socket.onclose = (event) => {
        if (badge) {
            badge.textContent = "offline";
            badge.className = "status-badge disconnected";
        }
        stopHeartbeat();
        
        if (event && event.code === 4010) {
            console.log("[WS] Router disconnected. Maximum concurrent users reached on server.");
            const banner = document.getElementById('connection-status-banner');
            if (banner) {
                banner.textContent = "Offline - Server user limit reached. Please try again later.";
                banner.classList.remove('connected-alert');
                banner.classList.add('visible');
            }
            return; // Stop auto-reconnect retries
        }
        
        // Show reconnecting banner
        showConnectionWarningBanner();
        
        const delay = reconnectDelay;
        // Double reconnection backoff up to limit
        reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
        console.log(`[WS] Router disconnected. Reconnecting in ${delay}ms...`);
        setTimeout(initWebSocket, delay);
    };
}

// Handles incoming WebSocket Events
function handleWSMessage(data) {
    if (data.type === 'message') {
        // Play notification sound for incoming messages
        const myUsername = localStorage.getItem(KEY_USERNAME);
        if (data.sender_name !== myUsername) {
            playNotificationSound();
        }
        
        // A new chat message arrived
        if (activeChatId && data.chat_id === activeChatId) {
            appendMessageBubble(data);
            scrollMessagesToBottom();
            
            // Send read receipt if this chat is currently open
            sendReadReceipt(data.id, data.chat_id);
        } else {
            // Re-pull chat list to update badge and message snippet
            pullChatList();
        }
    } else if (data.type === 'read_receipt') {
        // A read receipt was sent by other participant
        if (activeChatId && data.chat_id === activeChatId) {
            updateCheckmarkToRead(data.message_id);
        }
    } else if (data.type === 'delivery_receipt') {
        // A delivery receipt was sent by server
        if (activeChatId && data.chat_id === activeChatId) {
            updateCheckmarkToDelivered(data.message_id);
        }
    } else if (data.type === 'presence') {
        // Discovered/Online presence update
        updateContactOnlineStatus(data.user_id, data.status);
    } else if (data.type === 'typing') {
        // Typing status update
        if (activeChatId && data.chat_id === activeChatId) {
            handleIncomingTyping(data.sender_name, data.typing);
        }
    }
}

// Send read event over socket
function sendReadReceipt(messageId, chatId) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            type: "read",
            message_id: messageId,
            chat_id: chatId
        }));
    }
}

// -------------------------------------------------------------
// DASHBOARD & INTERFACE RENDERING
// -------------------------------------------------------------
function showDashboard(username) {
    document.getElementById('my-username').textContent = username;
    document.getElementById('my-avatar').src = `https://api.dicebear.com/7.x/adventurer/svg?seed=${username}`;
    showScreen('main-screen');
    
    // Connect WebSockets
    initWebSocket();
    
    // Initial pulls
    pullChatList();
    pullContactsList();
    
    // Setup long-polling backups for contacts and lists (to check if new users registered)
    activeIntervals.push(setInterval(pullChatList, 4000));
    activeIntervals.push(setInterval(pullContactsList, 6000));
}

// Pull Chats Sidebar list
async function pullChatList() {
    const token = localStorage.getItem(KEY_TOKEN);
    if (!token) return;
    
    try {
        const res = await fetch('/api/chats/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.status === 401) {
            handleLogout();
            return;
        }
        chatsData = await res.json();
        renderChatList(chatsData);
        updateTotalUnreadCount(chatsData);
    } catch (e) {
        console.error("Error pulling chats:", e);
    }
}

// Render Chats list inside DOM sidebar
function renderChatList(chats) {
    const listContainer = document.getElementById('chat-list');
    listContainer.innerHTML = "";
    
    if (chats.length === 0) {
        listContainer.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 13px;">No conversations yet. Click ＋ to start a chat!</div>`;
        return;
    }
    
    chats.forEach(chat => {
        const div = document.createElement('div');
        div.className = `chat-item ${chat.id === activeChatId ? 'active' : ''} ${chat.is_online === 1 ? 'online' : ''}`;
        div.id = `chat-item-${chat.id}`;
        div.onclick = () => openConversation(chat.id, chat.name, chat.avatar_url, chat.is_online);
        
        let timeStr = "";
        if (chat.last_time) {
            const d = new Date(chat.last_time);
            timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        const badgeHtml = chat.unread_count > 0 ? `<span class="chat-item-unread">${chat.unread_count}</span>` : "";
        
        div.innerHTML = `
            <div class="chat-item-avatar">
                <img src="${chat.avatar_url}" alt="Avatar">
                <span class="status-dot"></span>
            </div>
            <div class="chat-item-details">
                <div class="chat-item-row1">
                    <span class="chat-item-name">${chat.name}</span>
                    <span class="chat-item-time">${timeStr}</span>
                </div>
                <div class="chat-item-row2">
                    <span class="chat-item-msg">${chat.last_message}</span>
                    ${badgeHtml}
                </div>
            </div>
        `;
        listContainer.appendChild(div);
    });
}

function updateTotalUnreadCount(chats) {
    const total = chats.reduce((sum, c) => sum + (c.unread_count || 0), 0);
    if (total > 0) {
        document.title = `(${total}) AetherLink - LAN Messenger`;
    } else {
        document.title = "AetherLink - LAN Messenger";
    }
}

// Pull Contacts
async function pullContactsList() {
    const token = localStorage.getItem(KEY_TOKEN);
    if (!token) return;
    try {
        const res = await fetch('/api/contacts/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        contactsData = await res.json();
    } catch (e) {
        console.error(e);
    }
}

// Open active chat and load message history
async function openConversation(chatId, name, avatarUrl, isOnline) {
    activeChatId = chatId;
    activeChatOnline = (isOnline === 1);
    
    // Update E2EE UI state
    const e2eeBtn = document.getElementById('e2ee-toggle-btn');
    if (e2eeBtn) {
        if (window.e2eeKeys[chatId]) {
            e2eeBtn.innerHTML = `🛡️ <span class="mobile-hide">E2EE On</span>`;
            e2eeBtn.classList.add('btn-e2ee-active');
        } else {
            e2eeBtn.innerHTML = `🔒 <span class="mobile-hide">E2EE Off</span>`;
            e2eeBtn.classList.remove('btn-e2ee-active');
        }
    }
    isTypingStateSent = false;
    clearTimeout(typingTimeout);
    
    // Toggle active classes on sidebar
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    const activeItem = document.getElementById(`chat-item-${chatId}`);
    if (activeItem) activeItem.classList.add('active');
    
    // UI Screen transitions
    document.getElementById('chat-placeholder').classList.remove('active');
    document.getElementById('active-chat-container').classList.add('chat-active');
    document.querySelector('.chat-layout').classList.add('chat-active'); // For mobile mode
    
    // Set Header Info
    document.getElementById('active-chat-avatar').src = avatarUrl;
    document.getElementById('active-chat-title').textContent = name;
    
    const statusLbl = document.getElementById('active-chat-status');
    if (isOnline === 1) {
        statusLbl.textContent = "Online";
        statusLbl.className = "status-online";
    } else {
        statusLbl.textContent = "Offline";
        statusLbl.className = "status-offline";
    }
    
    // Pull history
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch(`/api/messages/history/${chatId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const messages = await res.json();
        
        const box = document.getElementById('messages-box');
        box.innerHTML = "";
        
        messages.forEach(msg => {
            appendMessageBubble(msg);
        });
        
        scrollMessagesToBottom();
        
        // Refresh sidebar lists to clear unread badges
        pullChatList();
        
    } catch (err) {
        console.error("Error loading chat history:", err);
    }
}

// Append Message Bubble into viewport
function appendMessageBubble(msg) {
    const box = document.getElementById('messages-box');
    const myUsername = localStorage.getItem(KEY_USERNAME);
    
    const isOutgoing = msg.sender_name === myUsername;
    
    // Check if this is a real-time echo of a previously offline-pending message
    if (isOutgoing && !msg.is_offline_pending) {
        const pendingCheckmarks = document.querySelectorAll('.checkmark.pending');
        for (const checkmark of pendingCheckmarks) {
            const bubble = checkmark.closest('.message-bubble');
            if (bubble && bubble.getAttribute('data-content') === msg.content) {
                checkmark.className = 'checkmark sent';
                checkmark.textContent = '✓';
                checkmark.id = `check-${msg.id}`;
                bubble.id = `msg-${msg.id}`;
                return; // Stop and prevent duplicate bubble rendering
            }
        }
    }

    const div = document.createElement('div');
    div.className = `message-bubble ${isOutgoing ? 'outgoing' : 'incoming'}`;
    div.id = `msg-${msg.id || msg.localId}`;
    div.setAttribute('data-content', msg.content);
    
    // Format timestamp
    let timeStr = "";
    try {
        const d = new Date(msg.timestamp);
        timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        timeStr = msg.timestamp;
    }
    
    // Checkmark rendering
    let checkmarkHtml = "";
    if (isOutgoing) {
        let checkClass = "sent";
        let checkText = "✓";
        if (msg.is_offline_pending) {
            checkClass = "pending";
            checkText = "🕒";
        } else if (msg.is_read === 1) {
            checkClass = "read";
            checkText = "✓✓";
        } else if (msg.is_delivered === 1) {
            checkClass = "delivered";
            checkText = "✓✓";
        }
        checkmarkHtml = `<span class="checkmark ${checkClass}" id="check-${msg.id || msg.localId}">${checkText}</span>`;
    }
    
    // Render media content or text
    let bodyContent = "";
    const msgType = msg.msg_type || msg.type;
    
    if (msgType === 'text') {
        if (msg.content && msg.content.startsWith('[E2EE] ')) {
            const msgTextId = `e2ee-msg-${msg.id}-${Math.random().toString(36).substr(2, 9)}`;
            bodyContent = `<span id="${msgTextId}" class="e2ee-locked-message">🔒 Encrypted message (no key)</span>`;
            
            // Decrypt asynchronously
            const chatId = msg.chat_id || activeChatId;
            const key = window.e2eeKeys[chatId];
            if (key) {
                const cipherPayload = msg.content.substring(7); // Remove "[E2EE] "
                decryptMessage(cipherPayload, key).then(decryptedText => {
                    const textEl = document.getElementById(msgTextId);
                    if (textEl) {
                        textEl.textContent = decryptedText;
                        textEl.classList.remove('e2ee-locked-message');
                        // Add green badge
                        const badge = document.createElement('span');
                        badge.className = 'e2ee-badge';
                        badge.textContent = '🛡️ E2EE';
                        textEl.appendChild(badge);
                    }
                }).catch(err => {
                    console.error("Decryption error:", err);
                    const textEl = document.getElementById(msgTextId);
                    if (textEl) {
                        textEl.textContent = "❌ Decryption failed (bad key)";
                    }
                });
            }
        } else {
            bodyContent = escapeHtml(msg.content);
        }
    } else if (msgType === 'image') {
        bodyContent = `
            <div class="media-card">
                <img src="${msg.file_path}?token=${localStorage.getItem(KEY_TOKEN)}" onclick="window.open(this.src)" style="cursor: pointer;">
            </div>
            <div class="media-caption">${escapeHtml(msg.content)}</div>
        `;
    } else if (msgType === 'video') {
        bodyContent = `
            <div class="media-card">
                <video src="${msg.file_path}?token=${localStorage.getItem(KEY_TOKEN)}" controls></video>
            </div>
            <div class="media-caption">${escapeHtml(msg.content)}</div>
        `;
    } else if (msgType === 'document') {
        const sizeStr = formatBytes(msg.size_bytes);
        bodyContent = `
            <div class="doc-card" onclick="window.open('${msg.file_path}?token=${localStorage.getItem(KEY_TOKEN)}')" style="cursor: pointer;">
                <span class="doc-icon">📄</span>
                <div class="doc-info">
                     <h4>${escapeHtml(msg.content)}</h4>
                     <span>${sizeStr}</span>
                </div>
            </div>
        `;
    } else if (msgType === 'audio') {
        const uniqueId = `audio-${msg.id}`;
        bodyContent = `
            <div class="audio-player-bubble neon-audio-player" id="${uniqueId}">
                <button class="audio-btn play-pause-btn audio-ctrl-btn" onclick="toggleAudioPlay(this, '${msg.file_path}?token=${localStorage.getItem(KEY_TOKEN)}')">▶</button>
                <div class="audio-wave-container audio-wave-bars" onclick="seekAudio(event, this)">
                    <div class="audio-track-fill" style="display: none;"></div>
                    <div class="audio-mock-waveform" style="display: flex; align-items: center; gap: 3px; width: 100%; height: 100%;">
                        <span class="audio-wave-bar" style="height: 10px;"></span>
                        <span class="audio-wave-bar" style="height: 22px;"></span>
                        <span class="audio-wave-bar" style="height: 14px;"></span>
                        <span class="audio-wave-bar" style="height: 20px;"></span>
                        <span class="audio-wave-bar" style="height: 18px;"></span>
                        <span class="audio-wave-bar" style="height: 12px;"></span>
                        <span class="audio-wave-bar" style="height: 20px;"></span>
                        <span class="audio-wave-bar" style="height: 16px;"></span>
                        <span class="audio-wave-bar" style="height: 24px;"></span>
                        <span class="audio-wave-bar" style="height: 10px;"></span>
                    </div>
                </div>
                <button class="audio-speed-btn audio-ctrl-btn" onclick="toggleAudioSpeed(this)">1.0x</button>
                <audio style="display: none;"></audio>
            </div>
        `;
    }
    
    div.innerHTML = `
        <div class="body">
            ${bodyContent}
        </div>
        <div class="meta">
            <span class="time">${timeStr}</span>
            ${checkmarkHtml}
        </div>
    `;
    box.appendChild(div);
}

function scrollMessagesToBottom() {
    const box = document.getElementById('messages-box');
    box.scrollTop = box.scrollHeight;
}

// -------------------------------------------------------------
// RICH CHAT & VOICE NOTE RECORDER
// -------------------------------------------------------------
async function sendTextMessage(e) {
    e.preventDefault();
    if (!activeChatId) return;
    
    const input = document.getElementById('chat-text-input');
    const content = input.value.trim();
    if (!content) return;
    
    input.value = "";
    
    // Trigger Send Message Particle Burst
    const form = document.getElementById('chat-send-form');
    if (form && window.triggerSendBurst) {
        const rect = form.getBoundingClientRect();
        const sendBtnX = rect.right - 20;
        const sendBtnY = rect.top + (rect.height / 2);
        window.triggerSendBurst(sendBtnX, sendBtnY);
    }
    
    let finalContent = content;
    const e2eeKey = window.e2eeKeys[activeChatId];
    if (e2eeKey) {
        try {
            const encrypted = await encryptMessage(content, e2eeKey);
            finalContent = `[E2EE] ${encrypted}`;
        } catch (err) {
            console.error("Encryption failed, sending as plaintext:", err);
        }
    }
    
    // Intercept offline messages
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        const localId = `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const myUsername = localStorage.getItem(KEY_USERNAME);
        
        const offlineMsg = {
            localId: localId,
            chat_id: activeChatId,
            sender_name: myUsername,
            content: finalContent,
            type: "text",
            timestamp: new Date().toISOString(),
            is_offline_pending: true
        };
        
        // Write to IndexedDB queue
        if (db) {
            try {
                const tx = db.transaction("offline_messages", "readwrite");
                const store = tx.objectStore("offline_messages");
                store.add(offlineMsg);
            } catch (err) {
                console.error("Failed to store message in IndexedDB:", err);
            }
        }
        
        // Render locally with clock
        appendMessageBubble(offlineMsg);
        scrollMessagesToBottom();
        return;
    }
    
    // Transmit over WebSocket
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            type: "text",
            chat_id: activeChatId,
            content: finalContent
        }));
    }
}

// Media attachment helper
function toggleAttachmentMenu() {
    document.getElementById('attachment-menu').classList.toggle('active');
}

let uploadCategory = 'document';
function triggerFileSelect(category) {
    uploadCategory = category;
    document.getElementById('attachment-menu').classList.remove('active');
    document.getElementById('media-file-input').click();
}

function showCompressModal(file) {
    pendingUploadFile = file;
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    document.getElementById('compress-file-size').textContent = `${sizeMB} MB`;
    document.getElementById('compress-modal').classList.add('active');
}

function closeCompressModal() {
    pendingUploadFile = null;
    document.getElementById('compress-modal').classList.remove('active');
}

function compressImage(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function(event) {
            const img = new Image();
            img.onload = function() {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;
                
                const maxDim = 1920;
                if (width > maxDim || height > maxDim) {
                    if (width > height) {
                        height = Math.round((height * maxDim) / width);
                        width = maxDim;
                    } else {
                        width = Math.round((width * maxDim) / height);
                        height = maxDim;
                    }
                }
                
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob((blob) => {
                    if (blob) {
                        let newName = file.name;
                        const lastDot = file.name.lastIndexOf('.');
                        if (lastDot !== -1) {
                            newName = file.name.substring(0, lastDot) + '_compressed.jpg';
                        } else {
                            newName = file.name + '_compressed.jpg';
                        }
                        const compressedFile = new File([blob], newName, { type: 'image/jpeg' });
                        resolve(compressedFile);
                    } else {
                        reject(new Error("Canvas compression failed"));
                    }
                }, 'image/jpeg', 0.75);
            };
            img.onerror = () => reject(new Error("Failed to load image"));
            img.src = event.target.result;
        };
        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsDataURL(file);
    });
}

async function handleMediaSelect(e) {
    const file = e.target.files[0];
    if (!file || !activeChatId) return;
    
    // Clear selection so the same file can be selected again
    e.target.value = '';
    
    const limit = 1.5 * 1024 * 1024; // 1.5MB
    const isCompressibleImage = file.type.startsWith('image/') && file.type !== 'image/gif';
    
    if (isCompressibleImage && file.size > limit) {
        showCompressModal(file);
    } else {
        uploadFile(file);
    }
}

async function uploadFile(file) {
    const token = localStorage.getItem(KEY_TOKEN);
    const indicator = document.getElementById('chat-upload-indicator');
    const nameLbl = document.getElementById('upload-name');
    const progressFill = document.getElementById('upload-bar-fill');
    const progressPct = document.getElementById('upload-pct');
    
    indicator.style.display = 'flex';
    nameLbl.textContent = file.name;
    progressFill.style.width = '0%';
    progressPct.textContent = '0%';
    
    const formData = new FormData();
    formData.append('file', file);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/media/upload', true);
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    
    xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            progressFill.style.width = `${percent}%`;
            progressPct.textContent = `${percent}%`;
        }
    };
    
    xhr.onload = () => {
        indicator.style.display = 'none';
        if (xhr.status === 200) {
            const resData = JSON.parse(xhr.responseText);
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    type: resData.type,
                    chat_id: activeChatId,
                    content: file.name,
                    file_path: resData.file_path,
                    size_bytes: resData.size
                }));
            }
        }
    };
    
    xhr.send(formData);
}

// E2EE Configuration Map (chatId -> CryptoKey)
window.e2eeKeys = {};

async function deriveE2EEKey(passphrase, saltText) {
    const encoder = new TextEncoder();
    const salt = encoder.encode(saltText);
    const passphraseKey = await window.crypto.subtle.importKey(
        "raw",
        encoder.encode(passphrase),
        { name: "PBKDF2" },
        false,
        ["deriveKey"]
    );
    return window.crypto.subtle.deriveKey(
        {
            name: "PBKDF2",
            salt: salt,
            iterations: 10000,
            hash: "SHA-256"
        },
        passphraseKey,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"]
    );
}

async function encryptMessage(plaintext, key) {
    const encoder = new TextEncoder();
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await window.crypto.subtle.encrypt(
        { name: "AES-GCM", iv: iv },
        key,
        encoder.encode(plaintext)
    );
    const cipherHex = Array.from(new Uint8Array(ciphertext)).map(b => b.toString(16).padStart(2, '0')).join('');
    const ivHex = Array.from(iv).map(b => b.toString(16).padStart(2, '0')).join('');
    return `${ivHex}:${cipherHex}`;
}

async function decryptMessage(combinedHex, key) {
    const [ivHex, cipherHex] = combinedHex.split(':');
    if (!ivHex || !cipherHex) {
        throw new Error("Invalid encrypted message format");
    }
    const iv = new Uint8Array(ivHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const ciphertext = new Uint8Array(cipherHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const decrypted = await window.crypto.subtle.decrypt(
        { name: "AES-GCM", iv: iv },
        key,
        ciphertext
    );
    const decoder = new TextDecoder();
    return decoder.decode(decrypted);
}

async function toggleE2EE() {
    if (!window.crypto || !window.crypto.subtle) {
        alert("End-to-End Encryption (E2EE) requires a secure context (HTTPS or localhost). It is disabled on non-secure origins.");
        return;
    }
    if (!activeChatId) {
        alert("Please select a chat room first.");
        return;
    }
    const btn = document.getElementById('e2ee-toggle-btn');
    if (window.e2eeKeys[activeChatId]) {
        delete window.e2eeKeys[activeChatId];
        btn.innerHTML = `🔒 <span class="mobile-hide">E2EE Off</span>`;
        btn.classList.remove('btn-e2ee-active');
        // Reload history to refresh view
        openConversation(activeChatId, document.getElementById('active-chat-title').textContent, document.getElementById('active-chat-avatar').src, activeChatOnline ? 1 : 0);
    } else {
        const passphrase = prompt("Enter E2EE Passphrase for this chat room. Both participants must use the exact same passphrase to decrypt messages:");
        if (!passphrase || !passphrase.trim()) return;
        
        try {
            const saltHex = `aethersync_salt_${activeChatId}`;
            const key = await deriveE2EEKey(passphrase, saltHex);
            window.e2eeKeys[activeChatId] = key;
            btn.innerHTML = `🛡️ <span class="mobile-hide">E2EE On</span>`;
            btn.classList.add('btn-e2ee-active');
            openConversation(activeChatId, document.getElementById('active-chat-title').textContent, document.getElementById('active-chat-avatar').src, activeChatOnline ? 1 : 0);
        } catch (err) {
            console.error(err);
            alert("Failed to derive encryption key.");
        }
    }
}

async function toggleVoiceRecording() {
    const btn = document.getElementById('voice-record-btn');
    if (!isRecording) {
        // Start recording
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            
            let recorderOptions = {};
            if (typeof MediaRecorder.isTypeSupported === 'function') {
                if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                    recorderOptions = { mimeType: 'audio/webm;codecs=opus' };
                } else if (MediaRecorder.isTypeSupported('audio/webm')) {
                    recorderOptions = { mimeType: 'audio/webm' };
                } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
                    recorderOptions = { mimeType: 'audio/ogg;codecs=opus' };
                }
            }
            recorderOptions.audioBitsPerSecond = 24000;
            
            mediaRecorder = new MediaRecorder(stream, recorderOptions);
            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };
            mediaRecorder.onstop = async () => {
                const mimeType = mediaRecorder.mimeType || 'audio/webm';
                const audioBlob = new Blob(audioChunks, { type: mimeType });
                await uploadVoiceNote(audioBlob, mimeType);
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start();
            isRecording = true;
            
            // Start timer display
            const timerSpan = document.getElementById('recording-timer');
            const timerDot = timerSpan.querySelector('.timer-dot');
            const timerText = document.getElementById('timer-text');
            
            if (timerDot) timerDot.style.display = 'inline-block';
            if (timerText) timerText.textContent = '0:00';
            timerSpan.style.display = 'inline-flex';
            
            const startTime = Date.now();
            window.voiceRecordInterval = setInterval(() => {
                const elapsed = Date.now() - startTime;
                const secs = Math.floor(elapsed / 1000);
                const mins = Math.floor(secs / 60);
                if (timerText) {
                    timerText.textContent = `${mins}:${String(secs % 60).padStart(2, '0')}`;
                }
            }, 500);
            btn.classList.add('recording');
            btn.setAttribute('aria-label', 'Stop recording');
        } catch (err) {
            console.error("Audio recording permission denied or failed:", err);
            alert("Failed to access microphone. Please grant audio permission.");
        }
    } else {
        // Stop recording
        if (mediaRecorder) {
            mediaRecorder.stop();
        }
        isRecording = false;
        // Clear timer
        if (window.voiceRecordInterval) {
            clearInterval(window.voiceRecordInterval);
            window.voiceRecordInterval = null;
        }
        // Show final length for a short period then hide
        const timerSpan = document.getElementById('recording-timer');
        const timerDot = timerSpan.querySelector('.timer-dot');
        const timerText = document.getElementById('timer-text');
        
        if (timerDot) timerDot.style.display = 'none';
        if (timerText) {
            const finalText = timerText.textContent;
            timerText.textContent = `Recorded: ${finalText}`;
        }
        
        setTimeout(() => {
            timerSpan.style.display = 'none';
        }, 4000);
        btn.classList.remove('recording');
        btn.textContent = "🎙️";
        btn.setAttribute('aria-label', 'Record voice note');
    }
}

async function uploadVoiceNote(audioBlob, mimeType) {
    const token = localStorage.getItem(KEY_TOKEN);
    let extension = 'webm';
    if (mimeType.includes('ogg')) {
        extension = 'ogg';
    }
    const filename = `voice_note_${Date.now()}.${extension}`;
    
    const formData = new FormData();
    formData.append('file', audioBlob, filename);
    
    try {
        const res = await fetch('/api/media/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        
        if (res.ok) {
            const data = await res.json();
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    type: "audio",
                    chat_id: activeChatId,
                    content: "Voice Message",
                    file_path: data.file_path,
                    size_bytes: data.size
                }));
            }
        }
    } catch (e) {
        console.error("Error uploading voice note:", e);
    }
}

// Custom Audio player controls
function toggleAudioPlay(btn, audioSrc) {
    const bubble = btn.closest('.audio-player-bubble');
    const fill = bubble.querySelector('.audio-track-fill');
    const audioEl = bubble.querySelector('audio');
    const speedBtn = bubble.querySelector('.audio-speed-btn');
    
    if (audioEl.src !== window.location.origin + audioSrc && audioEl.src !== audioSrc) {
        audioEl.src = audioSrc;
    }
    
    // Set active speed rate
    const currentSpeed = parseFloat(speedBtn.textContent) || 1.0;
    audioEl.playbackRate = currentSpeed;
    
    if (audioEl.paused) {
        // Pause all other playing audios
        document.querySelectorAll('audio').forEach(a => {
            if (a !== audioEl && !a.paused) {
                a.pause();
                const otherPlayBtn = a.closest('.audio-player-bubble')?.querySelector('.play-pause-btn');
                if (otherPlayBtn) otherPlayBtn.textContent = "▶";
                a.closest('.audio-player-bubble')?.classList.remove('playing');
            }
        });
        
        // Play audio
        audioEl.play();
        btn.textContent = "⏸";
        if (bubble) bubble.classList.add('playing');
        
        audioEl.ontimeupdate = () => {
            if (audioEl.duration) {
                const pct = (audioEl.currentTime / audioEl.duration) * 100;
                if (fill) fill.style.width = `${pct}%`;
            }
        };
        
        audioEl.onended = () => {
            btn.textContent = "▶";
            if (fill) fill.style.width = "0%";
            if (bubble) bubble.classList.remove('playing');
        };
    } else {
        // Pause audio
        audioEl.pause();
        btn.textContent = "▶";
        if (bubble) bubble.classList.remove('playing');
    }
}

function playNotificationSound() {
    const isSoundEnabled = localStorage.getItem('aethersync_sound_enabled') !== 'false';
    if (!isSoundEnabled) return;
    
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.05);
        oscillator.frequency.exponentialRampToValueAtTime(600, audioCtx.currentTime + 0.15);
        
        gainNode.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.25);
        
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.25);
    } catch (e) {
        console.error("Audio synthesis failed:", e);
    }
}

// -------------------------------------------------------------
// MODALS MANAGEMENT
// -------------------------------------------------------------
function toggleCreateChatModal() {
    document.getElementById('create-chat-modal').classList.toggle('active');
    switchModalTab('dm');
}

function switchModalTab(type) {
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.modal-panel').forEach(p => p.classList.remove('active'));
    
    if (type === 'dm') {
        document.getElementById('tab-new-dm').classList.add('active');
        document.getElementById('panel-new-dm').classList.add('active');
    } else {
        document.getElementById('tab-new-group').classList.add('active');
        document.getElementById('panel-new-group').classList.add('active');
    }
}

async function createDirectChat() {
    const contactName = document.getElementById('new-chat-username').value.trim();
    if (!contactName) return;
    
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch('/api/chats/create', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ recipient_username: contactName, type: "direct" })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to start chat");
        }
        
        const data = await res.json();
        toggleCreateChatModal();
        document.getElementById('new-chat-username').value = "";
        
        // Re-pull chat lists and open
        await pullChatList();
        openConversation(data.chat_id, contactName, `https://api.dicebear.com/7.x/adventurer/svg?seed=${contactName}`, 0);
        
    } catch (e) {
        alert(e.message);
    }
}

async function createGroupChat() {
    const groupName = document.getElementById('new-group-name').value.trim();
    if (!groupName) return;
    
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch('/api/chats/create', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ group_name: groupName, type: "group" })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to start group chat");
        }
        
        const data = await res.json();
        toggleCreateChatModal();
        document.getElementById('new-group-name').value = "";
        
        await pullChatList();
        openConversation(data.chat_id, groupName, `https://api.dicebear.com/7.x/initials/svg?seed=${groupName}`, 0);
        
    } catch (e) {
        alert(e.message);
    }
}

function toggleSettingsModal() {
    document.getElementById('settings-modal').classList.toggle('active');
    
    // Prefill settings
    document.getElementById('settings-avatar-url').value = document.getElementById('my-avatar').src;
    document.getElementById('settings-status').value = "Hey there! I am using AetherLink.";
    
    const soundEnabled = localStorage.getItem('aethersync_sound_enabled') !== 'false';
    document.getElementById('settings-sound-alert').checked = soundEnabled;
}

const ACCENT_MAP = {
    red: { color: '#ef4444', glow: 'rgba(239, 68, 68, 0.25)', border: 'rgba(239, 68, 68, 0.12)' },
    blue: { color: '#3b82f6', glow: 'rgba(59, 130, 246, 0.25)', border: 'rgba(59, 130, 246, 0.12)' },
    green: { color: '#10b981', glow: 'rgba(16, 185, 129, 0.25)', border: 'rgba(16, 185, 129, 0.12)' },
    amber: { color: '#fbbf24', glow: 'rgba(251, 191, 36, 0.25)', border: 'rgba(251, 191, 36, 0.12)' }
};

function setThemeAccent(name) {
    const theme = ACCENT_MAP[name] || ACCENT_MAP.red;
    localStorage.setItem('aethersync_accent_name', name);
    
    document.documentElement.style.setProperty('--accent-color', theme.color);
    document.documentElement.style.setProperty('--accent-glow', theme.glow);
    document.documentElement.style.setProperty('--border-color', theme.border);
}

async function saveSettings() {
    const avatarUrl = document.getElementById('settings-avatar-url').value;
    const statusText = document.getElementById('settings-status').value;
    const soundEnabled = document.getElementById('settings-sound-alert').checked;
    
    localStorage.setItem('aethersync_sound_enabled', soundEnabled);
    
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch('/api/contacts/update-profile', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ avatar_url: avatarUrl, status_text: statusText })
        });
        if (res.ok) {
            document.getElementById('my-avatar').src = avatarUrl;
            toggleSettingsModal();
        }
    } catch (e) {
        console.error("Failed to save settings:", e);
    }
}

// -------------------------------------------------------------
// SLIDE-OUT VAULT AND CLIPBOARD UTILITIES
// -------------------------------------------------------------
function toggleVaultPanel() {
    document.getElementById('clipboard-panel').classList.remove('active');
    const vault = document.getElementById('vault-panel');
    vault.classList.toggle('active');
    if (vault.classList.contains('active')) {
        pullVaultFilesList();
    }
}

function toggleClipboardPanel() {
    document.getElementById('vault-panel').classList.remove('active');
    const clip = document.getElementById('clipboard-panel');
    clip.classList.toggle('active');
    if (clip.classList.contains('active')) {
        pullClipboard();
    }
}

// Vault Files Upload
function triggerVaultUpload() {
    document.getElementById('vault-file-input').click();
}

async function handleVaultUploadSelect(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    const token = localStorage.getItem(KEY_TOKEN);
    for (let file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            await fetch('/api/files/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
        } catch (e) {
            console.error("Upload error:", e);
        }
    }
    pullVaultFilesList();
    pullChatList(); // Refresh chats last-msg if files uploaded
}

async function pullVaultFilesList() {
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch('/api/files/list', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const files = await res.json();
        
        const list = document.getElementById('vault-file-list');
        list.innerHTML = "";
        
        if (files.length === 0) {
            list.innerHTML = `<div style="text-align: center; color: var(--text-muted); font-size: 11px; padding-top: 20px;">No files in vault folder.</div>`;
            return;
        }
        
        files.forEach(f => {
            const div = document.createElement('div');
            div.className = 'vault-file-item';
            div.innerHTML = `
                <div class="vault-file-info">
                    <h4 title="${f.name}">${f.name}</h4>
                    <span>${formatBytes(f.size)}</span>
                </div>
                <div class="vault-actions">
                    <button class="btn-icon btn-icon-dl" onclick="downloadFile('${f.name}')">📥</button>
                    <button class="btn-icon btn-icon-del" onclick="deleteVaultFile('${f.name}')">🗑️</button>
                </div>
            `;
            list.appendChild(div);
        });
        
        // Re-apply search filter if there's any active text
        filterVaultFiles();
    } catch (e) {
        console.error("Failed to load vault files:", e);
    }
}

function filterVaultFiles() {
    const query = (document.getElementById('vault-search-input')?.value || '').toLowerCase().trim();
    const items = document.querySelectorAll('.vault-file-item');
    items.forEach(item => {
        const fileName = (item.querySelector('.vault-file-info h4')?.textContent || '').toLowerCase();
        if (fileName.includes(query)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}


async function deleteVaultFile(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch(`/api/files/delete/${encodeURIComponent(filename)}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            pullVaultFilesList();
        }
    } catch (err) {
        console.error("Error deleting vault file:", err);
    }
}

// Clipboard Pull/Push
async function pullClipboard() {
    const token = localStorage.getItem(KEY_TOKEN);
    try {
        const res = await fetch('/api/clipboard/get', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        document.getElementById('clipboard-text').value = data.content;
    } catch (e) {
        console.error("Failed to pull clipboard:", e);
    }
}

async function pushClipboard() {
    const token = localStorage.getItem(KEY_TOKEN);
    const content = document.getElementById('clipboard-text').value;
    try {
        const res = await fetch('/api/clipboard/set', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ content })
        });
        if (res.ok) {
            const txt = document.getElementById('clipboard-text');
            txt.style.borderColor = 'var(--neon-green)';
            setTimeout(() => { txt.style.borderColor = 'var(--border-color)'; }, 500);
        }
    } catch (e) {
        console.error(e);
    }
}

// -------------------------------------------------------------
// FILTERING & UTILITIES
// -------------------------------------------------------------
function filterChatList() {
    const q = document.getElementById('chat-search').value.toLowerCase().trim();
    if (!q) {
        renderChatList(chatsData);
        return;
    }
    
    // Filter locally based on search query
    const filtered = chatsData.filter(c => c.name.toLowerCase().includes(q));
    renderChatList(filtered);
}

function updateContactOnlineStatus(userId, status) {
    // If the active conversation partner is updated
    pullChatList(); // Triggers sidebar statuses re-render
}

function updateCheckmarkToRead(messageId) {
    const el = document.getElementById(`check-${messageId}`);
    if (el) {
        el.className = "checkmark read";
        el.textContent = "✓✓";
    }
}

function updateCheckmarkToDelivered(messageId) {
    const el = document.getElementById(`check-${messageId}`);
    if (el && !el.classList.contains('read')) {
        el.className = "checkmark delivered";
        el.textContent = "✓✓";
    }
}

function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// -------------------------------------------------------------
// CYBERPUNK UPGRADES: TYPING, DRAG-DROP, CUSTOM PLAYERS
// -------------------------------------------------------------

// Ephemeral Typing logic
function handleTypingIndicator() {
    if (!activeChatId || !socket || socket.readyState !== WebSocket.OPEN) return;
    
    if (!isTypingStateSent) {
        isTypingStateSent = true;
        socket.send(JSON.stringify({
            type: "typing",
            chat_id: activeChatId,
            typing: true
        }));
    }
    
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        isTypingStateSent = false;
        socket.send(JSON.stringify({
            type: "typing",
            chat_id: activeChatId,
            typing: false
        }));
    }, 1500);
}

function handleIncomingTyping(senderName, typing) {
    const statusLbl = document.getElementById('active-chat-status');
    if (!statusLbl) return;
    
    if (typing) {
        statusLbl.textContent = `${senderName} is typing...`;
        statusLbl.className = "status-typing animating-pulse";
    } else {
        if (activeChatOnline) {
            statusLbl.textContent = "Online";
            statusLbl.className = "status-online";
        } else {
            statusLbl.textContent = "Offline";
            statusLbl.className = "status-offline";
        }
    }
}

// Fullscreen Drag & Drop
function handleDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!activeChatId) return;
    document.getElementById('drag-drop-overlay').classList.add('active');
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    
    // Check if we left the window entirely
    const rect = document.getElementById('drag-drop-overlay').getBoundingClientRect();
    if (e.clientX <= rect.left || e.clientX >= rect.right || e.clientY <= rect.top || e.clientY >= rect.bottom) {
        document.getElementById('drag-drop-overlay').classList.remove('active');
    }
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drag-drop-overlay').classList.remove('active');
    
    if (!activeChatId) return;
    
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
        // Upload the first file dropped
        const file = files[0];
        const limit = 1.5 * 1024 * 1024;
        const isCompressibleImage = file.type.startsWith('image/') && file.type !== 'image/gif';
        
        if (isCompressibleImage && file.size > limit) {
            showCompressModal(file);
        } else {
            uploadFile(file);
        }
    }
}

// Custom Audio Speed controller
function toggleAudioSpeed(btn) {
    const bubble = btn.closest('.audio-player-bubble');
    const audioEl = bubble.querySelector('audio');
    
    let speed = parseFloat(btn.textContent) || 1.0;
    if (speed === 1.0) {
        speed = 1.5;
    } else if (speed === 1.5) {
        speed = 2.0;
    } else {
        speed = 1.0;
    }
    
    btn.textContent = `${speed.toFixed(1)}x`;
    if (audioEl) {
        audioEl.playbackRate = speed;
    }
}

// Audio Seeking
function seekAudio(event, trackContainer) {
    const bubble = trackContainer.closest('.audio-player-bubble');
    const audioEl = bubble.querySelector('audio');
    const fill = bubble.querySelector('.audio-track-fill');
    
    if (audioEl && audioEl.duration) {
        const rect = trackContainer.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const width = rect.width;
        const pct = clickX / width;
        audioEl.currentTime = pct * audioEl.duration;
        fill.style.width = `${pct * 100}%`;
    }
}

// Intercept page unload during active recording to prevent data loss
window.addEventListener('beforeunload', (event) => {
    if (typeof isRecording !== 'undefined' && isRecording) {
        event.preventDefault();
        event.returnValue = 'You have an active recording in progress. If you leave now, it will be lost.';
        return event.returnValue;
    }
});

// IndexedDB Initialization
function initIndexedDB() {
    if (!window.indexedDB) {
        console.warn("IndexedDB not supported in this browser.");
        return;
    }
    const request = indexedDB.open("AetherSyncOfflineDB", 1);
    request.onupgradeneeded = (event) => {
        db = event.target.result;
        if (!db.objectStoreNames.contains("offline_messages")) {
            db.createObjectStore("offline_messages", { keyPath: "localId" });
        }
    };
    request.onsuccess = (event) => {
        db = event.target.result;
        console.log("[IndexedDB] Offline store initialized successfully.");
    };
    request.onerror = (event) => {
        console.error("IndexedDB error:", event.target.error);
    };
}

// Flush and send stored offline messages once WebSocket recovers
function flushOfflineMessages() {
    if (!db) return;
    try {
        const tx = db.transaction("offline_messages", "readwrite");
        const store = tx.objectStore("offline_messages");
        const request = store.getAll();
        
        request.onsuccess = () => {
            const messages = request.result;
            if (messages.length === 0) return;
            
            console.log(`[WS] Flushing ${messages.length} offline queued messages...`);
            
            messages.forEach(msg => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        type: "text",
                        chat_id: msg.chat_id,
                        content: msg.content
                    }));
                }
            });
            
            // Clear IndexedDB store once flushed
            const clearTx = db.transaction("offline_messages", "readwrite");
            clearTx.objectStore("offline_messages").clear();
        };
    } catch (err) {
        console.error("Error flushing offline messages:", err);
    }
}

// Connection Banner Helpers
function showConnectionWarningBanner() {
    const banner = document.getElementById('connection-status-banner');
    if (banner) {
        banner.textContent = "Offline - Reconnecting to AetherSync...";
        banner.classList.remove('connected-alert');
        banner.classList.add('visible');
    }
}

function showConnectionSuccessBanner() {
    const banner = document.getElementById('connection-status-banner');
    if (banner) {
        banner.textContent = "Connected!";
        banner.classList.add('connected-alert');
        banner.classList.add('visible');
        setTimeout(() => {
            banner.classList.remove('visible');
        }, 1500);
    }
}

function closeActiveChat() {
    activeChatId = null;
    document.getElementById('active-chat-container').classList.remove('chat-active');
    document.querySelector('.chat-layout').classList.remove('chat-active');
    document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
    document.getElementById('chat-placeholder').classList.add('active');
}

function runBootDiagnosticSequence() {
    const screen = document.getElementById('cyber-boot-screen');
    const log = document.getElementById('boot-terminal-log');
    if (!screen || !log) return;
    
    const logs = [
        "[OS INITIALIZING] ... OK",
        "[RESOLVING LAN NETWORK SUBNETS] ... OK",
        "[SCANNING ACTIVE PEERS ON PORT 8085] ... OK",
        "[DECRYPTING ENCRYPTION VAULTS] ... OK",
        "[ESTABLISHING ENCRYPTED SOCKET HANDSHAKE] ... OK",
        "[BOOT SEQUENCE COMPLETE] ... BOOTING HUB"
    ];
    
    let index = 0;
    function printNextLog() {
        if (index < logs.length) {
            log.innerHTML += `<div>&gt; ${logs[index]}</div>`;
            log.scrollTop = log.scrollHeight;
            index++;
            setTimeout(printNextLog, 220);
        } else {
            setTimeout(() => {
                screen.style.opacity = '0';
                setTimeout(() => {
                    screen.style.display = 'none';
                }, 500);
            }, 300);
        }
    }
    
    setTimeout(printNextLog, 150);
}





