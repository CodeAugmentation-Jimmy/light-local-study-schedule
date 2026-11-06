"""Persistent user data paths and first-install migration for the Windows package."""
import json
import os
from pathlib import Path
import sys
import uuid

from . import Ledger, load_settings


def data_directory():
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return base / "StudySchedule"
    return Path(__file__).resolve().parents[1]


def import_legacy(source_directory, destination):
    """Validate and copy only data, never overwrite an existing installation's data."""
    source = Path(source_directory).resolve()
    destination = Path(destination).resolve()
    target = destination / "学习记录.json"
    if target.exists():
        raise FileExistsError("安装版已存在学习记录，不会覆盖")
    original = source / "学习记录.json"
    stored = json.loads(original.read_text(encoding="utf-8"))
    if not isinstance(stored, list):
        raise ValueError("学习记录格式不正确")
    settings_path = source / "同步设置.json"
    settings = load_settings(settings_path) if settings_path.exists() else None
    ledger = Ledger(settings["device"] if settings else "import", stored)
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / ("import-" + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(ledger.stored(), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        if settings and not (destination / "同步设置.json").exists():
            (destination / "同步设置.json").write_text(json.dumps(settings), encoding="utf-8")
        if target.exists():
            raise FileExistsError("安装版已存在学习记录，不会覆盖")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
