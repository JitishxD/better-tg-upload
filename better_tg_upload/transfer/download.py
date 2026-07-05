from argparse import Namespace
from pathlib import Path

from pyrogram.client import Client

from ..core.exceptions import CliError
from ..core.link_parser import normalize_chat_id, parse_tg_link
from .progress import TransferProgress
from .retry import run_with_floodwait_retry
from .splitter import combine_files, discover_part_groups


def _resolve_message_filename(message, fallback_prefix: str = "MSG") -> str:
    media = (
        message.document
        or message.photo
        or message.video
        or message.audio
        or message.voice
        or message.video_note
        or message.sticker
        or message.animation
    )
    if media is None:
        raise CliError(f"No downloadable media in message {message.id}.")
    name = getattr(media, "file_name", None)
    if name:
        return name.replace("/", "_")
    ext = "bin"
    mime = getattr(media, "mime_type", "") or ""
    if "/" in mime:
        ext = mime.split("/")[-1]
    return f"{fallback_prefix}_{message.id}.{ext}"


async def _download_message(client: Client, message, out_dir: Path, args: Namespace) -> Path:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _resolve_message_filename(message)
    out_path = (out_dir / name).resolve()
    progress = TransferProgress("DL", name)

    async def action():
        return await message.download(
            file_name=str(out_path),
            progress=progress.callback,
        )

    result = await run_with_floodwait_retry(action)
    progress.newline()
    if not result:
        raise CliError(f"Download failed for message {message.id}.")
    saved = Path(result).resolve()
    print(f"Saved -> {saved}")
    return saved


async def _get_message(client: Client, chat_id: int | str, message_id: int):
    msg = await client.get_messages(chat_id=chat_id, message_ids=message_id)
    if not msg or getattr(msg, "empty", False):
        raise CliError(f"Message not accessible: chat={chat_id}, id={message_id}")
    return msg


def _range(a: int, b: int) -> range:
    return range(a, b + 1) if a <= b else range(b, a + 1)


def _auto_combine(out_dir: Path, args: Namespace) -> None:
    """Discover and combine split part groups in the download directory."""
    out_dir = out_dir.resolve()
    groups = discover_part_groups(out_dir)
    if not groups:
        files = sorted(p.name for p in out_dir.iterdir() if p.is_file())
        if files:
            shown = ", ".join(files[:8])
            if len(files) > 8:
                shown += ", ..."
            print(f"No split part groups to combine in {out_dir} (found: {shown})")
        else:
            print(f"No files to combine in {out_dir}")
        return

    chunk_size = max(int(args.combine_memory_limit), 1)
    for base_name, parts in groups.items():
        out_path = out_dir / base_name
        expected_size = sum(part.stat().st_size for part in parts)
        print(f"Combining {len(parts)} parts -> {out_path}")
        combine_files(parts, out_path, chunk_size)
        if not out_path.is_file():
            raise CliError(f"Combine failed: output not created: {out_path}")
        actual_size = out_path.stat().st_size
        if actual_size != expected_size:
            raise CliError(
                f"Combine size mismatch for {out_path}: "
                f"expected {expected_size} bytes, got {actual_size} bytes. "
                "Part files were left in place."
            )
        for part in parts:
            part.unlink(missing_ok=True)
        print(f"Combined successfully -> {out_path} ({actual_size} bytes)")


async def run_download_mode(client: Client, args: Namespace) -> None:
    out_dir = Path(args.dl_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Download directory: {out_dir}")
    links = [x.strip() for x in args.links if str(x).strip()]
    if args.txt_file:
        txt = Path(args.txt_file)
        if not txt.is_file():
            raise CliError(f"Invalid txt file: {txt}")
        links.extend([ln.strip() for ln in txt.read_text(encoding="utf-8").splitlines() if ln.strip()])

    successes = 0
    failures = 0

    if links:
        if args.range_mode:
            if len(links) < 2:
                raise CliError("--range requires at least 2 links.")
            l1, l2 = parse_tg_link(links[0]), parse_tg_link(links[1])
            if l1.chat_id != l2.chat_id:
                raise CliError("Range links must belong to same chat.")
            for msg_id in _range(l1.message_id, l2.message_id):
                try:
                    msg = await _get_message(client, l1.chat_id, msg_id)
                    await _download_message(client, msg, out_dir, args)
                    successes += 1
                except Exception as e:
                    print(f"ERROR: Failed to download message {msg_id}: {e}")
                    failures += 1
                    continue
        else:
            for link in links:
                try:
                    ref = parse_tg_link(link)
                    msg = await _get_message(client, ref.chat_id, ref.message_id)
                    await _download_message(client, msg, out_dir, args)
                    successes += 1
                except Exception as e:
                    print(f"ERROR: Failed to download {link}: {e}")
                    failures += 1
                    continue
    elif args.msg_id:
        chat_id = normalize_chat_id(args.chat_id)
        if args.range_mode:
            if len(args.msg_id) < 2:
                raise CliError("--range requires at least 2 message ids.")
            for msg_id in _range(args.msg_id[0], args.msg_id[1]):
                try:
                    msg = await _get_message(client, chat_id, msg_id)
                    await _download_message(client, msg, out_dir, args)
                    successes += 1
                except Exception as e:
                    print(f"ERROR: Failed to download message {msg_id}: {e}")
                    failures += 1
                    continue
        else:
            for msg_id in args.msg_id:
                try:
                    msg = await _get_message(client, chat_id, int(msg_id))
                    await _download_message(client, msg, out_dir, args)
                    successes += 1
                except Exception as e:
                    print(f"ERROR: Failed to download message {msg_id}: {e}")
                    failures += 1
                    continue
    else:
        raise CliError("No source provided. Use --links/--txt_file or --msg_id.")

    # Print download summary
    total = successes + failures
    if total > 0:
        print(f"Download complete: {successes}/{total} succeeded, {failures} failed.")

    # Auto-combine split parts if requested
    if args.auto_combine:
        _auto_combine(out_dir, args)
