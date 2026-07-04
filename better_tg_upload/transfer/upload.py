from argparse import Namespace
from asyncio import sleep
from pathlib import Path

from pyrogram import enums
from pyrogram.client import Client
from pyrogram.errors import BadRequest, RPCError

from ..core.exceptions import CliError
from ..core.link_parser import normalize_chat_id
from ..utils.fs import apply_name_mutations, build_caption
from ..utils.media import (
    cleanup_temp_file,
    load_caption_template,
    resolve_thumbnail,
)
from .media_probe import (
    get_audio_thumbnail,
    get_document_type,
    get_media_info,
    get_video_dimensions,
    get_video_thumbnail,
)
from .progress import TransferProgress
from .retry import run_with_floodwait_retry
from .large_upload import (
    SplitResumeStore,
    cleanup_split_dir,
    get_upload_limit,
    needs_split,
    plan_split,
    prepare_parts,
    upload_parts_sequential,
    work_dir_for_file,
)


def _parse_mode(name: str):
    mapping = {
        "DEFAULT": enums.ParseMode.DEFAULT,
        "HTML": enums.ParseMode.HTML,
        "MARKDOWN": enums.ParseMode.MARKDOWN,
        "DISABLED": enums.ParseMode.DISABLED,
    }
    return mapping.get(str(name).upper(), enums.ParseMode.DEFAULT)


def _thumb_seek(args: Namespace) -> float:
    return float(getattr(args, "thumb_seek", 0) or 0)


async def _send_one(
    client: Client,
    args: Namespace,
    chat_id: int | str,
    src_path: Path,
    caption_text: str,
    parse_mode,
    *,
    caption_override: str | None = None,
    display_name_override: str | None = None,
    message_thread_id: int | None = None,
    force_document: bool = False,
) -> None:
    display_name = display_name_override or apply_name_mutations(src_path.name, args)
    progress = TransferProgress("UP", display_name)
    forced_thumb = await resolve_thumbnail(src_path, args)
    thumb = forced_thumb

    base_kwargs = {
        "disable_notification": bool(args.silent),
        "reply_to_message_id": int(args.reply_to) if args.reply_to else None,
        "protect_content": bool(args.protect),
        "progress": progress.callback,
    }
    if message_thread_id is not None:
        base_kwargs["message_thread_id"] = message_thread_id
    base_kwargs = {k: v for k, v in base_kwargs.items() if v is not None}

    cap = caption_override if caption_override is not None else build_caption(
        src_path, caption_text, args
    )
    if not cap:
        cap = display_name
    is_video, is_audio, is_image = await get_document_type(src_path)

    if (is_audio and not is_video) and thumb is None:
        thumb = await get_audio_thumbnail(src_path)

    async def _send_document():
        if is_video and thumb is None:
            auto_thumb = await get_video_thumbnail(
                src_path, None, thumb_seek=_thumb_seek(args)
            )
        else:
            auto_thumb = None
        send_thumb = thumb or auto_thumb
        doc_kwargs = dict(base_kwargs)
        if send_thumb is not None:
            doc_kwargs["thumb"] = send_thumb
        try:
            return await client.send_document(
                chat_id,
                str(src_path),
                caption=cap,
                parse_mode=parse_mode,
                file_name=display_name,
                force_document=True,
                **doc_kwargs,
            )
        finally:
            await cleanup_temp_file(auto_thumb, args)

    async def _send_video():
        duration = int(args.duration) if args.duration else (await get_media_info(src_path))[0]
        if thumb is None:
            auto_thumb = await get_video_thumbnail(
                src_path, duration, thumb_seek=_thumb_seek(args)
            )
        else:
            auto_thumb = None
        send_thumb = thumb or auto_thumb
        # Auto-detect video dimensions when not explicitly provided
        if int(args.width) == 0 and int(args.height) == 0:
            _vid_w, _vid_h = await get_video_dimensions(src_path)
        else:
            _vid_w = int(args.width)
            _vid_h = int(args.height)
        video_kwargs = dict(base_kwargs)
        if _vid_w:
            video_kwargs["width"] = _vid_w
        if _vid_h:
            video_kwargs["height"] = _vid_h
        if duration:
            video_kwargs["duration"] = duration
        if send_thumb is not None:
            video_kwargs["thumb"] = send_thumb
        if args.self_destruct:
            video_kwargs["ttl_seconds"] = int(args.self_destruct)
        try:
            return await client.send_video(
                chat_id,
                str(src_path),
                caption=cap,
                parse_mode=parse_mode,
                file_name=display_name,
                supports_streaming=not bool(args.disable_stream),
                has_spoiler=bool(args.spoiler),
                **video_kwargs,
            )
        finally:
            await cleanup_temp_file(auto_thumb, args)

    async def _send_audio():
        duration, artist, title = await get_media_info(src_path)
        audio_kwargs = dict(base_kwargs)
        audio_duration = int(args.duration) if args.duration else duration
        if audio_duration:
            audio_kwargs["duration"] = audio_duration
        performer = args.artist or artist
        if performer:
            audio_kwargs["performer"] = performer
        audio_title = args.title or title
        if audio_title:
            audio_kwargs["title"] = audio_title
        if thumb is not None:
            audio_kwargs["thumb"] = thumb
        return await client.send_audio(
            chat_id,
            str(src_path),
            caption=cap,
            parse_mode=parse_mode,
            file_name=display_name,
            **audio_kwargs,
        )

    async def _send_photo():
        photo_kwargs = dict(base_kwargs)
        if args.self_destruct:
            photo_kwargs["ttl_seconds"] = int(args.self_destruct)
        return await client.send_photo(
            chat_id,
            str(src_path),
            caption=cap,
            parse_mode=parse_mode,
            has_spoiler=bool(args.spoiler),
            **photo_kwargs,
        )

    async def _send_voice():
        duration = int(args.duration) if args.duration else (await get_media_info(src_path))[0]
        voice_kwargs = dict(base_kwargs)
        if duration:
            voice_kwargs["duration"] = duration
        return await client.send_voice(
            chat_id,
            str(src_path),
            caption=cap,
            parse_mode=parse_mode,
            **voice_kwargs,
        )

    async def _send_video_note():
        duration = int(args.duration) if args.duration else (await get_media_info(src_path))[0]
        note_kwargs = dict(base_kwargs)
        if duration:
            note_kwargs["duration"] = duration
        if thumb is not None:
            note_kwargs["thumb"] = thumb
        return await client.send_video_note(
            chat_id,
            str(src_path),
            **note_kwargs,
        )

    async def send_action(doc_fallback: bool = False):
        if force_document or doc_fallback or not (
            args.as_photo
            or args.as_video
            or args.as_audio
            or args.as_voice
            or args.as_video_note
            or is_video
            or is_audio
            or is_image
        ):
            return await _send_document()
        if args.as_voice:
            return await _send_voice()
        if args.as_video_note:
            return await _send_video_note()
        if args.as_photo:
            return await _send_photo()
        if args.as_video:
            return await _send_video()
        if args.as_audio:
            return await _send_audio()
        if is_video:
            return await _send_video()
        if is_audio:
            return await _send_audio()
        if is_image:
            return await _send_photo()
        return await _send_document()

    async def resilient_action():
        try:
            return await send_action(False)
        except BadRequest:
            return await send_action(True)
        except RPCError:
            raise

    await run_with_floodwait_retry(resilient_action)
    progress.newline()
    await cleanup_temp_file(thumb, args)
    await cleanup_temp_file(forced_thumb, args)


async def run_upload_mode(client: Client, args: Namespace) -> None:
    src = Path(args.path)
    if not src.exists():
        raise CliError(f"Path not found: {src}")

    if src.is_dir():
        from .tree_upload import run_tree_upload_mode

        await run_tree_upload_mode(client, args)
        return

    if not src.is_file():
        raise CliError(f"Path is not a file or directory: {src}")

    parse_mode = _parse_mode(args.parse_mode)
    caption, template_mode = load_caption_template(args)
    if template_mode:
        parse_mode = _parse_mode(template_mode)
    chat_id = normalize_chat_id(args.chat_id)
    split_root = Path(args.split_dir)
    split_root.mkdir(parents=True, exist_ok=True)

    upload_limit, is_premium = await get_upload_limit(client)
    print(
        "Upload account: "
        f"{'premium' if is_premium else 'standard'} "
        f"(limit {upload_limit} bytes)"
    )

    resume_store = SplitResumeStore.load(
        SplitResumeStore.default_path(args.profile or "default"),
        profile=args.profile or "default",
        chat_id=str(chat_id),
        use_resume=not bool(args.no_resume),
    )

    successes = 0
    failures = 0
    item = src

    if item.stat().st_size == 0:
        raise CliError(f"Zero-size file: {item}")

    try:
        file_size = item.stat().st_size

        if needs_split(file_size, upload_limit):
            equal_splits = bool(args.equal_splits)
            chunk_size, expected_parts = plan_split(
                file_size, upload_limit, equal_splits=equal_splits
            )
            is_video, _, _ = await get_document_type(item)
            use_ffmpeg = bool(is_video)
            split_dir = work_dir_for_file(item, split_root)
            mode = "equal" if equal_splits else "fixed"
            split_kind = "ffmpeg" if use_ffmpeg else "gnu"
            print(
                f"Splitting {item.name} ({file_size} bytes) "
                f"into ~{expected_parts} parts ({mode}, {split_kind}, "
                f"chunk {chunk_size} bytes)"
            )
            parts, split_method = await prepare_parts(
                item,
                split_dir,
                chunk_size,
                use_ffmpeg=use_ffmpeg,
                max_part_bytes=upload_limit,
                expected_parts=expected_parts,
            )
            if not parts:
                raise RuntimeError(f"Split produced no parts for {item.name}.")

            file_key = resume_store.file_key(item)
            start_idx = resume_store.split_resume_start(
                file_key,
                item,
                total_parts=len(parts),
                chunk_size=chunk_size,
                equal_splits=equal_splits,
                split_method=split_method,
                split_dir=split_dir,
            )
            if start_idx >= len(parts):
                print(f"Skip split file (already uploaded): {item.name}")
            else:
                if start_idx > 0:
                    print(
                        f"Resuming split upload for {item.name} "
                        f"from part {start_idx + 1}/{len(parts)}"
                    )

                async def _send_part(part_path: Path, part_cap: str, _part_idx: int) -> None:
                    await _send_one(
                        client,
                        args,
                        chat_id,
                        part_path,
                        caption,
                        enums.ParseMode.HTML,
                        caption_override=part_cap,
                        force_document=True,
                    )

                def _on_part_done(next_part: int) -> None:
                    resume_store.mark_split_part(
                        file_key,
                        item,
                        next_part=next_part,
                        total_parts=len(parts),
                        chunk_size=chunk_size,
                        equal_splits=equal_splits,
                        split_method=split_method,
                        split_dir=split_dir,
                    )

                await upload_parts_sequential(
                    parts,
                    start_idx,
                    send_part=_send_part,
                    on_part_done=_on_part_done,
                    sleep_between=lambda: sleep(float(getattr(args, "sleep", 1.0) or 1.0)),
                )
            resume_store.mark_complete(file_key)
            if not args.keep_split_parts:
                cleanup_split_dir(split_dir)
        else:
            await _send_one(
                client,
                args,
                chat_id,
                item,
                caption,
                parse_mode,
                force_document=bool(getattr(args, "document_only", False)),
            )
            if args.delete_on_done and item.exists():
                item.unlink()
        successes = 1
    except Exception as e:
        print(f"ERROR: Failed to upload {item}: {e}")
        failures = 1

    total = successes + failures
    if failures:
        print(f"Upload failed: {item}")
    elif total:
        print(f"Upload complete: {item.name}")
