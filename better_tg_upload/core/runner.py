from argparse import Namespace
from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE
from json import dumps
from pathlib import Path

from .client_manager import TelegramClientManager
from .config import config_path, ensure_workspace, load_user_config, mask_secret, user_config_snapshot
from .exceptions import CliError
from .validate import validate_telegram_args
from ..transfer.splitter import combine_files, split_file
from ..utils.fs import file_hashes


def _is_utility_only(args: Namespace) -> bool:
    return any(
        [
            args.combine,
            args.hash_file,
            args.split_file,
            args.convert,
            args.file_info,
            args.env,
            args.frame is not None,
        ]
    )


async def _capture_frame(args: Namespace) -> bool:
    """Capture a video frame at the specified second using ffmpeg."""
    if args.frame is None:
        return False
    if not args.path:
        raise CliError("--frame requires --path to specify the video file.")
    src = Path(args.path)
    if not src.is_file():
        raise CliError(f"Invalid video file for --frame: {src}")

    second = int(args.frame)
    out = Path(args.filename or f"{src.stem}_frame_{second}s").with_suffix(".jpg")

    proc = await create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-ss", str(second),
        "-i", str(src),
        "-vf", "thumbnail",
        "-q:v", "1",
        "-frames:v", "1",
        str(out),
        stdout=PIPE,
        stderr=PIPE,
    )
    _, stderr = await wait_for(proc.communicate(), timeout=90)

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="ignore").strip()
        raise CliError(f"Frame capture failed: {err or 'ffmpeg error'}")

    print(f"Frame captured -> {out}")
    return True


def _run_utility_commands(args: Namespace) -> bool:
    if args.combine:
        parts = [Path(p) for p in args.combine]
        for p in parts:
            if not p.exists():
                raise CliError(f"Combine part not found: {p}")
        output_name = args.filename or parts[0].stem
        output_path = Path(args.combine_dir) / output_name
        combine_files(parts, output_path, max(int(args.combine_memory_limit), 1))
        print(f"Combined -> {output_path}")
        return True

    if args.hash_file:
        p = Path(args.hash_file)
        if not p.is_file():
            raise CliError(f"Invalid file for --hash: {p}")
        h_sha, h_md5 = file_hashes(p, max(int(args.hash_memory_limit), 1))
        print(f"File Name:\n{p.name}\nSHA256:\n{h_sha}\nMD5:\n{h_md5}")
        return True

    if args.split_file:
        if not args.path:
            raise CliError("--split_file requires --path.")
        src = Path(args.path)
        if not src.is_file():
            raise CliError(f"Invalid file path for split: {src}")
        out = split_file(src, int(args.split_file), Path(args.split_dir))
        print(f"Created {len(out)} part files in {Path(args.split_dir)}")
        return True

    if args.file_info:
        p = Path(args.file_info)
        if not p.exists():
            raise CliError(f"Invalid path for --file_info: {p}")
        st = p.stat()
        print(
            f"File Name:\n{p.name}\nSize:\n{st.st_size} bytes\nCreated:\n{st.st_ctime}\nModified:\n{st.st_mtime}"
        )
        return True

    if args.convert:
        from PIL import Image

        src = Path(args.convert)
        if not src.is_file():
            raise CliError(f"Invalid image for --convert: {src}")
        out = Path(args.filename or src.stem).with_suffix(".jpg")
        with Image.open(src) as img:
            img.convert("RGB").save(out, "JPEG")
        print(f"Converted -> {out}")
        return True

    if args.env:
        load_user_config()
        resolved = {
            "config_file": str(config_path()) if config_path() else None,
            "workspace_dir": str(ensure_workspace()),
            "profile": args.profile,
            "api_id": args.api_id,
            "api_hash": mask_secret(args.api_hash),
            "phone": args.phone,
            "bot_token": mask_secret(args.bot),
            "session_string": mask_secret(args.login_string),
            "path": args.path,
            "chat_id": args.chat_id,
            "caption": args.caption,
            "session_dir": args.session_dir,
            "split_dir": args.split_dir,
            "dl_dir": args.dl_dir,
            "sleep": args.sleep,
            "config_py": user_config_snapshot(),
        }
        print(dumps(resolved, indent=2, default=str))
        return True

    # --frame is async, handled separately in run_cli
    if args.frame is not None:
        return False

    return False


async def _run_login_flows(client, args: Namespace) -> bool:
    if args.login_only:
        print("Authorization completed!")
        return True
    if args.export_string:
        print(await client.export_session_string())
        return True
    if args.logout:
        await client.log_out()
        print(f"Terminated [{args.profile}]")
        return True
    if args.info:
        me = await client.get_me()
        print(me)
        return True
    return False


async def run_cli(args: Namespace) -> int:
    try:
        handled = _run_utility_commands(args)
        if handled:
            return 0
    except CliError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    # Handle async utility commands (--frame)
    try:
        if args.frame is not None:
            done = await _capture_frame(args)
            if done:
                return 0
    except CliError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    if _is_utility_only(args):
        return 0

    try:
        ensure_workspace()
        validate_telegram_args(args)
        async with TelegramClientManager(args) as client:
            if await _run_login_flows(client, args):
                return 0
            if args.dl:
                from ..transfer.download import run_download_mode

                await run_download_mode(client, args)
            else:
                from ..transfer.upload import run_upload_mode

                await run_upload_mode(client, args)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except CliError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

