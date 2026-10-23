import os
import re
import time
import shutil
import asyncio
from typing import Dict, Any, Optional, Callable
import yt_dlp

KNOWN_MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com",
    "tiktok.com", "twitter.com", "x.com", "vimeo.com", "soundcloud.com",
    "reddit.com", "twitch.tv", "dailymotion.com", "pinterest.com"
]

def is_social_or_media_url(url: str) -> bool:
    """Detects if URL matches popular video/audio streaming services."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in KNOWN_MEDIA_DOMAINS)

def find_ffmpeg_binary() -> Optional[str]:
    """Finds ffmpeg executable in PATH, local project bin, or WinGet packages."""
    # 1. System PATH
    p = shutil.which("ffmpeg")
    if p:
        return p

    # 2. Project local bin folder
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_bin = os.path.join(project_root, "bin", "ffmpeg.exe")
    if os.path.exists(local_bin):
        return local_bin

    # 3. Check WinGet Packages in LocalAppData
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_dir = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
        if os.path.exists(winget_dir):
            for root, dirs, files in os.walk(winget_dir):
                if "ffmpeg.exe" in files:
                    return os.path.join(root, "ffmpeg.exe")

    # 4. Common Windows program paths
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\ffmpeg.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\ffmpeg\bin\ffmpeg.exe")
    ]
    for cp in common_paths:
        if os.path.exists(cp):
            return cp

    return None

class MediaExtractor:
    """
    Extracts and downloads multimedia (videos, audio, reels, clips)
    from 1000+ platforms at high speed using yt-dlp.
    """
    def __init__(self):
        self.ydl_opts_base = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'socket_timeout': 15,
        }

    async def get_media_info(self, url: str) -> Dict[str, Any]:
        """
        Analyzes media URL in an executor thread to avoid blocking the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_sync, url)

    def _extract_sync(self, url: str) -> Dict[str, Any]:
        try:
            has_ffmpeg = (find_ffmpeg_binary() is not None)
            
            with yt_dlp.YoutubeDL(self.ydl_opts_base) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return {"success": False, "error": "No media found at URL."}

                title = info.get("title", "media_download")
                # Clean filename
                clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                thumbnail = info.get("thumbnail", "")
                duration = info.get("duration", 0)
                uploader = info.get("uploader", "Unknown Artist")
                
                # Parse format options
                formats = []
                raw_formats = info.get("formats", [])
                
                # Check video resolutions
                seen_res = set()
                # Sort best quality first
                for f in sorted(raw_formats, key=lambda x: (x.get("height") or 0), reverse=True):
                    h = f.get("height")
                    ext = f.get("ext", "mp4")
                    vcodec = f.get("vcodec", "none")
                    acodec = f.get("acodec", "none")
                    if h and h >= 360 and vcodec != "none" and h not in seen_res:
                        seen_res.add(h)
                        label = f"{h}p ({ext.upper()})"
                        if h >= 2160:
                            label = "4K Ultra HD (2160p)"
                        elif h >= 1440:
                            label = "2K Quad HD (1440p)"
                        elif h >= 1080:
                            label = "Full HD (1080p)"
                        elif h >= 720:
                            label = "HD (720p)"
                        
                        filesize = f.get("filesize") or f.get("filesize_approx") or 0
                        formats.append({
                            "id": f.get("format_id"),
                            "label": label,
                            "type": "video",
                            "height": h,
                            "ext": ext,
                            "filesize": filesize
                        })

                # Best Direct MP4 Stream (Zero FFmpeg needed)
                formats.insert(0, {
                    "id": "best[ext=mp4]/best",
                    "label": "⚡ Fast Direct MP4 (Recommended - No Muxing)",
                    "type": "video",
                    "height": 720,
                    "ext": "mp4",
                    "filesize": 0
                })

                # Max Quality Muxed (If FFmpeg available)
                if has_ffmpeg:
                    formats.insert(1, {
                        "id": "bestvideo+bestaudio/best",
                        "label": "🌟 Max Quality HD (Merged Video + Audio)",
                        "type": "video",
                        "height": 9999,
                        "ext": "mp4",
                        "filesize": 0
                    })

                # Audio Options
                formats.append({
                    "id": "bestaudio[ext=m4a]/bestaudio",
                    "label": "🎵 High-Quality Audio (M4A / AAC - Fast)",
                    "type": "audio",
                    "height": 0,
                    "ext": "m4a",
                    "filesize": 0
                })

                if has_ffmpeg:
                    formats.append({
                        "id": "bestaudio/best",
                        "label": "🎧 Audio Studio MP3 (320kbps Converted)",
                        "type": "audio",
                        "height": 0,
                        "ext": "mp3",
                        "filesize": 0
                    })

                return {
                    "success": True,
                    "url": url,
                    "title": clean_title,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "uploader": uploader,
                    "formats": formats
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_media_sync(
        self,
        url: str,
        format_id: str,
        output_dir: str,
        filename_template: str,
        progress_callback: Optional[Callable] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> Dict[str, Any]:
        """
        Synchronously runs yt-dlp download with high-speed multi-fragment concurrency.
        """
        is_audio = "audio" in format_id or "bestaudio" in format_id
        ffmpeg_bin = find_ffmpeg_binary()

        # If ffmpeg is missing and user requested separate streams, fallback to single stream
        if not ffmpeg_bin:
            if not is_audio and ("+" in format_id or "bestvideo" in format_id):
                format_id = "best[ext=mp4]/best"
            elif is_audio and "mp3" in format_id:
                format_id = "bestaudio[ext=m4a]/bestaudio"

        def ydl_hook(d):
            if progress_callback:
                status = d.get('status')
                if status == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    speed = d.get('speed') or 0
                    eta = d.get('eta') or 0
                    progress = (downloaded / total * 100.0) if total > 0 else 0
                    
                    progress_callback({
                        "status": "downloading",
                        "downloaded_bytes": downloaded,
                        "total_bytes": total,
                        "speed_bps": speed,
                        "eta_seconds": eta,
                        "progress": round(progress, 1)
                    })
                elif status == 'finished':
                    progress_callback({
                        "status": "merging",
                        "progress": 99.0
                    })

        outtmpl = os.path.join(output_dir, f"{filename_template}.%(ext)s")
        
        ydl_opts = {
            'format': format_id if format_id else 'best[ext=mp4]/best',
            'outtmpl': outtmpl,
            'progress_hooks': [ydl_hook],
            'concurrent_fragment_downloads': 8, # Turbo speed for multi-stream fragments
            'quiet': True,
            'no_warnings': True,
        }

        if ffmpeg_bin:
            ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_bin)
            if is_audio and "mp3" in format_id:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(info)
                if ffmpeg_bin and is_audio and "mp3" in format_id:
                    final_filename = os.path.splitext(final_filename)[0] + ".mp3"
                return {"success": True, "file_path": final_filename}
        except Exception as e:
            return {"success": False, "error": str(e)}
