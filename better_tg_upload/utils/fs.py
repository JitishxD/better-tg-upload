from argparse import Namespace
from collections.abc import Awaitable, Callable
from hashlib import md5, sha256
from pathlib import Path
from typing import Iterator


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def iter_input_files(path: Path, recursive: bool) -> Iterator[Path]:
    if path.is_file():
        yield path
        return
    try:
        from natsort import natsorted
    except ImportError:
        natsorted = sorted  # type: ignore[assignment]
    if recursive:
        yield from natsorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: str(p))
    else:
        yield from natsorted((p for p in path.glob("*") if p.is_file()), key=lambda p: str(p))


def _truncate_filename(name: str, max_length: int = 60) -> str:
    """Truncate filename to max_length chars while preserving the extension.

    Split name and extension, then truncate the name part so name + extension fits within max_length.
    """
    if len(name) <= max_length:
        return name
    import os.path
    base, ext = os.path.splitext(name)
    ext_len = len(ext)
    if ext_len >= max_length:
        return name[:max_length]
    remain = max_length - ext_len
    base = base[:remain]
    return f"{base}{ext}"


def apply_name_mutations(file_name: str, args: Namespace) -> str:
    result = file_name
    if args.filename:
        result = args.filename
    if args.prefix:
        result = f"{args.prefix}{result}"
    if args.replace and len(args.replace) == 2:
        result = result.replace(args.replace[0], args.replace[1])
    result = _truncate_filename(result)
    return result


def file_hashes(path: Path, chunk_size: int) -> tuple[str, str]:
    h1 = sha256()
    h2 = md5()
    with path.open("rb") as fp:
        while True:
            data = fp.read(chunk_size)
            if not data:
                break
            h1.update(data)
            h2.update(data)
    return h1.hexdigest(), h2.hexdigest()


def build_caption(path: Path, template: str, args: Namespace) -> str:
    if not template:
        return ""
    size = path.stat().st_size
    h_sha, h_md5 = file_hashes(path, max(int(args.hash_memory_limit), 1))
    return template.format(
        file_name=path.stem,
        file_format=path.suffix,
        file_size_b=size,
        file_size_kb=size / 1024,
        file_size_mb=size / (1024 * 1024),
        file_size_gb=size / (1024 * 1024 * 1024),
        file_sha256=h_sha,
        file_md5=h_md5,
        path=path,
    )
