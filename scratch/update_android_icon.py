import os
import shutil
from PIL import Image

src_png = r"C:\Users\Elite computers\.gemini\antigravity\brain\126f3357-624d-4a32-b92b-13779c7db187\aethersync_app_icon_1782630079830.png"
res_dir = r"c:\Users\Elite computers\OneDrive\Documents\LNBTI\AntiGravity\aethersync\android\app\src\main\res"

sizes = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192
}

if not os.path.exists(src_png):
    print(f"Error: Source PNG does not exist at {src_png}")
    exit(1)

# Open source image
img = Image.open(src_png)

# 1. Clean up adaptive icon XMLs to force fallback to legacy raster icons
anydpi_dir = os.path.join(res_dir, "mipmap-anydpi-v26")
if os.path.exists(anydpi_dir):
    for f in ["ic_launcher.xml", "ic_launcher_round.xml"]:
        fp = os.path.join(anydpi_dir, f)
        if os.path.exists(fp):
            os.remove(fp)
            print(f"Removed adaptive XML: {fp}")

# 2. Resize and save raster PNGs
for folder, size in sizes.items():
    target_folder = os.path.join(res_dir, folder)
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        
    # Delete conflicting webp/png files if they exist
    for ext in [".webp", ".png"]:
        for name in ["ic_launcher", "ic_launcher_round"]:
            fp = os.path.join(target_folder, name + ext)
            if os.path.exists(fp):
                os.remove(fp)
                
    # Resize image
    resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # Save standard icon
    resized_img.save(os.path.join(target_folder, "ic_launcher.png"), "PNG")
    # Save round icon
    resized_img.save(os.path.join(target_folder, "ic_launcher_round.png"), "PNG")
    print(f"Generated icons in {folder} ({size}x{size})")

print("App icon update completed successfully!")
