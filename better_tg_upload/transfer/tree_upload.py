"""Folder-tree upload: announce subfolders, upload files with tree-level resume."""

from __future__ import annotations

import hashlib
import json
import os
from argparse import Namespace
from asyncio import sleep
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, cast

from pyrogram import enums
from pyrogram.client import Client

from ..core.chat_resolve import resolve_chat_target
from ..core.exceptions import CliError
from ..utils.fs import format_bytes
from ..core.config import UPLOAD_TREE_STATE_DIR
from .large_upload import (
    cleanup_split_dir,
    get_upload_limit,
    needs_split,
    plan_split,
    prepare_parts,
    upload_parts_sequential,
    work_dir_for_file,
)
from .media_probe import get_document_type
from .retry import run_with_floodwait_retry
from .upload import _parse_mode, _send_one
from ..utils.media import load_caption_template

_STATE_VERSION = 1


class SplitProgressEntry(TypedDict):
    size: int | float
    mtime: int | float
    next_part: int
    total_parts: int
    chunk_size: int
    equal_splits: bool
    split_method: str


def _file_fingerprint(path: Path) -> dict[str, int | float]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}


def default_tree_state_path(root: Path) -> Path:
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(UPLOAD_TREE_STATE_DIR) / f"{root.name}_{digest}.json"


def _sort_names(names: list[str]) -> list[str]:
    try:
        from natsort import natsorted

        return list(natsorted(names))
    except ImportError:
        return sorted(names)


@dataclass
class TreeResumeState:
    root: str
    chat_id: str
    folders_announced: set[str] = field(default_factory=set)
    files_uploaded: dict[str, dict[str, int | float]] = field(default_factory=dict)
    files_split_progress: dict[str, SplitProgressEntry] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, root: Path, chat_id: str, *, use_resume: bool) -> TreeResumeState:
        fresh = cls(root=str(root.resolve()), chat_id=str(chat_id))
        if not use_resume or not path.is_file():
            return fresh
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: Could not read tree state ({exc}); starting fresh.")
            return fresh
        if data.get("version") != _STATE_VERSION:
            print("WARNING: Tree state version mismatch; starting fresh.")
            return fresh
        if data.get("root") != str(root.resolve()):
            print("WARNING: Tree state is for a different folder; starting fresh.")
            return fresh
        if data.get("chat_id") != str(chat_id):
            print("WARNING: Tree state is for a different chat; starting fresh.")
            return fresh
        fresh.folders_announced = set(data.get("folders_announced", []))
        fresh.files_uploaded = dict(data.get("files_uploaded", {}))
        fresh.files_split_progress = cast(
            dict[str, SplitProgressEntry], data.get("files_split_progress", {})
        )
        return fresh

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _STATE_VERSION,
            "root": self.root,
            "chat_id": self.chat_id,
            "folders_announced": sorted(self.folders_announced),
            "files_uploaded": self.files_uploaded,
            "files_split_progress": self.files_split_progress,
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    def folder_done(self, rel_folder: str) -> bool:
        return rel_folder in self.folders_announced

    def file_done(self, rel_file: str, path: Path) -> bool:
        saved = self.files_uploaded.get(rel_file)
        if not saved:
            return False
        return saved == _file_fingerprint(path)

    def mark_folder(self, rel_folder: str, state_path: Path) -> None:
        self.folders_announced.add(rel_folder)
        self.save(state_path)

    def mark_file(self, rel_file: str, file_path: Path, state_path: Path) -> None:
        self.files_uploaded[rel_file] = _file_fingerprint(file_path)
        self.files_split_progress.pop(rel_file, None)
        self.save(state_path)

    def split_resume_start(
        self,
        rel_file: str,
        file_path: Path,
        *,
        total_parts: int,
        chunk_size: int,
        equal_splits: bool,
        split_method: str,
    ) -> int:
        saved = self.files_split_progress.get(rel_file)
        if not saved:
            return 0
        current = _file_fingerprint(file_path)
        if (
            saved["size"] != current["size"]
            or saved["mtime"] != current["mtime"]
            or saved["total_parts"] != total_parts
            or saved["chunk_size"] != chunk_size
            or saved["equal_splits"] != equal_splits
            or saved["split_method"] != split_method
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
        rel_file: str,
        file_path: Path,
        *,
        next_part: int,
        total_parts: int,
        chunk_size: int,
        equal_splits: bool,
        split_method: str,
        state_path: Path,
    ) -> None:
        fp = _file_fingerprint(file_path)
        self.files_split_progress[rel_file] = SplitProgressEntry(
            size=fp["size"],
            mtime=fp["mtime"],
            next_part=next_part,
            total_parts=total_parts,
            chunk_size=chunk_size,
            equal_splits=equal_splits,
            split_method=split_method,
        )
        self.save(state_path)


async def _announce_folder(
    client: Client,
    chat_id: int | str,
    rel_folder: str,
    thread_id: int | None,
) -> None:
    msg_kwargs: dict[str, Any] = {}
    if thread_id is not None:
        msg_kwargs["message_thread_id"] = thread_id

    async def _send() -> None:
        await client.send_message(chat_id, rel_folder, **msg_kwargs)

    await run_with_floodwait_retry(_send)


async def _upload_tree_file(
    client: Client,
    args: Namespace,
    chat_id: int | str,
    file_path: Path,
    *,
    caption: str,
    parse_mode,
    upload_limit: int,
    split_root: Path,
    rel_file: str,
    state: TreeResumeState,
    state_path: Path,
    thread_id: int | None,
) -> None:
    file_size = file_path.stat().st_size
    force_document = bool(getattr(args, "document_only", False))

    if not needs_split(file_size, upload_limit):
        await _send_one(
            client,
            args,
            chat_id,
            file_path,
            caption,
            parse_mode,
            message_thread_id=thread_id,
            force_document=force_document,
        )
        return

    equal_splits = bool(args.equal_splits)
    chunk_size, expected_parts = plan_split(
        file_size, upload_limit, equal_splits=equal_splits
    )
    is_video, _, _ = await get_document_type(file_path)
    use_ffmpeg = bool(is_video and not force_document)
    split_dir = work_dir_for_file(file_path, split_root)
    print(
        f"Splitting {file_path.name} ({format_bytes(file_size)}) "
        f"into ~{expected_parts} parts "
        f"({'equal' if equal_splits else 'fixed'}, "
        f"{'ffmpeg' if use_ffmpeg else 'gnu'}, chunk {format_bytes(chunk_size)})"
    )
    parts, split_method = await prepare_parts(
        file_path,
        split_dir,
        chunk_size,
        use_ffmpeg=use_ffmpeg,
        max_part_bytes=upload_limit,
        expected_parts=expected_parts,
    )
    if not parts:
        raise RuntimeError(f"Split produced no parts for {file_path.name}.")

    start_part = state.split_resume_start(
        rel_file,
        file_path,
        total_parts=len(parts),
        chunk_size=chunk_size,
        equal_splits=equal_splits,
        split_method=split_method,
    )
    if start_part >= len(parts):
        print(f"Skip split file (already uploaded): {rel_file}")
    else:
        if start_part > 0:
            print(f"Resuming split upload for {rel_file} from part {start_part + 1}/{len(parts)}")

        async def _send_part(part_path: Path, part_cap: str, _part_idx: int) -> None:
            await _send_one(
                client,
                args,
                chat_id,
                part_path,
                caption,
                enums.ParseMode.HTML,
                caption_override=part_cap,
                message_thread_id=thread_id,
                force_document=True,
            )

        def _on_part_done(next_part: int) -> None:
            state.mark_split_part(
                rel_file,
                file_path,
                next_part=next_part,
                total_parts=len(parts),
                chunk_size=chunk_size,
                equal_splits=equal_splits,
                split_method=split_method,
                state_path=state_path,
            )

        await upload_parts_sequential(
            parts,
            start_part,
            send_part=_send_part,
            on_part_done=_on_part_done,
            sleep_between=lambda: sleep(float(getattr(args, "sleep", 1.0) or 1.0)),
        )

    if not args.keep_split_parts:
        cleanup_split_dir(split_dir)


async def run_tree_upload_mode(client: Client, args: Namespace) -> None:
    """Upload a directory tree: folder-name messages + files with resume."""
    if args.dl:
        raise CliError("Folder upload is not available in download mode.")

    root = Path(args.path).resolve()
    if not root.is_dir():
        raise CliError(f"Expected a directory path, got: {root}")

    state_path = (
        Path(args.tree_state)
        if getattr(args, "tree_state", None)
        else default_tree_state_path(root)
    ).resolve()
    if getattr(args, "reset_tree", False) and state_path.exists():
        state_path.unlink()
        print(f"Reset tree state: {state_path}")

    parse_mode = _parse_mode(args.parse_mode)
    caption, template_mode = load_caption_template(args)
    if template_mode:
        parse_mode = _parse_mode(template_mode)

    target = await resolve_chat_target(client, args.chat_id)
    chat_id = target.chat_id
    thread_id = target.thread_id
    print(f"Target chat: {target.title} ({chat_id})")

    split_root = Path(args.split_dir)
    split_root.mkdir(parents=True, exist_ok=True)

    upload_limit, is_premium = await get_upload_limit(client)
    print(
        "Upload account: "
        f"{'premium' if is_premium else 'standard'} "
        f"(limit {format_bytes(upload_limit)})"
    )

    state = TreeResumeState.load(
        state_path,
        root,
        str(chat_id),
        use_resume=not bool(args.no_resume),
    )
    if state.files_uploaded or state.folders_announced:
        print(
            f"Resuming tree upload ({len(state.folders_announced)} folders, "
            f"{len(state.files_uploaded)} files done) -> {state_path}"
        )
    else:
        print(f"Tree state file: {state_path}")

    uploaded = 0
    skipped = 0
    failed = 0
    upload_delay = float(getattr(args, "sleep", 1.0) or 1.0)

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = _sort_names(dirnames)
        current = Path(dirpath)
        rel_dir = current.relative_to(root)
        rel_folder = str(rel_dir).replace("\\", "/")

        if rel_dir != Path("."):
            if state.folder_done(rel_folder):
                print(f"Skip folder message: {rel_folder}")
            else:
                print(f"Folder: {rel_folder}")
                await _announce_folder(client, chat_id, rel_folder, thread_id)
                state.mark_folder(rel_folder, state_path)

        for fname in _sort_names(filenames):
            file_path = current / fname
            if file_path.stat().st_size == 0:
                print(f"WARNING: Skipping zero-size file: {file_path.name}")
                continue

            rel_file = str(file_path.relative_to(root)).replace("\\", "/")
            if not args.no_resume and state.file_done(rel_file, file_path):
                print(f"Skip (done): {rel_file}")
                skipped += 1
                continue

            print(f"Uploading: {rel_file} ({format_bytes(file_path.stat().st_size)})")
            try:
                await _upload_tree_file(
                    client,
                    args,
                    chat_id,
                    file_path,
                    caption=caption,
                    parse_mode=parse_mode,
                    upload_limit=upload_limit,
                    split_root=split_root,
                    rel_file=rel_file,
                    state=state,
                    state_path=state_path,
                    thread_id=thread_id,
                )
                state.mark_file(rel_file, file_path, state_path)
                uploaded += 1
            except Exception as exc:
                print(f"ERROR: Failed to upload {rel_file}: {exc}")
                failed += 1
                continue

            await sleep(upload_delay)

    print(
        f"Tree upload finished: {uploaded} uploaded, "
        f"{skipped} skipped (resume), {failed} failed. State -> {state_path}"
    )
