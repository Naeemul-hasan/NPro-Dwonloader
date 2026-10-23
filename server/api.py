import os
import sys
import time
import json
import asyncio
import subprocess
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.downloader import TurboEngine, DownloadTask, format_bytes, detect_category, get_default_download_dir
from core.media_extractor import MediaExtractor, is_social_or_media_url
from core.storage import StorageManager

app = FastAPI(title="PulseGet Pro API", version="2026.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Storage & Engines
storage = StorageManager()
media_extractor = MediaExtractor()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

ws_manager = ConnectionManager()

# Background broadcast queue
async def on_engine_update(task_dict: dict):
    # Calculate global bandwidth
    total_speed = 0.0
    active_count = 0
    for t in engine.tasks.values():
        if t.status in ("downloading", "merging"):
            total_speed += t.speed_bps
            active_count += 1
            
    await ws_manager.broadcast({
        "type": "task_update",
        "task": task_dict,
        "global_speed_bps": total_speed,
        "global_speed_formatted": f"{format_bytes(int(total_speed))}/s",
        "active_downloads": active_count
    })

engine = TurboEngine(on_update_callback=on_engine_update)

# Models
class AnalyzeRequest(BaseModel):
    url: str

class StartDownloadRequest(BaseModel):
    url: str
    filename: Optional[str] = None
    save_path: Optional[str] = None
    threads: int = 16
    format_id: Optional[str] = None
    is_media: bool = False
    category: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    save_directory: Optional[str] = None
    default_threads: Optional[int] = None
    max_active_downloads: Optional[int] = None
    speed_limit_kbps: Optional[int] = None
    theme: Optional[str] = None
    sound_effects: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    clipboard_watch: Optional[bool] = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state snapshot
        tasks_data = [t.to_dict() for t in engine.tasks.values()]
        await websocket.send_text(json.dumps({
            "type": "init_state",
            "tasks": tasks_data,
            "settings": storage.settings
        }))
        while True:
            # Keep socket alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

@app.post("/api/analyze")
async def analyze_url(req: AnalyzeRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    # If it's a known social/video streaming platform, inspect with yt-dlp
    if is_social_or_media_url(url):
        media_info = await media_extractor.get_media_info(url)
        if media_info.get("success"):
            return {
                "success": True,
                "is_media": True,
                "data": media_info
            }

    # Otherwise inspect direct HTTP file with range probe
    probe = await engine.probe_url(url)
    return {
        "success": probe.get("success", True),
        "is_media": False,
        "data": probe
    }

@app.post("/api/download/start")
async def start_download(req: StartDownloadRequest):
    save_dir = req.save_path or storage.settings.get("save_directory") or get_default_download_dir()
    threads = req.threads or storage.settings.get("default_threads", 16)

    # Handle Media/Social Streaming Downloads
    if req.is_media and req.format_id:
        task = engine.create_task(
            url=req.url,
            filename=req.filename or "media_file",
            save_path=save_dir,
            threads=threads,
            category=req.category or "video"
        )
        task.status = "downloading"
        await engine.emit_update(task)

        loop = asyncio.get_running_loop()

        # Run yt-dlp in threadpool safely
        def run_media():
            last_emit = [0.0]

            def cb(progress_data):
                task.status = progress_data.get("status", "downloading")
                task.downloaded_bytes = progress_data.get("downloaded_bytes", 0)
                task.total_bytes = progress_data.get("total_bytes", 0)
                task.speed_bps = progress_data.get("speed_bps", 0)
                task.speed_formatted = f"{format_bytes(int(task.speed_bps))}/s"
                task.progress = progress_data.get("progress", 0.0)

                # Throttle updates to ~4 times per second to prevent event loop flooding
                now = time.time()
                if now - last_emit[0] >= 0.25 or task.progress >= 99.0:
                    last_emit[0] = now
                    try:
                        asyncio.run_coroutine_threadsafe(engine.emit_update(task), loop)
                    except Exception:
                        pass

            clean_name = req.filename or f"video_{task.id[:6]}"
            res = media_extractor.download_media_sync(
                url=req.url,
                format_id=req.format_id,
                output_dir=save_dir,
                filename_template=clean_name,
                progress_callback=cb
            )
            if res.get("success"):
                task.status = "completed"
                task.progress = 100.0
                task.filename = os.path.basename(res["file_path"])
                task.speed_formatted = "Done"
            else:
                task.status = "error"
                task.error_message = res.get("error", "Extraction failed")
            try:
                asyncio.run_coroutine_threadsafe(engine.emit_update(task), loop)
            except Exception:
                pass

        loop.run_in_executor(None, run_media)
        return {"success": True, "task_id": task.id, "message": "Media download started"}

    # Handle Standard Direct Multi-Chunk Download
    task = engine.create_task(
        url=req.url,
        filename=req.filename,
        save_path=save_dir,
        threads=threads,
        category=req.category or "other"
    )
    await engine.start_download(task.id)
    return {"success": True, "task_id": task.id, "message": "Turbo download started"}

@app.post("/api/download/pause/{task_id}")
async def pause_task(task_id: str):
    await engine.pause_download(task_id)
    return {"success": True}

@app.post("/api/download/resume/{task_id}")
async def resume_task(task_id: str):
    await engine.resume_download(task_id)
    return {"success": True}

@app.post("/api/download/cancel/{task_id}")
async def cancel_task(task_id: str):
    await engine.cancel_download(task_id, delete_files=True)
    await ws_manager.broadcast({"type": "task_removed", "task_id": task_id})
    return {"success": True}

@app.post("/api/download/clear-completed")
async def clear_completed():
    to_delete = [tid for tid, t in engine.tasks.items() if t.status in ("completed", "error", "cancelled")]
    for tid in to_delete:
        del engine.tasks[tid]
    await ws_manager.broadcast({"type": "tasks_cleared", "task_ids": to_delete})
    return {"success": True, "count": len(to_delete)}

@app.get("/api/downloads")
async def get_downloads():
    return [t.to_dict() for t in engine.tasks.values()]

@app.post("/api/download/open-file/{task_id}")
async def open_file(task_id: str):
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    full_path = os.path.join(task.save_path, task.filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File does not exist on disk")

    try:
        if sys.platform == "win32":
            os.startfile(full_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", full_path])
        else:
            subprocess.run(["xdg-open", full_path])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/open-folder/{task_id}")
async def open_folder(task_id: str):
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    full_path = os.path.join(task.save_path, task.filename)

    try:
        if sys.platform == "win32":
            subprocess.run(f'explorer /select,"{os.path.normpath(full_path)}"')
        else:
            folder = task.save_path
            subprocess.run(["xdg-open", folder])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview/{task_id}")
async def preview_media(task_id: str):
    task = engine.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    full_path = os.path.join(task.save_path, task.filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not ready or missing")
    return FileResponse(full_path)

@app.get("/api/settings")
async def get_settings():
    return storage.settings

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    updates = req.model_dump(exclude_unset=True)
    storage.save_settings(updates)
    await ws_manager.broadcast({"type": "settings_updated", "settings": storage.settings})
    return {"success": True, "settings": storage.settings}

def resolve_ui_dir() -> str:
    # 1. PyInstaller bundled temp directory
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, 'ui')
        if os.path.exists(p):
            return p
    # 2. Next to executable
    exe_dir = os.path.dirname(sys.executable)
    p_exe = os.path.join(exe_dir, 'ui')
    if os.path.exists(p_exe):
        return p_exe
    p_internal = os.path.join(exe_dir, '_internal', 'ui')
    if os.path.exists(p_internal):
        return p_internal
    # 3. Source directory
    dev_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
    return dev_dir

ui_dir = resolve_ui_dir()
if os.path.exists(ui_dir):
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
