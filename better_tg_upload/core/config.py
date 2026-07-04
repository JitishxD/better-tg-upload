"""Central configuration: defaults, paths, and user ``config.py``"""

from __future__ import annotations

import sys
from pathlib import Path
from sys import version_info
from typing import Any

# -------- Working-directory paths --------

_SUFFIX = "_tg_upload"

SPLIT_DIR = f"split{_SUFFIX}"
COMBINE_DIR = f"combine{_SUFFIX}"
DOWNLOADS_DIR = f"downloads{_SUFFIX}"
THUMB_DIR = f"thumb{_SUFFIX}"
SESSIONS_DIR = f".sessions{_SUFFIX}"
UPLOAD_RESUME_DIR = f".upload_resume{_SUFFIX}"
UPLOAD_TREE_STATE_DIR = f".upload_tree{_SUFFIX}"

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
