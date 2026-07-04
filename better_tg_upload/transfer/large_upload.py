"""Premium-aware large file splitting with resume support."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, cast

from pyrogram.client import Client

from ..utils.fs import format_bytes
from ..core.config import UPLOAD_RESUME_DIR
from .splitter import (
    clear_all_parts,
    discover_binary_parts,
    discover_ffmpeg_parts,
    ffmpeg_split_video,
    split_file,
    _validate_ffmpeg_sequence,
)

_STATE_VERSION = 1


class SplitResumeEntry(TypedDict):
    size: int | float
    mtime: int | float
    next_part: int
    total_parts: int
    chunk_size: int
    equal_splits: bool
    split_method: str
    split_dir: str

# Telegram limits
UPLOAD_LIMIT_STANDARD = 2_097_152_000
UPLOAD_LIMIT_PREMIUM = 4_194_304_000
CHUNK_SAFETY_MARGIN = 5_000_000


def file_fingerprint(path: Path) -> dict[str, int | float]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}


async def get_upload_limit(client: Client) -> tuple[int, bool]:
    me = await client.get_me()
    is_premium = bool(getattr(me, "is_premium", False))
    limit = UPLOAD_LIMIT_PREMIUM if is_premium else UPLOAD_LIMIT_STANDARD
    return limit, is_premium


def max_chunk_size(upload_limit: int) -> int:
    return max(upload_limit - CHUNK_SAFETY_MARGIN, 1)


def needs_split(file_size: int, upload_limit: int) -> bool:
    return file_size > upload_limit


def plan_split(file_size: int, upload_limit: int, *, equal_splits: bool) -> tuple[int, int]:
    """Return chunk size and expected part count for a file."""
    limit_chunk = max_chunk_size(upload_limit)
    part_count = -(-file_size // limit_chunk)  # ceil division
    if equal_splits:
        chunk_size = (file_size // part_count) + (file_size % part_count)
    else:
        chunk_size = limit_chunk
        part_count = -(-file_size // chunk_size)
    return chunk_size, part_count


def work_dir_for_file(file_path: Path, split_root: Path) -> Path:
    digest = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[:16]
    return split_root / digest


def part_caption(part_filename: str) -> str:
    """monospace part filename."""
    return f"<code>{part_filename}</code>"


async def upload_parts_sequential(
    parts: list[Path],
    start_idx: int,
    *,
    send_part: Callable[[Path, str, int], Awaitable[None]],
    on_part_done: Callable[[int], None],
    sleep_between: Callable[[], Awaitable[None]],
    log=print,
) -> None:
    """Upload split parts one-by-one with progress (no Telegram albums)."""
    total = len(parts)
    for idx in range(start_idx, total):
        part_path = parts[idx]
        caption = part_caption(part_path.name)
        log(
            f"Uploading part {idx + 1}/{total}: {part_path.name} "
            f"({format_bytes(part_path.stat().st_size)})"
        )
        await send_part(part_path, caption, idx)
        on_part_done(idx + 1)
        if idx + 1 < total:
            await sleep_between()


def _validate_binary_parts(parts: list[Path]) -> bool:
    from .splitter import _validate_binary_sequence

    return _validate_binary_sequence(parts)


@dataclass
class SplitResumeStore:
    path: Path
    profile: str
    chat_id: str
    entries: dict[str, SplitResumeEntry] = field(default_factory=dict)

    @classmethod
    def default_path(cls, profile: str) -> Path:
        safe = hashlib.sha256(profile.encode("utf-8")).hexdigest()[:12]
        return Path(UPLOAD_RESUME_DIR) / f"{safe}.json"

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        profile: str,
        chat_id: str,
        use_resume: bool,
    ) -> SplitResumeStore:
        store = cls(path=path, profile=profile, chat_id=str(chat_id))
        if not use_resume or not path.is_file():
            return store
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: Could not read resume state ({exc}); starting fresh.")
            return store
        if data.get("version") != _STATE_VERSION:
            print("WARNING: Resume state version mismatch; starting fresh.")
            return store
        if data.get("profile") != profile:
            print("WARNING: Resume state is for a different profile; starting fresh.")
            return store
        if data.get("chat_id") != str(chat_id):
            print("WARNING: Resume state is for a different chat; starting fresh.")
            return store
        store.entries = cast(dict[str, SplitResumeEntry], data.get("entries", {}))
        return store

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _STATE_VERSION,
            "profile": self.profile,
            "chat_id": self.chat_id,
            "entries": self.entries,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def file_key(self, file_path: Path) -> str:
        return str(file_path.resolve())

    def split_resume_start(
        self,
        file_key: str,
        file_path: Path,
        *,
        total_parts: int,
        chunk_size: int,
        equal_splits: bool,
        split_method: str,
        split_dir: Path,
    ) -> int:
        saved = self.entries.get(file_key)
        if not saved:
            return 0
        current = file_fingerprint(file_path)
        if (
            saved["size"] != current["size"]
            or saved["mtime"] != current["mtime"]
            or saved["total_parts"] != total_parts
            or saved["chunk_size"] != chunk_size
            or saved["equal_splits"] != equal_splits
            or saved["split_method"] != split_method
            or saved["split_dir"] != str(split_dir)
        ):
            return 0
        next_part = saved["next_part"]
        if next_part < 0:
            return 0
        if next_part > total_parts:
            return total_parts
        return next_part

    def mark_split_part(
        self,
        file_key: str,
        file_path: Path,
        *,
        next_part: int,
        total_parts: int,
        chunk_size: int,
        equal_splits: bool,
        split_method: str,
        split_dir: Path,
    ) -> None:
        fp = file_fingerprint(file_path)
        self.entries[file_key] = {
            "size": fp["size"],
            "mtime": fp["mtime"],
            "next_part": next_part,
            "total_parts": total_parts,
            "chunk_size": chunk_size,
            "equal_splits": equal_splits,
            "split_method": split_method,
            "split_dir": str(split_dir),
        }
        self.save()

    def mark_complete(self, file_key: str) -> None:
        self.entries.pop(file_key, None)
        self.save()


async def prepare_parts(
    src_file: Path,
    split_dir: Path,
    chunk_size: int,
    *,
    use_ffmpeg: bool,
    max_part_bytes: int,
    expected_parts: int,
) -> tuple[list[Path], str]:
    """Return split parts and method used (``ffmpeg`` or ``binary``)."""
    split_dir.mkdir(parents=True, exist_ok=True)

    if use_ffmpeg:
        existing = discover_ffmpeg_parts(split_dir, src_file.name)
        if existing and _validate_ffmpeg_sequence(existing):
            return existing, "ffmpeg"
        clear_all_parts(split_dir, src_file.name)
        parts = await ffmpeg_split_video(
            src_file,
            split_dir,
            chunk_size,
            max_part_bytes=max_part_bytes,
            expected_parts=expected_parts,
        )
        if parts:
            return parts, "ffmpeg"
        print(
            f"WARNING: ffmpeg split failed for {src_file.name}; "
            "falling back to GNU/binary split."
        )

    existing = discover_binary_parts(split_dir, src_file.name)
    if existing and _validate_binary_parts(existing):
        return existing, "binary"

    clear_all_parts(split_dir, src_file.name)
    return split_file(src_file, chunk_size, split_dir), "binary"


def cleanup_split_dir(split_dir: Path) -> None:
    if split_dir.exists():
        shutil.rmtree(split_dir, ignore_errors=True)
