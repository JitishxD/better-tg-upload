from argparse import Namespace
from json import load
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus"}


def load_caption_template(args: Namespace) -> tuple[str, str | None]:
    if args.capjson:
        config = Path("caption.json")
        if not config.exists():
            raise ValueError("caption.json not found while --capjson is set.")
        with config.open("r", encoding="utf-8") as fp:
            data = load(fp)
        if args.capjson not in data:
            raise ValueError(f"Template not found in caption.json: {args.capjson}")
        template = data[args.capjson]
        return str(template.get("text", "")), str(template.get("mode", "DEFAULT"))
    return str(args.caption or ""), None


def detect_upload_kind(path: Path, args: Namespace) -> str:
    if args.as_photo:
        return "photo"
    if args.as_video:
        return "video"
    if args.as_audio:
        return "audio"
    if args.as_voice:
        return "voice"
    if args.as_video_note:
        return "video_note"

    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "document"


async def resolve_thumbnail(src_path: Path, args: Namespace) -> str | None:
    if not args.thumb:
        return None
    if args.thumb == "none":
        return None
    if args.thumb == "auto":
        return None

    thumb_path = Path(args.thumb)
    if not thumb_path.exists():
        return None
    if thumb_path.suffix.lower() in {".jpg", ".jpeg"}:
        return str(thumb_path)

    with NamedTemporaryFile(prefix="btu_thumb_", suffix=".jpg", delete=False) as tmp:
        tmp_name = tmp.name
    with Image.open(thumb_path) as img:
        img.convert("RGB").save(tmp_name, "JPEG")
    return tmp_name


async def cleanup_temp_file(path: str | None, args: Namespace) -> None:
    if not path:
        return
    if args.thumb and path == str(Path(args.thumb)):
        return
    p = Path(path)
    if p.exists() and (
        p.name.startswith("btu_thumb_")
        or p.name.startswith("btu_vthumb_")
        or p.name.startswith("btu_athumb_")
    ):
        p.unlink()
