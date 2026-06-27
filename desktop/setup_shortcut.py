import os
import sys
import struct
import subprocess

def create_local_shortcut():
    print("=== AETHERSYNC SHORTCUT & ENVIRONMENT INITIALIZER ===")
    
    # Get absolute paths relative to this script
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Detect Desktop path from Windows registry for redirected folders (OneDrive)
    desktop_dir = None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        desktop_dir, _ = winreg.QueryValueEx(key, "Desktop")
        desktop_dir = os.path.expandvars(desktop_dir)
        winreg.CloseKey(key)
    except Exception:
        pass
        
    if not desktop_dir or not os.path.exists(desktop_dir):
        desktop_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "Desktop")
        onedrive_desktop = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "OneDrive", "Desktop")
        if os.path.exists(onedrive_desktop):
            desktop_dir = onedrive_desktop
            
    shortcut_path_hub = os.path.join(desktop_dir, "AetherSync Hub.lnk")
    shortcut_path_msg = os.path.join(desktop_dir, "AetherLink Messenger.lnk")
    
    launcher_path = os.path.join(base_dir, "desktop", "launcher.py")
    messenger_path = os.path.join(base_dir, "desktop", "messenger.py")
    ico_path = os.path.join(base_dir, "desktop", "icon.ico")
    png_path = os.path.join(base_dir, "frontend", "static", "icon.png")
    
    # Locate absolute path to pythonw.exe
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = "pythonw.exe"
        
    print(f"[*] Base Directory: {base_dir}")
    print(f"[*] Desktop Path: {desktop_dir}")
    print(f"[*] Pythonw Path: {pythonw_path}")
    
    # 1. Convert PNG to ICO if necessary
    # If icon exists but is old style, or doesn't exist, generate it using Pillow if available
    need_build_icon = True
    if os.path.exists(ico_path):
        # We can force rebuild to ensure it uses the high-quality Pillow version
        try:
            os.remove(ico_path)
        except Exception:
            need_build_icon = False
            
    if need_build_icon and os.path.exists(png_path):
        try:
            print("[*] Compiling custom app icon using Pillow...")
            from PIL import Image
            img = Image.open(png_path)
            img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            print("[+] Custom multi-resolution icon compiled successfully using Pillow.")
        except Exception as e_pil:
            print(f"[*] Pillow compilation not available or failed ({e_pil}). Falling back to raw header writer...")
            try:
                with open(png_path, "rb") as f:
                    png_data = f.read()
                png_size = len(png_data)
                header = struct.pack("<HHH", 0, 1, 1)
                entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, png_size, 22)
                with open(ico_path, "wb") as f:
                    f.write(header + entry + png_data)
                print("[+] Custom icon compiled successfully using raw writer.")
            except Exception as e:
                print(f"[-] Icon compilation failed: {e}")
                
    # 2. Build Shortcut LNK files using PowerShell COM Object
    print("[*] Registering shortcut parameters with Windows...")
    ps_cmd = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    
    # Create Hub Shortcut
    $ShortcutHub = $WshShell.CreateShortcut("{shortcut_path_hub}")
    $ShortcutHub.TargetPath = "{pythonw_path}"
    $ShortcutHub.Arguments = '"{launcher_path}"'
    $ShortcutHub.WorkingDirectory = "{os.path.join(base_dir, 'desktop')}"
    if (Test-Path "{ico_path}") {{
        $ShortcutHub.IconLocation = "{ico_path},0"
    }}
    $ShortcutHub.Save()
    
    # Create Messenger Shortcut
    $ShortcutMsg = $WshShell.CreateShortcut("{shortcut_path_msg}")
    $ShortcutMsg.TargetPath = "{pythonw_path}"
    $ShortcutMsg.Arguments = '"{messenger_path}"'
    $ShortcutMsg.WorkingDirectory = "{os.path.join(base_dir, 'desktop')}"
    if (Test-Path "{ico_path}") {{
        $ShortcutMsg.IconLocation = "{ico_path},0"
    }}
    $ShortcutMsg.Save()
    """
    
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
        print(f"[SUCCESS] Hub shortcut created at: {shortcut_path_hub}")
        print(f"[SUCCESS] Messenger shortcut created at: {shortcut_path_msg}")
        
        # Copy to Start Menu for search indexes
        start_menu_dir = os.path.join(os.environ.get("APPDATA"), "Microsoft\\Windows\\Start Menu\\Programs")
        if os.path.exists(start_menu_dir):
            import shutil
            shutil.copy2(shortcut_path_hub, os.path.join(start_menu_dir, "AetherSync Hub.lnk"))
            shutil.copy2(shortcut_path_msg, os.path.join(start_menu_dir, "AetherLink Messenger.lnk"))
            print("[+] Copied both shortcuts to Start Menu for instant keyboard search.")
    except Exception as e:
        print(f"[-] Failed to register shortcuts: {e}")

if __name__ == "__main__":
    create_local_shortcut()

