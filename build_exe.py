import os
import sys
import subprocess
import shutil

def build_windows_exe():
    print("==================================================")
    print("  🚀 Building NPro Downloader Standalone Windows .EXE")
    print("==================================================")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(base_dir, "ui")
    icon_file = os.path.join(base_dir, "icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=NPro-Downloader",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--icon={icon_file}",
        f"--add-data={ui_dir};ui",
        "--collect-all=webview",
        "--collect-all=fastapi",
        "--collect-all=uvicorn",
        "--collect-all=websockets",
        "--collect-all=starlette",
        "--hidden-import=aiofiles",
        "--hidden-import=yt_dlp",
        "--hidden-import=requests",
        "--hidden-import=aiohttp",
        "main.py"
    ]

    print("Running PyInstaller...")
    res = subprocess.run(cmd, cwd=base_dir)

    if res.returncode == 0:
        dist_dir = os.path.join(base_dir, "dist", "NPro-Downloader")
        dist_ui = os.path.join(dist_dir, "ui")
        if os.path.exists(ui_dir):
            shutil.copytree(ui_dir, dist_ui, dirs_exist_ok=True)
            print("Copied UI bundle into dist folder.")

        dist_bin = os.path.join(dist_dir, "bin")
        local_bin = os.path.join(base_dir, "bin")
        if os.path.exists(local_bin):
            shutil.copytree(local_bin, dist_bin, dirs_exist_ok=True)
            print("Copied FFmpeg bin bundle into dist folder.")

        dist_exe = os.path.join(dist_dir, "NPro-Downloader.exe")
        print("\n🎉 SUCCESS! EXE created successfully at:")
        print(dist_exe)
        return True
    else:
        print("\n❌ Build failed. Please check logs.")
        return False

if __name__ == "__main__":
    build_windows_exe()
