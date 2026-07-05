"""Central configuration: defaults, paths, and user ``config.py``"""

from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path
from sys import version_info
from typing import Any

from .exceptions import CliError

APP_DIR_NAME = ".better-tg-upload"
WORKSPACE_NAME = ".tg_upload"

_DEFAULT_HOME = Path.home() / APP_DIR_NAME
_DEFAULT_WORKSPACE = _DEFAULT_HOME / WORKSPACE_NAME

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
_CONFIG_OVERRIDE: Path | None = None
_WORKSPACE_OVERRIDE: Path | None = None


def app_home() -> Path:
    """Global app directory under the user home."""
    return _DEFAULT_HOME


def default_config_path() -> Path:
    return app_home() / "config.py"


def default_workspace_path() -> Path:
    return app_home() / WORKSPACE_NAME


def set_config_path(path: Path | None) -> None:
    """Override the config file path (from ``--config``)."""
    global _CONFIG_OVERRIDE, _CONFIG_LOADED, _CONFIG_PATH
    _USER.clear()
    _CONFIG_LOADED = False
    _CONFIG_PATH = None
    if path is None:
        _CONFIG_OVERRIDE = None
        return
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CliError(f"Config file not found: {resolved}")
    _CONFIG_OVERRIDE = resolved


def set_workspace_path(path: Path | None) -> None:
    """Override the workspace directory (from ``--workspace``)."""
    global _WORKSPACE_OVERRIDE
    _WORKSPACE_OVERRIDE = path.expanduser().resolve() if path else None


def resolved_config_path() -> Path:
    if _CONFIG_OVERRIDE is not None:
        return _CONFIG_OVERRIDE
    return default_config_path()


def config_dir() -> Path:
    path = config_path()
    if path is not None:
        return path.parent
    return app_home()


def missing_msg(name: str, cli_flag: str) -> str:
    """Human-readable hint when a setting is absent from CLI and config.py."""
    return f"{name} is missing (config.py or {cli_flag})."


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


def _load_config_file(path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("btu_user_config", path)
    if spec is None or spec.loader is None:
        raise CliError(f"Failed to load config: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        key: value
        for key, value in vars(module).items()
        if not key.startswith("_")
    }


def load_user_config() -> Path | None:
    """Load ``config.py`` from the resolved global config path."""
    global _CONFIG_LOADED, _CONFIG_PATH
    if _CONFIG_LOADED:
        return _CONFIG_PATH
    _CONFIG_LOADED = True

    path = resolved_config_path()
    if not path.is_file():
        _CONFIG_PATH = None
        return None

    _CONFIG_PATH = path.resolve()
    _USER.update(_load_config_file(_CONFIG_PATH))
    return _CONFIG_PATH


def config_path() -> Path | None:
    load_user_config()
    return _CONFIG_PATH


def config_source() -> str:
    if _CONFIG_OVERRIDE is not None:
        return "cli"
    return "global"


def workspace_source() -> str:
    if _WORKSPACE_OVERRIDE is not None:
        return "cli"
    load_user_config()
    val = _user_value("WORKSPACE_DIR")
    if val is not _MISSING and not _is_empty(val):
        return "config"
    return "global"


def workspace_root() -> Path:
    """Resolved workspace directory for runtime data."""
    if _WORKSPACE_OVERRIDE is not None:
        return _WORKSPACE_OVERRIDE
    load_user_config()
    default = str(default_workspace_path())
    name = cfg_str("WORKSPACE_DIR", default) or default
    return Path(name).expanduser().resolve()


def workspace_subdir(name: str) -> str:
    """Default absolute path for a standard folder under the resolved workspace."""
    return str(workspace_root() / name)


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
    return _resolve_dir("UPLOAD_RESUME_DIR", workspace_subdir("upload_resume"))


def upload_tree_state_dir() -> str:
    return _resolve_dir("UPLOAD_TREE_STATE_DIR", workspace_subdir("upload_tree"))


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
        "app_home": str(app_home()),
        "config_file": str(resolved_config_path()),
        "config_loaded": config_path() is not None,
        "config_source": config_source(),
        "workspace_dir": str(ensure_workspace()),
        "workspace_source": workspace_source(),
        "path_overrides": path_overrides(args),
        "resolved": build_resolved_config(args),
    }
