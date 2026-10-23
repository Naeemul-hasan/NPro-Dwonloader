import os
import sys
import time
import socket
import threading
import subprocess
import urllib.request
import webbrowser
import uvicorn

# Prevent NoneType stdout/stderr crashes in windowed mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from server.api import app

def find_available_port(start_port: int = 58250) -> int:
    """Finds an unused network port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def start_api_server(host: str, port: int):
    """Runs uvicorn in a background thread."""
    config = uvicorn.Config(app=app, host=host, port=port, log_level="error", access_log=False)
    server = uvicorn.Server(config)
    server.run()

def wait_for_server(url: str, timeout: float = 12.0) -> bool:
    """Waits until the local API server responds with HTTP 200."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{url}/api/settings", timeout=0.6) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def open_native_edge_app(url: str):
    """Fallback: Opens clean frameless app window using Windows Edge App Mode."""
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        "msedge"
    ]
    for p in edge_paths:
        try:
            subprocess.Popen([p, f"--app={url}", "--new-window"])
            return True
        except Exception:
            continue
    webbrowser.open(url)
    return False

def main():
    host = "127.0.0.1"
    port = find_available_port()
    url = f"http://{host}:{port}"

    # Launch background Uvicorn server thread
    server_thread = threading.Thread(target=start_api_server, args=(host, port), daemon=True)
    server_thread.start()

    # Wait until server is completely initialized & responsive
    server_ready = wait_for_server(url)
    if not server_ready:
        time.sleep(1.0)

    # If --web argument is passed
    if "--web" in sys.argv or "--browser" in sys.argv:
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

    # Attempt Primary GUI: PyWebView EdgeChromium
    gui_started = False
    try:
        import webview
        icon_path = os.path.join(current_dir, "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = None

        window = webview.create_window(
            title="NPro Downloader — 2026 Turbo Download Manager",
            url=url,
            width=1280,
            height=820,
            min_size=(800, 600),
            background_color='#080a12',
            text_select=False
        )
        gui_started = True
        webview.start(gui='edgechromium', debug=False, icon=icon_path)
    except Exception:
        gui_started = False

    # Secondary GUI Fallback: Edge App Mode (Frameless Native Window)
    if not gui_started:
        open_native_edge_app(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    main()
