"""Validate CLI args before connecting to Telegram."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from .config import ensure_session_dir
from .config import missing_msg
from .exceptions import CliError


def _session_path(args: Namespace) -> Path | None:
    if not args.profile:
        return None
    session_dir = ensure_session_dir(args.session_dir).resolve()
    return session_dir / f"{args.profile}.session"


def needs_api_credentials(args: Namespace) -> bool:
    if args.login_string:
        return False
    session_path = _session_path(args)
    if session_path is None:
        return True
    if args.tmp_session:
        return True
    return not session_path.exists()


def _is_login_flow_only(args: Namespace) -> bool:
    return bool(args.login_only or args.export_string or args.logout or args.info)


def _collect_core(args: Namespace) -> list[str]:
    missing: list[str] = []
    if not args.profile:
        missing.append(missing_msg("PROFILE", "-p/--profile"))
    if needs_api_credentials(args):
        if not args.api_id:
            missing.append(missing_msg("API_ID", "--api_id"))
        if not args.api_hash:
            missing.append(missing_msg("API_HASH", "--api_hash"))
    return missing


def _collect_upload(args: Namespace) -> list[str]:
    missing: list[str] = []
    if not args.path:
        missing.append(missing_msg("PATH", "-l/--path"))
    if not args.chat_id:
        missing.append(missing_msg("CHAT_ID", "-c/--chat_id"))
    return missing


def _collect_download(args: Namespace) -> list[str]:
    missing: list[str] = []
    has_links = bool(args.links)
    has_txt = bool(args.txt_file)
    has_msg = bool(args.msg_id)
    if not (has_links or has_txt or has_msg):
        missing.append(
            "Download source is missing. Pass --links, --txt_file, or --msg_id."
        )
    if has_msg and not args.chat_id:
        missing.append(missing_msg("CHAT_ID", "-c/--chat_id"))
    return missing


def collect_missing(args: Namespace) -> list[str]:
    missing = _collect_core(args)
    if _is_login_flow_only(args):
        return missing
    if args.dl:
        missing.extend(_collect_download(args))
    else:
        missing.extend(_collect_upload(args))
    return missing


def validate_telegram_args(args: Namespace) -> None:
    missing = collect_missing(args)
    if not missing:
        return
    if len(missing) == 1:
        raise CliError(missing[0])
    lines = "\n".join(f"  • {item}" for item in missing)
    raise CliError(f"Missing required settings:\n{lines}")
