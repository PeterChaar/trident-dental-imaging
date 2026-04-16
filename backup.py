"""Backup: DB + image_store zipped to a user-chosen folder (e.g. external USB).

Keeps last N backups, auto-runs on app close if configured. Restore unpacks a
chosen zip back into the app directory (DB overwritten, images merged)."""

import os
import json
import shutil
import zipfile
from datetime import datetime
from database import DB_PATH

APP_DIR = os.path.dirname(__file__)
IMAGE_STORE = os.path.join(APP_DIR, "image_store")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "backup_folder": "",
    "auto_backup_on_close": False,
    "keep_last_backups": 10,
    "clinic_name": "Dental Clinic",
    "doctor_name": "",
    "language": "en",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def backup_now(dest_folder):
    """Create timestamped .zip of DB + image_store at dest_folder. Returns path."""
    if not dest_folder:
        raise ValueError("Backup folder not set")
    os.makedirs(dest_folder, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(dest_folder, f"trident_backup_{ts}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(DB_PATH):
            z.write(DB_PATH, arcname="dental_clinic.db")
        if os.path.isdir(IMAGE_STORE):
            for root, _, files in os.walk(IMAGE_STORE):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, APP_DIR)
                    z.write(full, arcname=rel)
    return zip_path


def prune_old_backups(dest_folder, keep_last):
    if not dest_folder or not os.path.isdir(dest_folder):
        return 0
    backups = sorted(
        [f for f in os.listdir(dest_folder)
         if f.startswith("trident_backup_") and f.endswith(".zip")],
        reverse=True,
    )
    removed = 0
    for f in backups[keep_last:]:
        try:
            os.remove(os.path.join(dest_folder, f))
            removed += 1
        except OSError:
            pass
    return removed


def list_backups(dest_folder):
    if not dest_folder or not os.path.isdir(dest_folder):
        return []
    out = []
    for f in sorted(os.listdir(dest_folder), reverse=True):
        if f.startswith("trident_backup_") and f.endswith(".zip"):
            p = os.path.join(dest_folder, f)
            out.append({
                "path": p,
                "name": f,
                "size": os.path.getsize(p),
                "mtime": datetime.fromtimestamp(os.path.getmtime(p)),
            })
    return out


def restore_backup(zip_path):
    """Restore from a backup .zip. DB is replaced, images are merged (no delete).
    Caller must ensure the app is not using the DB (close DB connections first)."""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)

    # Safety snapshot of current DB before overwrite
    if os.path.exists(DB_PATH):
        snap = DB_PATH + f".pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
        shutil.copy2(DB_PATH, snap)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(APP_DIR)
