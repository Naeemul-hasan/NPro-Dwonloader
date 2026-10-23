import os
import json
from pathlib import Path
from typing import Dict, List, Any
from core.downloader import get_default_download_dir

DATA_DIR = Path.home() / ".pulseget_pro"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"

DEFAULT_SETTINGS = {
    "save_directory": get_default_download_dir(),
    "default_threads": 16,
    "max_active_downloads": 4,
    "speed_limit_kbps": 0, # 0 means unlimited
    "notifications_enabled": True,
    "sound_effects": True,
    "theme": "glass_dark",
    "clipboard_watch": True,
    "auto_start": True
}

class StorageManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.settings = self._load_settings()
        self.history = self._load_history()

    def _load_settings(self) -> Dict[str, Any]:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with default settings for any new keys
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return dict(DEFAULT_SETTINGS)

    def save_settings(self, new_settings: Dict[str, Any]):
        self.settings.update(new_settings)
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_history(self) -> List[Dict[str, Any]]:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save_history(self, task_list: List[Dict[str, Any]]):
        try:
            # Keep up to 200 items in history
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(task_list[:200], f, indent=2, ensure_ascii=False)
        except Exception:
            pass
