import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Theme colors (matching AetherLink cyberpunk red/dark theme)
COLOR_BG_DARK = "#090f1d"
COLOR_PANEL = "#0f172a"
COLOR_NEON_RED = "#ef4444"
COLOR_TEXT_PRIMARY = "#f8fafc"
COLOR_TEXT_MUTED = "#64748b"

TRANSLATIONS = {
    "en": {
        "title": "AetherLink Setup Wizard",
        "welcome_title": "Welcome to AetherLink Installation",
        "welcome_desc": "This wizard will guide you through installing AetherLink local secure messenger on your computer.\n\nAetherLink connects classmates and devices on Wi-Fi with zero internet dependency, hosting a local shared file vault, live clipboard sync, offline voice messages, and P2P connection bridges.",
        "license_title": "License Agreement",
        "license_desc": "Please read the following license agreement carefully. You must accept the terms before continuing.",
        "license_accept": "I accept the agreement",
        "folder_title": "Select Destination Folder",
        "folder_desc": "Where should AetherLink be installed?",
        "space_warning": "Warning: Low disk space on drive C. Installing on drive D is recommended.",
        "components_title": "Select Components to Install",
        "components_desc": "Check the components you wish to install:",
        "comp_hub": "AetherLink Desktop Hub (Server & Controller)",
        "comp_client": "AetherLink Desktop Client (Messenger WebView)",
        "comp_mobile": "AetherLink Mobile Client (Android APK)",
        "ready_title": "Ready to Install",
        "ready_desc": "Setup is now ready to begin installing AetherLink on your computer.",
        "ready_summary": "Destination Location:\n  {folder}\n\nSelected Components:\n{components}",
        "installing_title": "Installing AetherLink...",
        "installing_desc": "Please wait while Setup copies files and registers shortcuts...",
        "finish_title": "Completing the AetherLink Setup",
        "finish_desc": "Setup has successfully installed AetherLink on your computer.\n\nClick Finish to exit Setup.",
        "finish_launch": "Launch AetherLink Desktop Hub",
        "finish_shortcut": "Create Desktop Shortcut icons",
        "btn_next": "Next >",
        "btn_back": "< Back",
        "btn_cancel": "Cancel",
        "btn_finish": "Finish",
        "btn_browse": "Browse..."
    },
    "es": {
        "title": "Asistente de Instalación de AetherLink",
        "welcome_title": "Bienvenido a la instalación de AetherLink",
        "welcome_desc": "Este asistente lo guiará a través de la instalación del mensajero local seguro AetherLink en su computadora.\n\nAetherLink conecta dispositivos de compañeros de clase en Wi-Fi con cero dependencia de Internet, alojando un baúl de archivos local compartido, sincronización de portapapeles y notas de voz fuera de línea.",
        "license_title": "Acuerdo de Licencia",
        "license_desc": "Por favor lea el siguiente acuerdo de licencia cuidadosamente. Debe aceptar los términos antes de continuar.",
        "license_accept": "Acepto el acuerdo de licencia",
        "folder_title": "Seleccionar Carpeta de Destino",
        "folder_desc": "¿Dónde debería instalarse AetherLink?",
        "space_warning": "Advertencia: Poco espacio en disco en la unidad C. Se recomienda instalar en la unidad D.",
        "components_title": "Seleccionar Componentes",
        "components_desc": "Marque los componentes que desea instalar:",
        "comp_hub": "Servidor Hub de AetherLink (Servidor y Controlador)",
        "comp_client": "Cliente de Escritorio AetherLink (Mensajero WebView)",
        "comp_mobile": "Cliente Móvil AetherLink (APK de Android)",
        "ready_title": "Listo para Instalar",
        "ready_desc": "El asistente está listo para comenzar la instalación en su computadora.",
        "ready_summary": "Ubicación de Destino:\n  {folder}\n\nComponentes Seleccionados:\n{components}",
        "installing_title": "Instalando AetherLink...",
        "installing_desc": "Por favor espere mientras copiamos archivos y registramos accesos directos...",
        "finish_title": "Instalación Completada",
        "finish_desc": "Se ha instalado AetherLink correctamente en su computadora.\n\nHaga clic en Finalizar para salir.",
        "finish_launch": "Iniciar AetherLink Desktop Hub",
        "finish_shortcut": "Crear accesos directos en el escritorio",
        "btn_next": "Siguiente >",
        "btn_back": "< Atrás",
        "btn_cancel": "Cancelar",
        "btn_finish": "Finalizar",
        "btn_browse": "Examinar..."
    },
    "fr": {
        "title": "Assistant d'installation d'AetherLink",
        "welcome_title": "Bienvenue dans l'installation d'AetherLink",
        "welcome_desc": "Cet assistant vous guidera dans l'installation d'AetherLink sur votre ordinateur.\n\nAetherLink connecte les appareils sur le Wi-Fi local sans dépendance à Internet, avec coffre-fort partagé, synchronisation du presse-papiers et messages vocaux hors ligne.",
        "license_title": "Accord de Licence",
        "license_desc": "Veuillez lire attentivement l'accord de licence. Vous devez accepter les termes avant de continuer.",
        "license_accept": "J'accepte les termes de l'accord",
        "folder_title": "Dossier de Destination",
        "folder_desc": "Où installer AetherLink?",
        "space_warning": "Attention: Espace disque faible sur C:. L'installation sur D: est recommandée.",
        "components_title": "Sélectionner les Composants",
        "components_desc": "Cochez les composants à installer:",
        "comp_hub": "Serveur Hub AetherLink (Serveur et Contrôleur)",
        "comp_client": "Client de Bureau AetherLink (Messagerie WebView)",
        "comp_mobile": "Client Mobile AetherLink (APK Android)",
        "ready_title": "Prêt à Installer",
        "ready_desc": "L'assistant est prêt à commencer l'installation sur votre ordinateur.",
        "ready_summary": "Dossier de Destination:\n  {folder}\n\nComposants Sélectionnés:\n{components}",
        "installing_title": "Installation de AetherLink...",
        "installing_desc": "Veuillez patienter pendant la copie des fichiers et l'enregistrement...",
        "finish_title": "Fin de l'installation d'AetherLink",
        "finish_desc": "AetherLink a été installé avec succès sur votre ordinateur.\n\nCliquez sur Terminer pour quitter.",
        "finish_launch": "Démarrer AetherLink Desktop Hub",
        "finish_shortcut": "Créer les raccourcis sur le bureau",
        "btn_next": "Suivant >",
        "btn_back": "< Retour",
        "btn_cancel": "Annuler",
        "btn_finish": "Terminer",
        "btn_browse": "Parcourir..."
    }
}

class LanguagePrompt(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Select Setup Language")
        self.geometry("320x220")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)
        self.transient(parent)
        self.grab_set()
        
        # Center prompt
        self.update_idletasks()
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (320 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (220 // 2)
        self.geometry(f"+{x}+{y}")
        
        # Label
        lbl = ctk.CTkLabel(
            self, 
            text="Select installation language:", 
            font=("Space Grotesk", 13, "bold"),
            text_color=COLOR_NEON_RED
        )
        lbl.pack(pady=(25, 15))
        
        # Selected language
        self.selected_lang = "en"
        
        self.combo = ctk.CTkComboBox(
            self, 
            values=["English", "Español", "Français"],
            width=200,
            font=("Space Grotesk", 11),
            dropdown_font=("Space Grotesk", 11)
        )
        self.combo.pack(pady=10)
        self.combo.set("English")
        
        btn = ctk.CTkButton(
            self, 
            text="OK",
            width=120,
            height=32,
            font=("Space Grotesk", 11, "bold"),
            fg_color="#0f172a",
            border_color=COLOR_NEON_RED,
            border_width=1,
            text_color="#f8fafc",
            hover_color=COLOR_NEON_RED,
            command=self.confirm
        )
        btn.pack(pady=20)
        
    def confirm(self):
        val = self.combo.get()
        if val == "Español":
            self.selected_lang = "es"
        elif val == "Français":
            self.selected_lang = "fr"
        else:
            self.selected_lang = "en"
        self.destroy()

class SetupWizard(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AetherLink Installer")
        self.geometry("620x450")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)
        
        # Bind icon
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "desktop", "icon.ico"))
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass
                
        # Windows grouping
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("lnbti.aethersync.installer.1.0")
        except Exception:
            pass

        self.lang = "en"
        self.current_page = 0
        
        # Installation Variables
        default_dir = r"D:\AetherLink"
        # Fallback to C if D doesn't exist
        if not os.path.exists("D:\\"):
            default_dir = os.path.join(os.environ.get("USERPROFILE", "C:\\"), "AetherLink")
            
        self.install_dir = tk.StringVar(value=default_dir)
        self.install_hub = tk.BooleanVar(value=True)
        self.install_client = tk.BooleanVar(value=True)
        self.install_mobile = tk.BooleanVar(value=True)
        
        self.license_accepted = tk.BooleanVar(value=False)
        self.create_shortcuts = tk.BooleanVar(value=True)
        self.run_after_install = tk.BooleanVar(value=True)
        
        # Hide window and show language prompt
        self.withdraw()
        prompt = LanguagePrompt(self)
        self.wait_window(prompt)
        self.lang = prompt.selected_lang
        self.deiconify()
        
        self.title(TRANSLATIONS[self.lang]["title"])
        self.build_ui()
        self.show_page(0)
        
    def build_ui(self):
        # 1. Left banner frame
        self.banner_frame = ctk.CTkFrame(self, width=160, fg_color=COLOR_PANEL, corner_radius=0)
        self.banner_frame.pack(side="left", fill="y")
        
        self.logo_lbl = ctk.CTkLabel(
            self.banner_frame,
            text="⚡",
            font=("Space Grotesk", 64),
            text_color=COLOR_NEON_RED
        )
        self.logo_lbl.place(relx=0.5, rely=0.4, anchor="center")
        
        self.logo_text = ctk.CTkLabel(
            self.banner_frame,
            text="AETHERLINK\nINSTALLER",
            font=("Space Grotesk", 12, "bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.logo_text.place(relx=0.5, rely=0.6, anchor="center")
        
        # 2. Main content frame
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(side="top", fill="both", expand=True, padx=20, pady=20)
        
        # 3. Bottom controls frame
        self.controls_frame = ctk.CTkFrame(self, height=60, fg_color="transparent")
        self.controls_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 15))
        
        self.btn_cancel = ctk.CTkButton(
            self.controls_frame, 
            text=TRANSLATIONS[self.lang]["btn_cancel"],
            width=90,
            fg_color="#1e293b",
            hover_color=COLOR_NEON_RED,
            command=self.quit_setup
        )
        self.btn_cancel.pack(side="right", padx=5)
        
        self.btn_next = ctk.CTkButton(
            self.controls_frame, 
            text=TRANSLATIONS[self.lang]["btn_next"],
            width=90,
            fg_color=COLOR_NEON_RED,
            hover_color="#dc2626",
            command=self.next_page
        )
        self.btn_next.pack(side="right", padx=5)
        
        self.btn_back = ctk.CTkButton(
            self.controls_frame, 
            text=TRANSLATIONS[self.lang]["btn_back"],
            width=90,
            fg_color="#1e293b",
            hover_color="#334155",
            command=self.back_page
        )
        self.btn_back.pack(side="right", padx=5)

    def show_page(self, page_index):
        self.current_page = page_index
        
        # Clear main content
        for child in self.content_frame.winfo_children():
            child.destroy()
            
        # Update button states
        self.btn_back.configure(state="normal" if page_index > 0 and page_index < 5 else "disabled")
        self.btn_next.configure(text=TRANSLATIONS[self.lang]["btn_finish"] if page_index == 6 else TRANSLATIONS[self.lang]["btn_next"])
        self.btn_next.configure(state="normal")
        self.btn_cancel.configure(state="normal" if page_index < 5 else "disabled")
        
        t = TRANSLATIONS[self.lang]
        
        if page_index == 0:
            # Welcome page
            title = ctk.CTkLabel(self.content_frame, text=t["welcome_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 15))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["welcome_desc"], font=("Space Grotesk", 12), justify="left", wraplength=400, text_color=COLOR_TEXT_PRIMARY)
            desc.pack(anchor="w", pady=10)
            
        elif page_index == 1:
            # License Agreement page
            title = ctk.CTkLabel(self.content_frame, text=t["license_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 10))
            
            lbl_desc = ctk.CTkLabel(self.content_frame, text=t["license_desc"], font=("Space Grotesk", 11), text_color=COLOR_TEXT_MUTED)
            lbl_desc.pack(anchor="w", pady=(0, 8))
            
            license_text = "AetherLink Local Secure Hub License Agreement\n\n1. Distribution: This software is designed for private local network (LAN) sharing and offline campus classroom usage. You may share compiled binaries freely within your LAN.\n\n2. Privacy: All communications, audio notes, and files are stored strictly locally on the host machine database. No data is transmitted to external servers.\n\n3. Warranty: Provided as-is. The developer is not liable for data loss or connection drops during local network failure."
            
            text_box = ctk.CTkTextbox(self.content_frame, height=180, width=400, font=("Space Grotesk", 10))
            text_box.pack(anchor="w", pady=10)
            text_box.insert("1.0", license_text)
            text_box.configure(state="disabled")
            
            chk = ctk.CTkCheckBox(
                self.content_frame, 
                text=t["license_accept"],
                variable=self.license_accepted,
                font=("Space Grotesk", 11),
                command=self.update_license_state
            )
            chk.pack(anchor="w", pady=5)
            self.update_license_state()
            
        elif page_index == 2:
            # Directory selection page
            title = ctk.CTkLabel(self.content_frame, text=t["folder_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 15))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["folder_desc"], font=("Space Grotesk", 12), text_color=COLOR_TEXT_PRIMARY)
            desc.pack(anchor="w", pady=10)
            
            row = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            row.pack(fill="x", pady=10)
            
            entry = ctk.CTkEntry(row, textvariable=self.install_dir, font=("Space Grotesk", 11), width=280)
            entry.pack(side="left", padx=(0, 10))
            
            btn_browse = ctk.CTkButton(row, text=t["btn_browse"], width=80, fg_color="#1e293b", hover_color="#334155", command=self.browse_folder)
            btn_browse.pack(side="left")
            
        elif page_index == 3:
            # Component Selection page
            title = ctk.CTkLabel(self.content_frame, text=t["components_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 10))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["components_desc"], font=("Space Grotesk", 11), text_color=COLOR_TEXT_MUTED)
            desc.pack(anchor="w", pady=(0, 10))
            
            c1 = ctk.CTkCheckBox(self.content_frame, text=t["comp_hub"], variable=self.install_hub, font=("Space Grotesk", 11))
            c1.pack(anchor="w", pady=6)
            
            c2 = ctk.CTkCheckBox(self.content_frame, text=t["comp_client"], variable=self.install_client, font=("Space Grotesk", 11))
            c2.pack(anchor="w", pady=6)
            
            c3 = ctk.CTkCheckBox(self.content_frame, text=t["comp_mobile"], variable=self.install_mobile, font=("Space Grotesk", 11))
            c3.pack(anchor="w", pady=6)
            
        elif page_index == 4:
            # Ready page
            title = ctk.CTkLabel(self.content_frame, text=t["ready_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 10))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["ready_desc"], font=("Space Grotesk", 12), text_color=COLOR_TEXT_PRIMARY)
            desc.pack(anchor="w", pady=(0, 15))
            
            # Summary details
            comp_list = []
            if self.install_hub.get(): comp_list.append(" - Desktop Hub (FastAPI Server)")
            if self.install_client.get(): comp_list.append(" - Desktop Client (WebView Window)")
            if self.install_mobile.get(): comp_list.append(" - Mobile Client (Android APK)")
            
            summary_txt = t["ready_summary"].format(
                folder=self.install_dir.get(),
                components="\n".join(comp_list)
            )
            
            box = ctk.CTkTextbox(self.content_frame, height=180, width=400, font=("Space Grotesk", 11))
            box.pack(anchor="w", pady=5)
            box.insert("1.0", summary_txt)
            box.configure(state="disabled")
            
        elif page_index == 5:
            # Installing page
            self.btn_next.configure(state="disabled")
            self.btn_back.configure(state="disabled")
            
            title = ctk.CTkLabel(self.content_frame, text=t["installing_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 15))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["installing_desc"], font=("Space Grotesk", 12), text_color=COLOR_TEXT_PRIMARY)
            desc.pack(anchor="w", pady=10)
            
            self.progress = ctk.CTkProgressBar(self.content_frame, width=380, progress_color=COLOR_NEON_RED)
            self.progress.pack(anchor="w", pady=20)
            self.progress.set(0)
            
            # Start copying process asynchronously
            self.after(500, self.perform_installation)
            
        elif page_index == 6:
            # Finished page
            title = ctk.CTkLabel(self.content_frame, text=t["finish_title"], font=("Space Grotesk", 18, "bold"), text_color=COLOR_NEON_RED)
            title.pack(anchor="w", pady=(10, 15))
            
            desc = ctk.CTkLabel(self.content_frame, text=t["finish_desc"], font=("Space Grotesk", 12), justify="left", text_color=COLOR_TEXT_PRIMARY)
            desc.pack(anchor="w", pady=10)
            
            c1 = ctk.CTkCheckBox(self.content_frame, text=t["finish_shortcut"], variable=self.create_shortcuts, font=("Space Grotesk", 11))
            c1.pack(anchor="w", pady=8)
            
            c2 = ctk.CTkCheckBox(self.content_frame, text=t["finish_launch"], variable=self.run_after_install, font=("Space Grotesk", 11))
            c2.pack(anchor="w", pady=8)

    def update_license_state(self):
        if self.license_accepted.get():
            self.btn_next.configure(state="normal")
        else:
            self.btn_next.configure(state="disabled")

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.install_dir.get())
        if folder:
            self.install_dir.set(os.path.abspath(folder))

    def next_page(self):
        if self.current_page == 2:
            # Check C: space limits
            folder = self.install_dir.get()
            if folder.upper().startswith("C:"):
                # Check free space
                free_bytes = shutil.disk_usage("C:").free
                free_mb = free_bytes / (1024 * 1024)
                if free_mb < 500: # Less than 500MB free
                    messagebox.showwarning("Low Disk Space", TRANSLATIONS[self.lang]["space_warning"])
            
        if self.current_page < 6:
            self.show_page(self.current_page + 1)
        else:
            # Finishing
            self.complete_installation()

    def back_page(self):
        if self.current_page > 0:
            self.show_page(self.current_page - 1)

    def quit_setup(self):
        if messagebox.askyesno("Exit Setup", "Are you sure you want to cancel the installation?"):
            self.destroy()

    def perform_installation(self):
        source_dir = os.path.dirname(os.path.abspath(__file__))
        dest_dir = self.install_dir.get()
        
        try:
            # Update progress 10%
            self.progress.set(0.1)
            self.update_idletasks()
            
            # 1. Create target folder structure
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                
            self.progress.set(0.25)
            self.update_idletasks()
            
            # 2. Copy components
            ignore_patterns = shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".git", ".gemini", ".system_generated", 
                "Verify_indexes.py", "*.zip", "download_jdk.ps1"
            )
            
            # Copy all files
            for item in os.listdir(source_dir):
                s = os.path.join(source_dir, item)
                d = os.path.join(dest_dir, item)
                
                # Check component selections
                if item == "android" and not self.install_mobile.get():
                    continue
                if item == "desktop" and not self.install_hub.get() and not self.install_client.get():
                    continue
                    
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d, ignore=ignore_patterns)
                else:
                    shutil.copy2(s, d)
                    
            self.progress.set(0.65)
            self.update_idletasks()
            
            # 3. Handle specific components setup
            if self.install_mobile.get():
                # Copy the compiled APK to the root of the install directory as well
                apk_src = os.path.join(source_dir, "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
                if os.path.exists(apk_src):
                    shutil.copy2(apk_src, os.path.join(dest_dir, "AetherLink_Mobile_Client.apk"))
            
            self.progress.set(0.85)
            self.update_idletasks()
            
            # Finalize progress 100%
            self.progress.set(1.0)
            self.update_idletasks()
            self.after(500, lambda: self.show_page(6))
            
        except Exception as e:
            messagebox.showerror("Installation Error", f"An error occurred during copying files:\n{str(e)}")
            self.show_page(2)

    def complete_installation(self):
        dest_dir = self.install_dir.get()
        
        # Locate absolute path to pythonw.exe
        python_dir = os.path.dirname(sys.executable)
        pythonw_path = os.path.join(python_dir, "pythonw.exe")
        if not os.path.exists(pythonw_path):
            pythonw_path = "pythonw.exe"
            
        # 1. Create shortcuts if checkbox checked
        if self.create_shortcuts.get():
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
                    
            ico_path = os.path.join(dest_dir, "desktop", "icon.ico")
            
            ps_cmd = ""
            if self.install_hub.get():
                shortcut_hub = os.path.join(desktop_dir, "AetherLink Hub.lnk")
                launcher_path = os.path.join(dest_dir, "desktop", "launcher.py")
                ps_cmd += f"""
                $ShortcutHub = $WshShell.CreateShortcut("{shortcut_hub}")
                $ShortcutHub.TargetPath = "{pythonw_path}"
                $ShortcutHub.Arguments = '"{launcher_path}"'
                $ShortcutHub.WorkingDirectory = "{os.path.join(dest_dir, 'desktop')}"
                if (Test-Path "{ico_path}") {{ $ShortcutHub.IconLocation = "{ico_path},0" }}
                $ShortcutHub.Save()
                """
                
            if self.install_client.get():
                shortcut_client = os.path.join(desktop_dir, "AetherLink Messenger.lnk")
                messenger_path = os.path.join(dest_dir, "desktop", "messenger.py")
                ps_cmd += f"""
                $ShortcutClient = $WshShell.CreateShortcut("{shortcut_client}")
                $ShortcutClient.TargetPath = "{pythonw_path}"
                $ShortcutClient.Arguments = '"{messenger_path}"'
                $ShortcutClient.WorkingDirectory = "{os.path.join(dest_dir, 'desktop')}"
                if (Test-Path "{ico_path}") {{ $ShortcutClient.IconLocation = "{ico_path},0" }}
                $ShortcutClient.Save()
                """
                
            if ps_cmd:
                full_ps = f"$WshShell = New-Object -ComObject WScript.Shell\n{ps_cmd}"
                try:
                    subprocess.run(["powershell", "-Command", full_ps], check=True, capture_output=True)
                except Exception as e:
                    print(f"Failed to create shortcuts: {e}")
                    
        # 2. Launch application if checkbox checked
        if self.run_after_install.get() and self.install_hub.get():
            launcher_path = os.path.join(dest_dir, "desktop", "launcher.py")
            try:
                subprocess.Popen([pythonw_path, launcher_path], cwd=os.path.join(dest_dir, "desktop"))
            except Exception as e:
                print(f"Failed to start launcher: {e}")
                
        self.destroy()

if __name__ == "__main__":
    app = SetupWizard()
    app.mainloop()
