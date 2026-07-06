from __future__ import annotations

import os
from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import DEVNULL, PIPE
from json import loads
from mimetypes import guess_type
from pathlib import Path
from time import time

_FF_TIMEOUT = 60
_THUMB_TIMEOUT = 45


async def _exec_fftool(
    args: list[str],
    *,
    timeout: int = _FF_TIMEOUT,
    capture_output: bool = True,
) -> tuple[str, str, int]:
    """Run ffmpeg/ffprobe and always terminate the child process on timeout."""
    stdout = PIPE if capture_output else DEVNULL
    stderr = PIPE if capture_output else DEVNULL
    proc = await create_subprocess_exec(*args, stdout=stdout, stderr=stderr)
    try:
        if capture_output:
            out_b, err_b = await wait_for(proc.communicate(), timeout=timeout)
            stdout_s = out_b.decode("utf-8", errors="ignore")
            stderr_s = err_b.decode("utf-8", errors="ignore")
        else:
            await wait_for(proc.wait(), timeout=timeout)
            stdout_s, stderr_s = "", ""
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return stdout_s, stderr_s, proc.returncode if proc.returncode is not None else 1


def _temp_path(prefix: str, suffix: str) -> str:
    """Return a temp file path without creating the file (avoids ffmpeg overwrite prompt)."""
    import tempfile
    base = Path(tempfile.gettempdir())
    return str(base / f"{prefix}{int(time() * 1_000_000)}{suffix}")


def _mime(path: Path) -> str:
    mime_type = guess_type(str(path))[0]
    return mime_type or "application/octet-stream"


async def probe_video_metadata(
    path: Path,
) -> tuple[int, int, int, str | None, str | None]:
    """Single ffprobe call for duration, width, height, artist, title."""
    stdout, _, code = await _exec_fftool(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=_FF_TIMEOUT,
    )
    if code != 0 or not stdout.strip():
        return 0, 480, 320, None, None
    try:
        data = loads(stdout)
    except Exception:
        return 0, 480, 320, None, None

    duration = 0
    fmt = data.get("format", {}) or {}
    if fmt.get("duration") is not None:
        duration = round(float(fmt["duration"]))

    tags = fmt.get("tags", {}) or {}
    artist = tags.get("artist") or tags.get("ARTIST") or tags.get("Artist")
    title = tags.get("title") or tags.get("TITLE") or tags.get("Title")

    width, height = 480, 320
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            w, h = stream.get("width"), stream.get("height")
            if w and h:
                width, height = int(w), int(h)
            break

    return duration, width, height, artist, title


async def get_media_info(path: Path) -> tuple[int, str | None, str | None]:
    duration, _, _, artist, title = await probe_video_metadata(path)
    if duration or artist or title:
        return duration, artist, title

    stdout, _, code = await _exec_fftool(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ],
        timeout=_FF_TIMEOUT,
    )
    if code != 0 or not stdout.strip():
        return 0, None, None
    try:
        fmt = loads(stdout).get("format", {})
    except Exception:
        return 0, None, None
    duration = round(float(fmt.get("duration", 0)))
    tags = fmt.get("tags", {}) or {}
    artist = tags.get("artist") or tags.get("ARTIST") or tags.get("Artist")
    title = tags.get("title") or tags.get("TITLE") or tags.get("Title")
    return duration, artist, title


async def get_document_type(path: Path) -> tuple[bool, bool, bool]:
    mime_type = _mime(path)
    if mime_type.startswith("image"):
        return False, False, True

    stdout, _, code = await _exec_fftool(
        [
            "ffprobe",
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            str(path),
        ],
        timeout=_FF_TIMEOUT,
    )
    if code != 0 or not stdout.strip():
        return mime_type.startswith("video"), mime_type.startswith("audio"), False

    try:
        streams = loads(stdout).get("streams", [])
    except Exception:
        return mime_type.startswith("video"), mime_type.startswith("audio"), False

    is_video = False
    is_audio = False
    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video":
            codec_name = str(stream.get("codec_name", "")).lower()
            if codec_name not in {"mjpeg", "png", "bmp"}:
                is_video = True
        elif codec_type == "audio":
            is_audio = True

    return is_video, is_audio, False


def _ffmpeg_threads() -> list[str]:
    count = os.cpu_count() or 4
    return ["-threads", str(max(count, 1))]


async def _extract_video_frame(
    path: Path, seek: float, out: str, *, use_thumbnail_filter: bool
) -> bool:
    """Extract one JPEG frame from a video at the given seek time (seconds). Returns True if successful."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        str(seek),
        "-i",
        str(path),
    ]
    if use_thumbnail_filter:
        cmd.extend(["-vf", "thumbnail"])
    cmd.extend(
        [
            "-q:v",
            "1",
            "-frames:v",
            "1",
            *_ffmpeg_threads(),
            out,
        ]
    )
    try:
        _, stderr, code = await _exec_fftool(cmd, timeout=_THUMB_TIMEOUT, capture_output=True)
    except TimeoutError:
        return False
    if code != 0 or not Path(out).is_file() or Path(out).stat().st_size == 0:
        if stderr:
            pass  # caller may log
        Path(out).unlink(missing_ok=True)
        return False
    return True


async def get_video_thumbnail(
    path: Path,
    duration: int | None = None,
    *,
    thumb_seek: float = 0,
) -> str | None:
    if duration is None:
        duration = (await get_media_info(path))[0]
    if duration <= 0:
        duration = 3
    if thumb_seek > 0:
        seek = thumb_seek
    else:
        seek = float(max(duration // 2, 1))
    if duration > 0:
        seek = min(seek, max(float(duration) - 0.05, 0.05))

    out = _temp_path("btu_vthumb_", ".jpg")

    # Fast path first.
    if await _extract_video_frame(path, seek, out, use_thumbnail_filter=False):
        return out

    # Fallback: thumbnail filter for a better still frame.
    if await _extract_video_frame(path, seek, out, use_thumbnail_filter=True):
        return out

    return None


async def get_video_dimensions(path: Path) -> tuple[int, int]:
    _, width, height, _, _ = await probe_video_metadata(path)
    return width, height


async def get_audio_thumbnail(path: Path) -> str | None:
    out = _temp_path("btu_athumb_", ".jpg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(path),
        "-an",
        "-vcodec",
        "copy",
        *_ffmpeg_threads(),
        out,
    ]
    try:
        _, _, code = await _exec_fftool(cmd, timeout=_THUMB_TIMEOUT)
    except TimeoutError:
        return None
    if code != 0 or not Path(out).is_file() or Path(out).stat().st_size == 0:
        Path(out).unlink(missing_ok=True)
        return None
    return out
