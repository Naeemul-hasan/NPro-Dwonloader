import os
import sys
import time
import uuid
import asyncio
import aiohttp
import aiofiles
import mimetypes
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Callable
from urllib.parse import urlparse, unquote

def get_default_download_dir() -> str:
    """Returns the user's default Downloads folder."""
    home = Path.home()
    dl_dir = home / "Downloads"
    if not dl_dir.exists():
        dl_dir.mkdir(parents=True, exist_ok=True)
    return str(dl_dir)

def format_bytes(bytes_count: int) -> str:
    """Converts bytes to human-readable string (KB, MB, GB)."""
    if bytes_count <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(bytes_count)
    while size >= 1024.0 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.2f} {units[i]}"

def detect_category(filename: str, content_type: str = "") -> str:
    """Detects file category based on filename extension or mime type."""
    ext = os.path.splitext(filename)[1].lower()
    
    video_exts = {'.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.m4v', '.ts'}
    audio_exts = {'.mp3', '.m4a', '.wav', '.flac', '.aac', '.ogg', '.opus', '.wma'}
    doc_exts = {'.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx', '.epub'}
    archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'}
    exe_exts = {'.exe', '.msi', '.apk', '.bat', '.sh', '.dmg', '.deb'}

    if ext in video_exts or 'video' in content_type:
        return 'video'
    if ext in audio_exts or 'audio' in content_type:
        return 'audio'
    if ext in doc_exts or 'document' in content_type or 'text' in content_type:
        return 'document'
    if ext in archive_exts or 'zip' in content_type or 'tar' in content_type:
        return 'archive'
    if ext in exe_exts:
        return 'executable'
    return 'other'

class DownloadTask:
    def __init__(
        self,
        task_id: str,
        url: str,
        filename: str,
        save_path: str,
        threads: int = 16,
        category: str = "other",
        total_bytes: int = 0,
        supports_ranges: bool = True
    ):
        self.id = task_id
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.temp_dir = os.path.join(save_path, f".pulse_{task_id}")
        self.threads = max(1, min(32, threads))
        self.category = category
        self.total_bytes = total_bytes
        self.downloaded_bytes = 0
        self.status = "queued" # queued, downloading, paused, merging, completed, error
        self.supports_ranges = supports_ranges
        self.chunks = []
        self.speed_bps = 0.0
        self.speed_formatted = "0 KB/s"
        self.eta_seconds = 0
        self.eta_formatted = "--:--"
        self.progress = 0.0
        self.error_message = ""
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.is_cancelled = False
        self.is_paused = False
        
        # Speed measurement window
        self._last_time = time.time()
        self._last_bytes = 0
        self._speed_samples = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.filename,
            "save_path": self.save_path,
            "full_path": os.path.join(self.save_path, self.filename),
            "threads": self.threads,
            "category": self.category,
            "total_bytes": self.total_bytes,
            "total_formatted": format_bytes(self.total_bytes),
            "downloaded_bytes": self.downloaded_bytes,
            "downloaded_formatted": format_bytes(self.downloaded_bytes),
            "status": self.status,
            "supports_ranges": self.supports_ranges,
            "speed_bps": self.speed_bps,
            "speed": self.speed_formatted,
            "eta": self.eta_formatted,
            "progress": round(self.progress, 2),
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "chunks": self.chunks
        }

    def update_speed(self):
        now = time.time()
        dt = now - self._last_time
        if dt >= 0.4:
            current_bytes = self.downloaded_bytes
            delta = current_bytes - self._last_bytes
            speed = max(0.0, delta / dt)
            
            self._speed_samples.append(speed)
            if len(self._speed_samples) > 5:
                self._speed_samples.pop(0)
            
            avg_speed = sum(self._speed_samples) / len(self._speed_samples)
            self.speed_bps = avg_speed
            self.speed_formatted = f"{format_bytes(int(avg_speed))}/s"
            
            if self.total_bytes > 0 and self.total_bytes > current_bytes and avg_speed > 100:
                remaining = self.total_bytes - current_bytes
                eta = int(remaining / avg_speed)
                self.eta_seconds = eta
                mins, secs = divmod(eta, 60)
                hrs, mins = divmod(mins, 60)
                if hrs > 0:
                    self.eta_formatted = f"{hrs:02d}:{mins:02d}:{secs:02d}"
                else:
                    self.eta_formatted = f"{mins:02d}:{secs:02d}"
            else:
                self.eta_formatted = "--:--"
                
            self._last_time = now
            self._last_bytes = current_bytes

class TurboEngine:
    """
    High-Speed Segmented Multi-Thread Downloader.
    Splits files into parallel Range streams for maximum bandwidth utilization.
    """
    def __init__(self, on_update_callback: Optional[Callable] = None):
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.on_update = on_update_callback
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36 PulseGet/2026"
        )
        self.session_timeout = aiohttp.ClientTimeout(total=None, connect=20, sock_read=30)

    async def emit_update(self, task: DownloadTask):
        if self.on_update:
            try:
                res = self.on_update(task.to_dict())
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    async def probe_url(self, url: str) -> dict:
        """
        Inspects headers to extract filename, content size, and Range support.
        """
        headers = {"User-Agent": self.user_agent}
        async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
            try:
                # First attempt HEAD request
                async with session.head(url, headers=headers, allow_redirects=True) as resp:
                    if resp.status < 400:
                        total_bytes = int(resp.headers.get("Content-Length", 0))
                        accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
                        supports_ranges = (accept_ranges == "bytes")
                        content_type = resp.headers.get("Content-Type", "")
                        
                        # Extract filename
                        filename = self._extract_filename(resp, url)
                        category = detect_category(filename, content_type)
                        
                        # Double check range support if not explicitly stated
                        if not supports_ranges and total_bytes > 0:
                            supports_ranges = await self._test_range_support(session, url)

                        return {
                            "success": True,
                            "url": str(resp.url),
                            "filename": filename,
                            "total_bytes": total_bytes,
                            "total_formatted": format_bytes(total_bytes),
                            "supports_ranges": supports_ranges,
                            "category": category,
                            "content_type": content_type
                        }
            except Exception:
                pass

            # Fallback to GET with Range: bytes=0-0
            try:
                range_header = {"User-Agent": self.user_agent, "Range": "bytes=0-0"}
                async with session.get(url, headers=range_header, allow_redirects=True) as resp:
                    supports_ranges = (resp.status == 206)
                    content_range = resp.headers.get("Content-Range", "")
                    total_bytes = 0
                    if content_range and "/" in content_range:
                        try:
                            total_bytes = int(content_range.split("/")[-1])
                        except ValueError:
                            pass
                    if total_bytes == 0:
                        total_bytes = int(resp.headers.get("Content-Length", 0))
                    
                    filename = self._extract_filename(resp, url)
                    content_type = resp.headers.get("Content-Type", "")
                    category = detect_category(filename, content_type)
                    
                    return {
                        "success": True,
                        "url": str(resp.url),
                        "filename": filename,
                        "total_bytes": total_bytes,
                        "total_formatted": format_bytes(total_bytes),
                        "supports_ranges": supports_ranges,
                        "category": category,
                        "content_type": content_type
                    }
            except Exception as e:
                # If direct request fails, generate filename from path
                parsed = urlparse(url)
                base = os.path.basename(unquote(parsed.path)) or "download_file"
                return {
                    "success": False,
                    "url": url,
                    "filename": base,
                    "total_bytes": 0,
                    "total_formatted": "Unknown",
                    "supports_ranges": False,
                    "category": detect_category(base),
                    "error": str(e)
                }

    async def _test_range_support(self, session: aiohttp.ClientSession, url: str) -> bool:
        try:
            headers = {"User-Agent": self.user_agent, "Range": "bytes=0-0"}
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                return resp.status == 206
        except Exception:
            return False

    def _extract_filename(self, resp: aiohttp.ClientResponse, url: str) -> str:
        # Check Content-Disposition header
        cd = resp.headers.get("Content-Disposition", "")
        if cd and "filename=" in cd:
            parts = cd.split("filename=")
            if len(parts) > 1:
                name = parts[1].split(";")[0].strip("\"' ")
                if name:
                    return unquote(name)

        # Fallback to URL path
        parsed = urlparse(str(resp.url or url))
        path_name = os.path.basename(unquote(parsed.path)).strip()
        if path_name and "." in path_name:
            return path_name
        
        # If no extension in path, guess from Content-Type
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(ctype) or ".bin"
        if not path_name:
            path_name = "download_" + str(uuid.uuid4())[:8]
        return path_name + ext

    def create_task(
        self,
        url: str,
        filename: Optional[str] = None,
        save_path: Optional[str] = None,
        threads: int = 16,
        total_bytes: int = 0,
        supports_ranges: bool = True,
        category: str = "other"
    ) -> DownloadTask:
        task_id = str(uuid.uuid4())
        if not save_path:
            save_path = get_default_download_dir()
        if not filename:
            parsed = urlparse(url)
            filename = os.path.basename(unquote(parsed.path)) or f"file_{task_id[:6]}"

        task = DownloadTask(
            task_id=task_id,
            url=url,
            filename=filename,
            save_path=save_path,
            threads=threads,
            category=category,
            total_bytes=total_bytes,
            supports_ranges=supports_ranges
        )
        self.tasks[task_id] = task
        return task

    async def start_download(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "downloading"
        task.is_paused = False
        task.is_cancelled = False
        await self.emit_update(task)

        # Launch background runner
        runner = asyncio.create_task(self._run_download(task))
        self.active_tasks[task_id] = runner

    async def pause_download(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return
        task.is_paused = True
        task.status = "paused"
        task.speed_bps = 0
        task.speed_formatted = "0 KB/s"
        
        # Cancel running coroutine cleanly
        runner = self.active_tasks.pop(task_id, None)
        if runner and not runner.done():
            runner.cancel()

        await self.emit_update(task)

    async def resume_download(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task or task.status == "completed":
            return
        await self.start_download(task_id)

    async def cancel_download(self, task_id: str, delete_files: bool = True):
        task = self.tasks.get(task_id)
        if not task:
            return
        task.is_cancelled = True
        task.status = "cancelled"
        
        runner = self.active_tasks.pop(task_id, None)
        if runner and not runner.done():
            runner.cancel()

        if delete_files:
            try:
                if os.path.exists(task.temp_dir):
                    shutil.rmtree(task.temp_dir, ignore_errors=True)
                target_file = os.path.join(task.save_path, task.filename)
                if os.path.exists(target_file):
                    os.remove(target_file)
            except Exception:
                pass

        if task_id in self.tasks:
            del self.tasks[task_id]

    async def _run_download(self, task: DownloadTask):
        try:
            # Probe metadata if total_bytes is 0 or range support unknown
            if task.total_bytes <= 0:
                info = await self.probe_url(task.url)
                if info.get("total_bytes", 0) > 0:
                    task.total_bytes = info["total_bytes"]
                    task.supports_ranges = info["supports_ranges"]
                    if not task.filename or task.filename == "download_file":
                        task.filename = info["filename"]
                    task.category = info["category"]
                await self.emit_update(task)

            # Ensure temp dir exists
            os.makedirs(task.temp_dir, exist_ok=True)

            # If multi-segment downloading is supported & size is known and > 500KB
            if task.supports_ranges and task.total_bytes > 500 * 1024:
                try:
                    await self._download_segmented(task)
                except Exception as range_err:
                    # If server failed Range requests, fallback gracefully to single stream
                    task.supports_ranges = False
                    await self._download_single_stream(task)
            else:
                await self._download_single_stream(task)

            if task.is_paused or task.is_cancelled:
                return

            # Download completed! Merge chunks if needed
            if task.supports_ranges and task.total_bytes > 500 * 1024 and task.chunks:
                task.status = "merging"
                await self.emit_update(task)
                await self._merge_chunks(task)

            task.status = "completed"
            task.progress = 100.0
            task.completed_at = time.time()
            task.speed_bps = 0
            task.speed_formatted = "Done"
            task.eta_formatted = "00:00"
            await self.emit_update(task)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not task.is_paused and not task.is_cancelled:
                task.status = "error"
                task.error_message = str(e)
                task.speed_bps = 0
                await self.emit_update(task)

    async def _download_segmented(self, task: DownloadTask):
        """
        High performance segmented multi-thread downloader with aiohttp.
        """
        num_chunks = task.threads
        chunk_size = task.total_bytes // num_chunks
        
        # Initialize chunks state if empty
        if not task.chunks:
            task.chunks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = (task.total_bytes - 1) if (i == num_chunks - 1) else ((i + 1) * chunk_size - 1)
                chunk_total = (end - start) + 1
                task.chunks.append({
                    "id": i,
                    "start": start,
                    "end": end,
                    "total": chunk_total,
                    "downloaded": 0,
                    "progress": 0.0,
                    "active": True
                })

        # Calculate already downloaded bytes from partial files on disk
        total_downloaded = 0
        for chunk in task.chunks:
            part_path = os.path.join(task.temp_dir, f"part_{chunk['id']}.tmp")
            if os.path.exists(part_path):
                cur_size = os.path.getsize(part_path)
                chunk["downloaded"] = min(cur_size, chunk["total"])
            else:
                chunk["downloaded"] = 0
            chunk["progress"] = round((chunk["downloaded"] / chunk["total"]) * 100.0, 1) if chunk["total"] > 0 else 0
            total_downloaded += chunk["downloaded"]

        task.downloaded_bytes = total_downloaded
        if task.total_bytes > 0:
            task.progress = (task.downloaded_bytes / task.total_bytes) * 100.0

        connector = aiohttp.TCPConnector(limit=task.threads * 2, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=connector, timeout=self.session_timeout) as session:
            coros = [self._download_chunk(session, task, chunk) for chunk in task.chunks]
            await asyncio.gather(*coros)

    async def _download_chunk(self, session: aiohttp.ClientSession, task: DownloadTask, chunk: dict):
        part_path = os.path.join(task.temp_dir, f"part_{chunk['id']}.tmp")
        cur_downloaded = chunk["downloaded"]

        if cur_downloaded >= chunk["total"]:
            chunk["active"] = False
            return

        req_start = chunk["start"] + cur_downloaded
        req_end = chunk["end"]
        headers = {
            "User-Agent": self.user_agent,
            "Range": f"bytes={req_start}-{req_end}"
        }

        chunk["active"] = True
        try:
            async with session.get(task.url, headers=headers) as resp:
                if resp.status == 200:
                    raise RuntimeError("Server returned 200 instead of 206 Partial Content")
                if resp.status != 206:
                    raise RuntimeError(f"Server returned status {resp.status} for chunk {chunk['id']}")

                # Write append mode to preserve resume progress
                mode = "ab" if cur_downloaded > 0 else "wb"
                remaining_needed = chunk["total"] - cur_downloaded

                async with aiofiles.open(part_path, mode) as f:
                    async for data in resp.content.iter_chunked(64 * 1024): # 64KB stream buffer
                        if task.is_paused or task.is_cancelled:
                            chunk["active"] = False
                            return

                        to_write = data[:remaining_needed]
                        if to_write:
                            await f.write(to_write)
                            written_len = len(to_write)
                            chunk["downloaded"] += written_len
                            task.downloaded_bytes += written_len
                            remaining_needed -= written_len
                        
                        if chunk["total"] > 0:
                            chunk["progress"] = round((chunk["downloaded"] / chunk["total"]) * 100.0, 1)
                        if task.total_bytes > 0:
                            task.progress = (task.downloaded_bytes / task.total_bytes) * 100.0

                        task.update_speed()
                        await self.emit_update(task)

                        if remaining_needed <= 0:
                            break

            chunk["active"] = False
        except Exception as e:
            chunk["active"] = False
            raise e

    async def _download_single_stream(self, task: DownloadTask):
        """
        Fast single-stream fallback when Range headers are not supported.
        """
        final_dest = os.path.join(task.save_path, task.filename)
        temp_dest = os.path.join(task.temp_dir, "single_stream.tmp")

        headers = {"User-Agent": self.user_agent}
        # Check if partial file exists for resume
        downloaded = 0
        if os.path.exists(temp_dest):
            downloaded = os.path.getsize(temp_dest)
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"

        async with aiohttp.ClientSession(timeout=self.session_timeout) as session:
            async with session.get(task.url, headers=headers) as resp:
                mode = "ab" if (downloaded > 0 and resp.status == 206) else "wb"
                if mode == "wb":
                    downloaded = 0

                task.downloaded_bytes = downloaded
                async with aiofiles.open(temp_dest, mode) as f:
                    async for data in resp.content.iter_chunked(64 * 1024):
                        if task.is_paused or task.is_cancelled:
                            return
                        await f.write(data)
                        task.downloaded_bytes += len(data)
                        if task.total_bytes > 0:
                            task.progress = (task.downloaded_bytes / task.total_bytes) * 100.0
                        
                        task.update_speed()
                        await self.emit_update(task)

        # Move to final destination
        if os.path.exists(temp_dest):
            shutil.move(temp_dest, final_dest)
            shutil.rmtree(task.temp_dir, ignore_errors=True)

    async def _merge_chunks(self, task: DownloadTask):
        """
        Stitches segment chunk files sequentially into final destination.
        """
        final_dest = os.path.join(task.save_path, task.filename)
        
        # Ensure unique destination name if already exists
        base, ext = os.path.splitext(task.filename)
        counter = 1
        while os.path.exists(final_dest):
            final_dest = os.path.join(task.save_path, f"{base}_{counter}{ext}")
            counter += 1
        
        task.filename = os.path.basename(final_dest)

        # Binary stitch
        with open(final_dest, "wb") as outfile:
            for chunk in task.chunks:
                part_path = os.path.join(task.temp_dir, f"part_{chunk['id']}.tmp")
                if os.path.exists(part_path):
                    with open(part_path, "rb") as partfile:
                        shutil.copyfileobj(partfile, outfile, 1024 * 1024) # 1MB buffer

        # Clean up temp folder
        shutil.rmtree(task.temp_dir, ignore_errors=True)
