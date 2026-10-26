from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
ENGINE_DIR = ROOT_DIR / "engine"
CONFIG_PATH = ROOT_DIR / "config.json"

STRENGTH_PRESETS: dict[str, tuple[str, int, int, int]] = {
    "economy": ("省电", 800, 2, 64),
    "balanced": ("均衡", 2000, 4, 256),
    "deep": ("深度", 3500, 6, 512),
    "max": ("极限", 6000, 8, 1024),
}
CUSTOM_STRENGTH = "custom"

DEFAULT_CONFIG: dict[str, Any] = {
    "engine_path": "",
    "strength": "balanced",
    "adaptive": True,
    "analysis_ms": 2000,
    "debounce_ms": 300,
    "threads": 4,
    "hash_mb": 256,
    "opacity": 0.94,
    "geometry": None,
    "show_coords": True,
    "compact": False,
    "auto_accept": False,
    "low_priority": True,
}

MIN_OPACITY = 0.15
MAX_OPACITY = 1.0
DEFAULT_OPACITY = 0.94

MIN_WIDTH = 300
MIN_HEIGHT = 380
DEFAULT_GEOMETRY = [1100, 160, 470, 578]

def find_engine(explicit: str | None = None) -> Optional[Path]:

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if ENGINE_DIR.is_dir():
        candidates.extend(sorted(ENGINE_DIR.glob("stockfish*.exe")))
        candidates.extend(sorted(ENGINE_DIR.glob("stockfish*")))
    which = shutil.which("stockfish")
    if which:
        candidates.append(Path(which))

    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None

def apply_preset(cfg: dict[str, Any], name: str) -> None:

    if name in STRENGTH_PRESETS:
        _, ms, threads, hash_mb = STRENGTH_PRESETS[name]
        cfg["analysis_ms"] = ms
        cfg["threads"] = threads
        cfg["hash_mb"] = hash_mb
    cfg["strength"] = name

def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    raw: dict[str, Any] = {}
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw = loaded
            cfg.update({k: v for k, v in raw.items() if k in DEFAULT_CONFIG})
    except (OSError, ValueError):
        pass

    if "strength" not in raw:
        apply_preset(cfg, "balanced")
    return _sanitize(cfg)

def save_config(cfg: dict[str, Any]) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(_sanitize(cfg), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass

def _sanitize(cfg: dict[str, Any]) -> dict[str, Any]:
    out = dict(cfg)
    out["analysis_ms"] = int(max(100, min(30000, int(out.get("analysis_ms") or 2000))))
    out["debounce_ms"] = int(max(0, min(2000, int(out.get("debounce_ms") or 0))))
    out["threads"] = int(max(1, min(32, int(out.get("threads") or 4))))
    out["hash_mb"] = int(max(16, min(4096, int(out.get("hash_mb") or 256))))
    try:
        opacity = float(out.get("opacity") or 0.94)
    except (TypeError, ValueError):
        opacity = 0.94
    out["opacity"] = round(max(MIN_OPACITY, min(MAX_OPACITY, opacity)), 3)
    geo = out.get("geometry")
    if not (isinstance(geo, list) and len(geo) == 4):
        out["geometry"] = None
    out["show_coords"] = bool(out.get("show_coords", True))
    out["compact"] = bool(out.get("compact", False))
    out["auto_accept"] = bool(out.get("auto_accept", False))
    out["adaptive"] = bool(out.get("adaptive", True))
    out["low_priority"] = bool(out.get("low_priority", True))
    strength = out.get("strength")
    if strength not in STRENGTH_PRESETS and strength != CUSTOM_STRENGTH:
        strength = "balanced"
    out["strength"] = strength
    return out
