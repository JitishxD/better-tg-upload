from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .media_probe import _exec_fftool, get_media_info

_NUMERIC_PART = re.compile(r"^(?P<base>.+)\.(?P<num>\d{3})$")
_LEGACY_PART = re.compile(r"^(?P<base>.+)\.part(?P<num>\d+)$")
_FFMPEG_PART = re.compile(r"^(?P<stem>.+)\.part(?P<num>\d{3})(?P<ext>\.[^.]+)$")
FFMPEG_SIZE_MARGIN = 3_000_000


def part_path(split_dir: Path, src_name: str, part_number: int) -> Path:
    """GNU split style: ``bigfile.zip.001``."""
    return split_dir / f"{src_name}.{part_number:03d}"


def split_file(file_path: Path, chunk_size: int, split_dir: Path) -> list[Path]:
    split_dir.mkdir(parents=True, exist_ok=True)
    parts = _split_with_gnu(file_path, chunk_size, split_dir)
    if parts:
        return parts
    return _split_with_python(file_path, chunk_size, split_dir)


def _split_with_gnu(file_path: Path, chunk_size: int, split_dir: Path) -> list[Path]:
    if not shutil.which("split"):
        return []
    out_prefix = f"{split_dir / file_path.name}."
    proc = subprocess.run(
        [
            "split",
            "--numeric-suffixes=1",
            "--suffix-length=3",
            f"--bytes={chunk_size}",
            str(file_path),
            out_prefix,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    parts = discover_binary_parts(split_dir, file_path.name)
    return parts if _validate_binary_sequence(parts) else []


def _split_with_python(file_path: Path, chunk_size: int, split_dir: Path) -> list[Path]:
    result: list[Path] = []
    part_number = 1
    with file_path.open("rb") as src:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            out = part_path(split_dir, file_path.name, part_number)
            out.write_bytes(chunk)
            result.append(out)
            part_number += 1
    return result


def discover_binary_parts(split_dir: Path, src_name: str) -> list[Path]:
    parts: dict[int, Path] = {}
    for path in split_dir.iterdir():
        if not path.is_file():
            continue
        match = _NUMERIC_PART.match(path.name)
        if not match or match.group("base") != src_name:
            continue
        parts[int(match.group("num"))] = path
    if not parts:
        return _discover_legacy_parts(split_dir, src_name)
    ordered = [parts[i] for i in sorted(parts)]
    if not _validate_binary_sequence(ordered):
        return []
    return ordered


def _discover_legacy_parts(split_dir: Path, src_name: str) -> list[Path]:
    """Support older ``file.zip.part0`` chunks from previous versions."""
    parts: dict[int, Path] = {}
    for path in split_dir.glob(f"{src_name}.part*"):
        if not path.is_file():
            continue
        match = _LEGACY_PART.match(path.name)
        if not match:
            continue
        parts[int(match.group("num"))] = path
    if not parts:
        return []
    ordered = [parts[i] for i in sorted(parts)]
    if ordered and min(parts) == 0 and sorted(parts) == list(range(len(ordered))):
        return ordered
    return []


def _part_index_binary(path: Path) -> int:
    match = _NUMERIC_PART.match(path.name)
    if match:
        return int(match.group("num")) - 1
    match = _LEGACY_PART.match(path.name)
    if match:
        return int(match.group("num"))
    return -1


def _validate_binary_sequence(parts: list[Path]) -> bool:
    if not parts:
        return False
    indices = [_part_index_binary(p) for p in parts]
    return indices == list(range(len(parts)))


def clear_binary_parts(split_dir: Path, src_name: str) -> None:
    for path in split_dir.iterdir():
        if not path.is_file():
            continue
        match = _NUMERIC_PART.match(path.name)
        if match and match.group("base") == src_name:
            path.unlink(missing_ok=True)
            continue
        if path.name.startswith(f"{src_name}.part"):
            path.unlink(missing_ok=True)


def ffmpeg_part_path(split_dir: Path, src_name: str, part_number: int) -> Path:
    """ffmpeg style: ``movie.part001.mkv``."""
    stem = Path(src_name).stem
    suffix = Path(src_name).suffix
    return split_dir / f"{stem}.part{part_number:03d}{suffix}"


def discover_ffmpeg_parts(split_dir: Path, src_name: str) -> list[Path]:
    stem = Path(src_name).stem
    suffix = Path(src_name).suffix
    parts: dict[int, Path] = {}
    for path in split_dir.iterdir():
        if not path.is_file():
            continue
        match = _FFMPEG_PART.match(path.name)
        if not match or match.group("stem") != stem or match.group("ext") != suffix:
            continue
        parts[int(match.group("num"))] = path
    if not parts:
        return []
    nums = sorted(parts)
    if nums != list(range(1, len(nums) + 1)):
        return []
    return [parts[i] for i in nums]


def _part_index_ffmpeg(path: Path) -> int:
    match = _FFMPEG_PART.match(path.name)
    if not match:
        return -1
    return int(match.group("num")) - 1


def _validate_ffmpeg_sequence(parts: list[Path]) -> bool:
    if not parts:
        return False
    indices = [_part_index_ffmpeg(p) for p in parts]
    return indices == list(range(len(parts)))


def clear_ffmpeg_parts(split_dir: Path, src_name: str) -> None:
    for path in discover_ffmpeg_parts(split_dir, src_name):
        path.unlink(missing_ok=True)


async def ffmpeg_split_video(
    file_path: Path,
    split_dir: Path,
    chunk_size: int,
    *,
    max_part_bytes: int,
    expected_parts: int,
) -> list[Path]:
    """Split streamable video with ffmpeg -c copy."""
    split_dir.mkdir(parents=True, exist_ok=True)
    duration, _, _ = await get_media_info(file_path)
    if duration <= 0:
        return []

    src_name = file_path.name
    split_size = max(chunk_size - FFMPEG_SIZE_MARGIN, 1)
    parts: list[Path] = []
    start_time = 0.0
    part_no = 1
    multi_streams = True
    max_iterations = max(expected_parts, 1) + 8

    for _ in range(max_iterations):
        if part_no > expected_parts and start_time >= max(duration - 4, 0) and parts:
            break

        out_path = ffmpeg_part_path(split_dir, src_name, part_no)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(start_time),
            "-i",
            str(file_path),
            "-fs",
            str(split_size),
            "-map",
            "0",
            "-map_chapters",
            "-1",
            "-async",
            "1",
            "-strict",
            "-2",
            "-c",
            "copy",
            str(out_path),
        ]
        if not multi_streams:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                str(file_path),
                "-fs",
                str(split_size),
                "-async",
                "1",
                "-strict",
                "-2",
                "-c",
                "copy",
                str(out_path),
            ]

        _, stderr, code = await _exec_fftool(cmd, timeout=7200)
        if code != 0:
            if out_path.exists():
                out_path.unlink(missing_ok=True)
            if multi_streams:
                multi_streams = False
                continue
            for part in parts:
                part.unlink(missing_ok=True)
            if stderr.strip():
                print(f"WARNING: ffmpeg split error: {stderr.strip()}")
            return []

        if not out_path.is_file() or out_path.stat().st_size == 0:
            out_path.unlink(missing_ok=True)
            break

        out_size = out_path.stat().st_size
        if out_size > max_part_bytes:
            split_size = max(split_size - (out_size - max_part_bytes) - 5_000_000, 1)
            out_path.unlink(missing_ok=True)
            continue

        part_duration, _, _ = await get_media_info(out_path)
        if part_duration <= 0:
            out_path.unlink(missing_ok=True)
            break

        parts.append(out_path)
        if part_duration >= duration - 1:
            break
        if part_duration <= 3:
            out_path.unlink(missing_ok=True)
            parts.pop()
            break

        start_time += max(part_duration - 3, 1)
        part_no += 1

    return parts


def clear_all_parts(split_dir: Path, src_name: str) -> None:
    clear_binary_parts(split_dir, src_name)
    clear_ffmpeg_parts(split_dir, src_name)


def combine_files(input_parts: list[Path], output_path: Path, chunk_size: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as dest:
        for part in input_parts:
            with part.open("rb") as src:
                while True:
                    data = src.read(chunk_size)
                    if not data:
                        break
                    dest.write(data)


def discover_part_groups(directory: Path) -> dict[str, list[Path]]:
    """Find split part groups for auto-combine (GNU and ffmpeg naming)."""
    groups: dict[str, dict[int, Path]] = {}

    for path in directory.iterdir():
        if not path.is_file():
            continue

        match = _NUMERIC_PART.match(path.name)
        if match:
            base = match.group("base")
            groups.setdefault(base, {})[int(match.group("num"))] = path
            continue

        legacy = _LEGACY_PART.match(path.name)
        if legacy:
            base = legacy.group("base")
            groups.setdefault(base, {})[int(legacy.group("num")) + 1] = path
            continue

        ffmpeg = _FFMPEG_PART.match(path.name)
        if ffmpeg:
            base = f"{ffmpeg.group('stem')}{ffmpeg.group('ext')}"
            groups.setdefault(base, {})[int(ffmpeg.group("num"))] = path

    result: dict[str, list[Path]] = {}
    for base, numbered in groups.items():
        if len(numbered) < 2:
            continue
        nums = sorted(numbered)
        if nums != list(range(1, len(nums) + 1)):
            continue
        result[base] = [numbered[i] for i in nums]
    return result
