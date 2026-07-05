"""Central configuration: defaults, paths, and user ``config.py``"""

from __future__ import annotations

import sys
from argparse import Namespace
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


def mask_secret(value: object) -> object:
    if value and isinstance(value, str):
        return "***"
    return value


_PATH_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("session_dir", "sessions", "SESSION_DIR", "--session_dir"),
    ("split_dir", "split", "SPLIT_DIR", "--split_dir"),
    ("dl_dir", "downloads", "DL_DIR", "--dl_dir"),
    ("combine_dir", "combine", "COMBINE_DIR", "--combine_dir"),
    ("thumb_dir", "thumb", "THUMB_DIR", "--thumb_dir"),
    ("upload_resume_dir", "upload_resume", "UPLOAD_RESUME_DIR", ""),
    ("upload_tree_state_dir", "upload_tree", "UPLOAD_TREE_STATE_DIR", ""),
)


def _resolve_path(path: str) -> str:
    return str(Path(path).resolve())


def _cli_flag_used(flag: str) -> bool:
    if not flag:
        return False
    for arg in sys.argv[1:]:
        if arg == flag or arg.startswith(f"{flag}="):
            return True
    return False


def _path_override_source(cli_flag: str, config_key: str) -> str:
    if _cli_flag_used(cli_flag):
        return "cli"
    load_user_config()
    val = _user_value(config_key)
    if val is not _MISSING and not _is_empty(val):
        return "config"
    return "default"


def resolved_paths(args: Namespace) -> dict[str, str]:
    """Absolute paths the CLI will use for workspace data."""
    paths = {
        "session_dir": _resolve_path(args.session_dir),
        "split_dir": _resolve_path(args.split_dir),
        "dl_dir": _resolve_path(args.dl_dir),
        "combine_dir": _resolve_path(args.combine_dir),
        "thumb_dir": _resolve_path(args.thumb_dir),
        "upload_resume_dir": _resolve_path(upload_resume_dir()),
        "upload_tree_state_dir": _resolve_path(upload_tree_state_dir()),
    }
    return paths


def path_overrides(args: Namespace) -> dict[str, dict[str, str]]:
    """Paths that differ from the standard workspace layout."""
    root = ensure_workspace()
    paths = resolved_paths(args)
    overrides: dict[str, dict[str, str]] = {}
    for key, subdir, config_key, cli_flag in _PATH_SPECS:
        effective = Path(paths[key])
        default = (root / subdir).resolve()
        if effective != default:
            overrides[key] = {
                "path": str(effective),
                "source": _path_override_source(cli_flag, config_key),
            }
    return overrides


def build_resolved_config(args: Namespace) -> dict[str, Any]:
    """Effective settings after CLI > config.py > code defaults."""
    load_user_config()
    return {
        "auth": {
            "profile": args.profile,
            "api_id": args.api_id,
            "api_hash": mask_secret(args.api_hash),
            "phone": args.phone,
            "bot_token": mask_secret(args.bot),
            "session_string": mask_secret(args.login_string),
        },
        "target": {
            "path": args.path,
            "chat_id": args.chat_id,
            "caption": args.caption,
            "capjson": args.capjson,
            "filename": args.filename,
            "thumb": args.thumb,
            "thumb_seek": args.thumb_seek,
            "duration": args.duration,
            "parse_mode": args.parse_mode,
            "reply_to": args.reply_to,
            "self_destruct": args.self_destruct,
        },
        "upload": {
            "equal_splits": args.equal_splits,
            "no_resume": args.no_resume,
            "keep_split_parts": args.keep_split_parts,
            "document_only": args.document_only,
            "disable_stream": args.disable_stream,
            "reset_tree": args.reset_tree,
            "sleep": args.sleep,
            "prefix": args.prefix,
            "replace": args.replace,
            "tree_state": str(args.tree_state) if args.tree_state else None,
        },
        "download": {
            "dl_dir": resolved_paths(args)["dl_dir"],
            "auto_combine": args.auto_combine,
        },
        "client": {
            "proxy": args.proxy,
            "ipv6": args.ipv6,
            "device_model": args.device_model,
            "system_version": args.system_version,
            "verbose": args.verbose,
        },
        "limits": {
            "hash_memory_limit": args.hash_memory_limit,
            "combine_memory_limit": args.combine_memory_limit,
        },
        "paths": resolved_paths(args),
    }


def build_env_snapshot(args: Namespace) -> dict[str, Any]:
    """JSON-serializable snapshot for ``--env``."""
    load_user_config()
    return {
        "config_file": str(config_path()) if config_path() else None,
        "workspace_dir": str(ensure_workspace()),
        "path_overrides": path_overrides(args),
        "resolved": build_resolved_config(args),
    }
