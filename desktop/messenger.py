import os
import sys
import socket
import json
import webview
from tkinter import simpledialog, Tk

UDP_PORT = 8085

def discover_server():
    # Setup socket to listen for broadcast presence
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(2.0) # Wait up to 2 seconds
    try:
        sock.bind(("", UDP_PORT))
    except Exception:
        return None
        
    try:
        data, addr = sock.recvfrom(1024)
        payload = json.loads(data.decode('utf-8'))
        if payload.get("service") == "aethersync":
            ip = payload.get("ip")
            port = payload.get("port", 8080)
            return f"http://{ip}:{port}"
    except Exception:
        pass
    finally:
        sock.close()
    return None

def main():
    print("[Discovery] Scanning local Wi-Fi for AetherSync server...")
    server_url = discover_server()
    
    if not server_url:
        # Fallback 1: check if server runs locally
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", 8080))
            s.close()
            server_url = "http://127.0.0.1:8080"
        except Exception:
            pass
            
    if not server_url:
        # Fallback 2: Ask user for IP using a simple Tkinter dialog
        root = Tk()
        root.withdraw() # Hide main window
        ans = simpledialog.askstring(
            "AetherSync Server Connection", 
            "Could not auto-discover Server Hub on Wi-Fi.\nPlease enter the Server IP address shown on the Hub Controller (e.g. 192.168.1.10):",
            initialvalue="192.168.1.10"
        )
        root.destroy()
        if ans:
            if not ans.startswith("http"):
                server_url = f"http://{ans}:8080"
            else:
                server_url = ans
        else:
            sys.exit(0)
            
    # Resolve absolute path to custom app icon
    ico_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "icon.ico"))
    if not os.path.exists(ico_path):
        ico_path = None

    # Launch WebView app
    print(f"[Messenger] Launching native window client pointing to: {server_url}")
    
    # Configure webview window
    webview.create_window(
        "AetherLink Client", 
        server_url, 
        width=1020, 
        height=740,
        resizable=True
    )
    
    # Start webview
    webview.start()

if __name__ == "__main__":
    main()
