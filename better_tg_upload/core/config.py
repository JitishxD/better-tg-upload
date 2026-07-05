"""Central configuration: defaults, paths, and user ``config.py``"""

from __future__ import annotations

import sys
from pathlib import Path
from sys import version_info
from typing import Any

# -------- Working-directory paths --------

WORKSPACE_DIR = ".tg_upload"

SESSIONS_DIR = f"{WORKSPACE_DIR}/sessions"
DOWNLOADS_DIR = f"{WORKSPACE_DIR}/downloads"
SPLIT_DIR = f"{WORKSPACE_DIR}/split"
COMBINE_DIR = f"{WORKSPACE_DIR}/combine"
THUMB_DIR = f"{WORKSPACE_DIR}/thumb"
UPLOAD_RESUME_DIR = f"{WORKSPACE_DIR}/upload_resume"
UPLOAD_TREE_STATE_DIR = f"{WORKSPACE_DIR}/upload_tree"

_WORKSPACE_SUBDIRS = (
    "sessions",
    "downloads",
    "split",
    "combine",
    "thumb",
    "upload_resume",
    "upload_tree",
)

_MISSING = object()
_USER: dict[str, Any] = {}
_CONFIG_LOADED = False
_CONFIG_PATH: Path | None = None


def missing_msg(name: str, cli_flag: str) -> str:
    """Human-readable hint when a setting is absent from CLI and config.py."""
    return f"{name} is missing. Set {name} in config.py or pass {cli_flag}."


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _user_value(name: str) -> Any:
    if name not in _USER:
        return _MISSING
    return _USER[name]


def load_user_config() -> Path | None:
    """Import ``config.py`` from the current working directory."""
    global _CONFIG_LOADED, _CONFIG_PATH
    if _CONFIG_LOADED:
        return _CONFIG_PATH
    _CONFIG_LOADED = True

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        import config as user_config  # noqa: PLC0415
    except ModuleNotFoundError:
        _CONFIG_PATH = None
        return None

    _CONFIG_PATH = Path(getattr(user_config, "__file__", "config.py")).resolve()
    for key, value in vars(user_config).items():
        if key.startswith("_"):
            continue
        _USER[key] = value
    return _CONFIG_PATH


def config_path() -> Path | None:
    load_user_config()
    return _CONFIG_PATH


def workspace_root() -> Path:
    """Resolved workspace directory (override with ``WORKSPACE_DIR`` in config.py)."""
    load_user_config()
    name = cfg_str("WORKSPACE_DIR", WORKSPACE_DIR) or WORKSPACE_DIR
    return Path(name).resolve()


def ensure_workspace() -> Path:
    """Create the workspace folder and standard subfolders."""
    root = workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    for sub in _WORKSPACE_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def ensure_session_dir(path: str) -> Path:
    """Create the session directory if needed and return it."""
    session_dir = Path(path)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _resolve_dir(config_key: str, default: str) -> str:
    load_user_config()
    return cfg_str(config_key, default) or default


def upload_resume_dir() -> str:
    return _resolve_dir("UPLOAD_RESUME_DIR", UPLOAD_RESUME_DIR)


def upload_tree_state_dir() -> str:
    return _resolve_dir("UPLOAD_TREE_STATE_DIR", UPLOAD_TREE_STATE_DIR)


def cfg_str(name: str, default: str | None = None) -> str | None:
    val = _user_value(name)
    if val is not _MISSING and not _is_empty(val):
        return str(val)
    return default


def cfg_int(name: str, default: int) -> int:
    val = _user_value(name)
    if val is not _MISSING and not _is_empty(val):
        return int(val)
    return default


def cfg_float(name: str, default: float) -> float:
    val = _user_value(name)
    if val is not _MISSING and not _is_empty(val):
        return float(val)
    return default


def cfg_bool(name: str, default: bool = False) -> bool:
    val = _user_value(name)
    if val is not _MISSING and not _is_empty(val):
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return default


def default_system_version() -> str:
    fallback = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    return cfg_str("SYSTEM_VERSION", fallback) or fallback


def user_config_snapshot() -> dict[str, Any]:
    load_user_config()
    return dict(_USER)


def mask_secret(value: object) -> object:
    if value and isinstance(value, str):
        return "***"
    return value
