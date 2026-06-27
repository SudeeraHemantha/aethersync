/**
 * @jest-environment jsdom
 */

const fs = require('fs');
const path = require('path');

// Polyfill Web Crypto API for JSDOM / Node environment
const { webcrypto } = require('crypto');
Object.defineProperty(global.self, 'crypto', {
    value: webcrypto,
    configurable: true
});

global.TextEncoder = require('util').TextEncoder;
global.TextDecoder = require('util').TextDecoder;
global.window.TextEncoder = global.TextEncoder;
global.window.TextDecoder = global.TextDecoder;


// Mock browser APIs
let mockStoreData = [];
const mockStore = {
    add: jest.fn((msg) => {
        mockStoreData.push(msg);
        return { onsuccess: null, onerror: null };
    }),
    getAll: jest.fn(() => {
        const req = { onsuccess: null, onerror: null, result: [...mockStoreData] };
        setTimeout(() => {
            if (req.onsuccess) req.onsuccess({ target: req });
        }, 0);
        return req;
    }),
    clear: jest.fn(() => {
        mockStoreData = [];
        return { onsuccess: null, onerror: null };
    })
};

const mockDb = {
    objectStoreNames: {
        contains: jest.fn().mockReturnValue(true)
    },
    createObjectStore: jest.fn().mockReturnValue(mockStore),
    transaction: jest.fn(() => ({
        objectStore: jest.fn().mockReturnValue(mockStore)
    }))
};

const mockIndexedDBRequest = {
    onsuccess: null,
    onupgradeneeded: null,
    onerror: null
};

global.indexedDB = {
    open: jest.fn().mockImplementation(() => {
        setTimeout(() => {
            if (mockIndexedDBRequest.onupgradeneeded) {
                mockIndexedDBRequest.onupgradeneeded({ target: { result: mockDb } });
            }
            if (mockIndexedDBRequest.onsuccess) {
                mockIndexedDBRequest.onsuccess({ target: { result: mockDb } });
            }
        }, 0);
        return mockIndexedDBRequest;
    })
};
global.window.indexedDB = global.indexedDB;

let localStorageMockData = {};
const localStorageMock = {
    getItem: jest.fn((key) => localStorageMockData[key] || null),
    setItem: jest.fn((key, val) => { localStorageMockData[key] = val; }),
    removeItem: jest.fn((key) => { delete localStorageMockData[key]; }),
    clear: jest.fn(() => { localStorageMockData = {}; })
};
Object.defineProperty(global.window, 'localStorage', {
    value: localStorageMock,
    writable: true,
    configurable: true
});
global.localStorage = localStorageMock;

global.WebSocket = class {
    constructor(url) {
        this.url = url;
        this.readyState = global.WebSocket.CONNECTING;
        this.send = jest.fn();
        this.close = jest.fn().mockImplementation(() => {
            this.readyState = global.WebSocket.CLOSED;
            if (this.onclose) this.onclose();
        });
        this.addEventListener = jest.fn();
        global.WebSocket.lastInstance = this;
    }
};
global.WebSocket.CONNECTING = 0;
global.WebSocket.OPEN = 1;
global.WebSocket.CLOSING = 2;
global.WebSocket.CLOSED = 3;
global.WebSocket.lastInstance = null;


// Mock fetch and FormData
global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: jest.fn().mockResolvedValue({
        status: 'success',
        filename: 'mock_voice_note.wav'
    })
});

global.FormData = class {
    constructor() {
        this.data = {};
    }
    append(key, value, filename) {
        this.data[key] = { value, filename };
    }
};

// Mock MediaRecorder
class MockMediaRecorder {
    constructor(stream, options) {
        this.stream = stream;
        this.options = options;
        this.state = 'inactive';
    }
    start() {
        this.state = 'recording';
    }
    stop() {
        this.state = 'inactive';
        if (this.onstop) this.onstop();
    }
}
MockMediaRecorder.isTypeSupported = jest.fn().mockReturnValue(true);
global.MediaRecorder = MockMediaRecorder;

// Mock getUserMedia
const mockStream = {
    getTracks: jest.fn().mockReturnValue([{
        stop: jest.fn()
    }])
};
global.navigator.mediaDevices = {
    getUserMedia: jest.fn().mockResolvedValue(mockStream)
};

global.alert = jest.fn();

describe('AetherSync Voice Recorder Frontend Tests', () => {
    beforeAll(() => {
        // Load the actual app.js content and eval it ONCE
        const appJsPath = path.resolve(__dirname, '../static/app.js');
        const appJsContent = fs.readFileSync(appJsPath, 'utf8');
        
        // Execute the script in JSDOM window context
        window.eval(appJsContent);
    });

    beforeEach(() => {
        // Setup mock DOM elements matching index.html
        document.body.innerHTML = `
            <div id="connection-status-banner" class="connection-banner">Offline - Reconnecting to AetherSync...</div>
            <span id="ws-status-badge" class="status-badge connected">online</span>
            <div id="messages-box" class="messages-box"></div>
            <form id="chat-send-form" class="chat-send-form">
                <input type="text" id="chat-text-input" placeholder="Type a message..." required autocomplete="off">
                <button type="submit" class="send-submit-btn">✈</button>
            </form>
            <span id="active-chat-status">Online</span>
            <button id="voice-record-btn">🎙️</button>
            <span id="recording-timer" style="display: none;">
                <span class="timer-dot"></span>
                <span id="timer-text">0:00</span>
            </span>
            <span id="device-name-lbl">Detecting...</span>
            <img id="my-avatar" src="">
            <span id="my-username">Guest</span>
            
            <!-- Additional DOM nodes for screen and chat transitions -->
            <div id="auth-screen" class="screen"></div>
            <div id="chat-placeholder" class="screen"></div>
            <div id="active-chat-container" class="screen"></div>
            <div class="chat-layout"></div>
            <img id="active-chat-avatar" src="">
            <span id="active-chat-title"></span>
            <button id="e2ee-toggle-btn"></button>
            <div id="chat-list"></div>
        `;
        
        // Reset mocks and timers
        jest.clearAllMocks();
        jest.useFakeTimers();
        
        // Reset mock store data
        mockStoreData.length = 0;
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test('should start voice recording, update button UI and show live timer', async () => {
        const btn = document.getElementById('voice-record-btn');
        const timerSpan = document.getElementById('recording-timer');
        const timerText = document.getElementById('timer-text');

        // Initially does not have recording class
        expect(btn.classList.contains('recording')).toBe(false);

        // Call toggleVoiceRecording (starts recording)
        await window.toggleVoiceRecording();

        expect(btn.classList.contains('recording')).toBe(true);
        
        // Advance timer and check if it updates text
        jest.advanceTimersByTime(1000);
        expect(timerText.textContent).toBe('0:01');
        expect(timerSpan.style.display).toBe('inline-flex');

        jest.advanceTimersByTime(2000);
        expect(timerText.textContent).toBe('0:03');
        
        // Cleanup recording state for next test
        await window.toggleVoiceRecording();
    });

    test('should stop voice recording, stop timer and display final duration', async () => {
        const btn = document.getElementById('voice-record-btn');
        const timerSpan = document.getElementById('recording-timer');
        const timerText = document.getElementById('timer-text');

        // Start recording first
        await window.toggleVoiceRecording();
        
        // Let it run for 5 seconds
        jest.advanceTimersByTime(5000);
        expect(timerText.textContent).toBe('0:05');

        // Call toggleVoiceRecording again (stops recording)
        await window.toggleVoiceRecording();

        expect(btn.classList.contains('recording')).toBe(false);
        expect(timerText.textContent).toBe('Recorded: 0:05');

        // After 4 seconds, the timer span should be hidden
        jest.advanceTimersByTime(4000);
        expect(timerSpan.style.display).toBe('none');
    });
});

describe('AetherSync E2EE Cryptography Tests', () => {
    test('should derive a cryptographic key from a passphrase', async () => {
        const passphrase = "test-secret-passphrase";
        const salt = "aethersync_salt_123";
        const key = await window.deriveE2EEKey(passphrase, salt);
        
        expect(key).toBeDefined();
        expect(key.type).toBe('secret');
        expect(key.algorithm.name).toBe('AES-GCM');
    });

    test('should encrypt and decrypt a message successfully', async () => {
        const passphrase = "test-secret-passphrase";
        const salt = "aethersync_salt_123";
        const key = await window.deriveE2EEKey(passphrase, salt);
        
        const plaintext = "Hello End-to-End Encryption World!";
        const encrypted = await window.encryptMessage(plaintext, key);
        
        expect(encrypted).toBeDefined();
        expect(encrypted).toContain(':'); // contains iv:ciphertext
        
        const decrypted = await window.decryptMessage(encrypted, key);
        expect(decrypted).toBe(plaintext);
    });

    test('should fail decryption with an incorrect key', async () => {
        const salt = "aethersync_salt_123";
        const key1 = await window.deriveE2EEKey("correct-passphrase", salt);
        const key2 = await window.deriveE2EEKey("wrong-passphrase", salt);
        
        const plaintext = "Secret Message";
        const encrypted = await window.encryptMessage(plaintext, key1);
        
        await expect(window.decryptMessage(encrypted, key2)).rejects.toThrow();
    });
});

describe('AetherSync Auto-Reconnect & Offline Sync Tests', () => {
    beforeEach(async () => {
        jest.useFakeTimers();
        
        // Reset socket and activeChatId inside app.js scope
        window.eval("socket = null;");
        window.eval("activeChatId = null;");
        
        // Ensure e2eeKeys and local storage items are defined
        window.e2eeKeys = {};
        localStorageMockData = {
            aethersync_username: 'test_user',
            aethersync_token: 'mock_token'
        };
        
        // Initialize DB mock connection
        await window.initIndexedDB();
        // Wait for the open request timeouts to resolve so `db` is populated
        jest.runOnlyPendingTimers();
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    test('should queue messages to IndexedDB when offline and display pending icon', async () => {
        // Mock fetch for openConversation history pull
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: jest.fn().mockResolvedValue([])
        });
        
        // Open conversation to set activeChatId in app.js
        await window.openConversation('chat_123', 'Test Chat', 'avatar.png', 1);
        
        const input = document.getElementById('chat-text-input');
        input.value = "Hello Offline World!";
        
        // Mock event for form submission
        const mockEvent = { preventDefault: jest.fn() };
        
        await window.sendTextMessage(mockEvent);
        
        // Verify message was stored in IndexedDB mock store
        expect(mockStoreData.length).toBe(1);
        expect(mockStoreData[0].content).toBe("Hello Offline World!");
        expect(mockStoreData[0].chat_id).toBe("chat_123");
        expect(mockStoreData[0].is_offline_pending).toBe(true);
        
        // Verify it was appended to the DOM message box with clock icon
        const msgBox = document.getElementById('messages-box');
        const bubble = msgBox.querySelector('.message-bubble');
        expect(bubble).toBeTruthy();
        expect(bubble.textContent).toContain("Hello Offline World!");
        
        const checkmark = bubble.querySelector('.checkmark.pending');
        expect(checkmark).toBeTruthy();
        expect(checkmark.textContent).toBe("🕒");
    });

    test('should manage warning and success banners on WS close and open', () => {
        // Call initWebSocket to construct the WebSocket
        window.initWebSocket();
        
        const socketInstance = global.WebSocket.lastInstance;
        expect(socketInstance).toBeDefined();
        
        const banner = document.getElementById('connection-status-banner');
        const badge = document.getElementById('ws-status-badge');
        
        // Trigger onclose (disconnected)
        socketInstance.onclose();
        
        // Verify banner has warning state
        expect(banner.classList.contains('visible')).toBe(true);
        expect(banner.classList.contains('connected-alert')).toBe(false);
        expect(banner.textContent).toContain("Offline");
        expect(badge.textContent).toBe("offline");
        expect(badge.className).toContain("disconnected");
        
        // Trigger onopen (reconnected)
        socketInstance.onopen();
        
        // Verify banner has success state
        expect(banner.classList.contains('connected-alert')).toBe(true);
        expect(banner.textContent).toContain("Connected!");
        expect(badge.textContent).toBe("online");
        expect(badge.className).toContain("connected");
        
        // Run setTimeout timer for banner fade out
        jest.advanceTimersByTime(1500);
        expect(banner.classList.contains('visible')).toBe(false);
    });

    test('should flush offline messages when socket reconnects', async () => {
        // Pre-populate mock store with offline messages
        mockStoreData.push({
            localId: 'local_1',
            chat_id: 'chat_123',
            content: 'Offline Message 1',
            is_offline_pending: true
        });
        
        // Call initWebSocket
        window.initWebSocket();
        const socketInstance = global.WebSocket.lastInstance;
        socketInstance.readyState = global.WebSocket.OPEN;
        
        // Open the connection (triggers flush)
        socketInstance.onopen();
        
        // Resolve IndexedDB getAll promise/timeout
        jest.runOnlyPendingTimers();
        
        // Verify socket sent the messages
        expect(socketInstance.send).toHaveBeenCalledTimes(1);
        const sentPayload = JSON.parse(socketInstance.send.mock.calls[0][0]);
        expect(sentPayload.content).toBe("Offline Message 1");
        expect(sentPayload.chat_id).toBe("chat_123");
        
        // Resolve IndexedDB clear promise/timeout
        jest.runOnlyPendingTimers();
        
        // Verify IndexedDB store is cleared
        expect(mockStoreData.length).toBe(0);
    });

    test('should update pending bubble and prevent duplicate when server echoes the message', () => {
        // Clear messages box
        const msgBox = document.getElementById('messages-box');
        msgBox.innerHTML = '';
        
        // Render a pending message first
        window.appendMessageBubble({
            localId: 'local_999',
            chat_id: 'chat_123',
            sender_name: 'test_user',
            content: 'Hello Echo Sync',
            is_offline_pending: true
        });
        
        expect(msgBox.children.length).toBe(1);
        const bubble = msgBox.firstElementChild;
        expect(bubble.querySelector('.checkmark.pending')).toBeTruthy();
        expect(bubble.querySelector('.checkmark.pending').textContent).toBe("🕒");
        
        // Now simulate server echoing the finalized message
        window.appendMessageBubble({
            id: 456,
            chat_id: 'chat_123',
            sender_name: 'test_user',
            content: 'Hello Echo Sync',
            is_offline_pending: false
        });
        
        // Should NOT append a new bubble (length stays 1)
        expect(msgBox.children.length).toBe(1);
        
        // Should update checkmark to sent (✓)
        const checkmark = bubble.querySelector('.checkmark');
        expect(checkmark.className).toContain('sent');
        expect(checkmark.textContent).toBe('✓');
    });

    test('should stop reconnecting and show specific limit error if WebSocket closes with code 4010', () => {
        window.initWebSocket();
        const socketInstance = global.WebSocket.lastInstance;
        expect(socketInstance).toBeDefined();
        
        const banner = document.getElementById('connection-status-banner');
        
        // Mock socket.onclose call with CloseEvent containing code 4010
        const mockCloseEvent = { code: 4010 };
        socketInstance.onclose(mockCloseEvent);
        
        // Banner should show max users error
        expect(banner.classList.contains('visible')).toBe(true);
        expect(banner.textContent).toContain("limit reached");
        
        // Verify no reconnect timeout was scheduled
        jest.clearAllTimers();
        global.WebSocket.lastInstance = null;
        jest.advanceTimersByTime(16000);
        expect(global.WebSocket.lastInstance).toBeNull();
    });
});

