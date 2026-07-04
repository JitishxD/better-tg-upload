from argparse import ArgumentParser
from pathlib import Path
from sys import version_info

from .. import __version__
from ..core.config import (
    COMBINE_DIR,
    DOWNLOADS_DIR,
    SESSIONS_DIR,
    SPLIT_DIR,
    THUMB_DIR,
    UPLOAD_TREE_STATE_DIR,
    cfg_bool,
    cfg_float,
    cfg_int,
    cfg_str,
    default_system_version,
)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="better-tg-upload",
        description="CLI to upload/download files to Telegram using MTProto.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"better-tg-upload {__version__} (python {version_info.major}.{version_info.minor}.{version_info.micro})",
    )

    # Connectivity
    parser.add_argument(
        "--ipv6",
        default=cfg_bool("IPV6", False),
        action="store_true",
        help="Connect using IPv6.",
    )
    parser.add_argument(
        "--proxy",
        default=cfg_str("PROXY"),
        help="Proxy name in proxy.json.",
    )

    # Login
    parser.add_argument(
        "-p",
        "--profile",
        default=cfg_str("PROFILE"),
        help="Session profile name.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show account info JSON.",
    )
    parser.add_argument(
        "--api_id",
        default=cfg_int("API_ID", 0),
        type=int,
        help="Telegram API ID.",
    )
    parser.add_argument(
        "--api_hash",
        default=cfg_str("API_HASH"),
        help="Telegram API hash.",
    )
    parser.add_argument(
        "--phone",
        default=cfg_str("PHONE"),
        help="Phone number for user auth.",
    )
    parser.add_argument(
        "--hide_pswd",
        action="store_true",
        help="Hide password prompt where supported.",
    )
    parser.add_argument(
        "--bot",
        default=cfg_str("BOT_TOKEN"),
        help="Bot token.",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Terminate current session.",
    )
    parser.add_argument(
        "--login_string",
        default=cfg_str("SESSION_STRING"),
        help="Use session string login.",
    )
    parser.add_argument(
        "--export_string",
        action="store_true",
        help="Export current session as session string.",
    )
    parser.add_argument(
        "--tmp_session",
        action="store_true",
        help="Do not persist session file.",
    )
    parser.add_argument(
        "--login_only",
        action="store_true",
        help="Only perform auth and exit.",
    )

    # File
    parser.add_argument(
        "-l",
        "--path",
        default=cfg_str("PATH"),
        help="File/folder path to upload.",
    )
    parser.add_argument(
        "-n",
        "--filename",
        default=cfg_str("FILENAME"),
        help="Custom output filename.",
    )
    parser.add_argument(
        "-i",
        "--thumb",
        default=cfg_str("THUMB"),
        help="Thumbnail path or 'auto'.",
    )
    parser.add_argument(
        "--thumb_seek",
        default=cfg_float("THUMB_SEEK", 0.0),
        type=float,
        help="Video thumbnail frame time in seconds (0 = middle of video).",
    )
    parser.add_argument(
        "-z",
        "--caption",
        default=cfg_str("CAPTION", ""),
        help="Caption text.",
    )
    parser.add_argument(
        "--duration",
        default=cfg_int("DURATION", 0),
        type=int,
        help="Duration for audio/video.",
    )
    parser.add_argument(
        "--capjson",
        default=cfg_str("CAPJSON"),
        help="Template key from caption.json.",
    )

    # Behaviour
    parser.add_argument(
        "-c",
        "--chat_id",
        default=cfg_str("CHAT_ID"),
        help="Target/source chat id/username.",
    )
    parser.add_argument("--as_photo", action="store_true", help="Send as photo.")
    parser.add_argument("--as_video", action="store_true", help="Send as video.")
    parser.add_argument("--as_audio", action="store_true", help="Send as audio.")
    parser.add_argument("--as_voice", action="store_true", help="Send as voice.")
    parser.add_argument(
        "--as_video_note", action="store_true", help="Send as video note."
    )
    parser.add_argument(
        "--equal_splits",
        default=cfg_bool("EQUAL_SPLITS", False),
        action="store_true",
        help="Split oversized files into equal-sized parts when possible.",
    )
    parser.add_argument(
        "--no_resume",
        default=cfg_bool("NO_RESUME", False),
        action="store_true",
        help="Do not resume interrupted split uploads.",
    )
    parser.add_argument(
        "--keep_split_parts",
        default=cfg_bool("KEEP_SPLIT_PARTS", False),
        action="store_true",
        help="Keep local split part files after successful upload.",
    )
    parser.add_argument(
        "--replace",
        nargs=2,
        default=None,
        metavar=("FROM", "TO"),
        help="Replace text in file names.",
    )
    parser.add_argument(
        "--reply_to",
        default=cfg_int("REPLY_TO", 0),
        type=int,
        help="Reply-to message id.",
    )
    parser.add_argument(
        "--disable_stream",
        default=cfg_bool("DISABLE_STREAM", False),
        action="store_true",
        help="Disable streaming for video.",
    )
    parser.add_argument("-b", "--spoiler", action="store_true", help="Media spoiler.")
    parser.add_argument(
        "-y",
        "--self_destruct",
        default=cfg_int("SELF_DESTRUCT", 0),
        type=int,
        help="TTL seconds for self-destruct where supported.",
    )
    parser.add_argument("--protect", action="store_true", help="Protect content.")
    parser.add_argument(
        "--parse_mode",
        default=cfg_str("PARSE_MODE", "DEFAULT"),
        help="DEFAULT/HTML/MARKDOWN/DISABLED",
    )
    parser.add_argument(
        "-d",
        "--delete_on_done",
        action="store_true",
        help="Delete source files after success.",
    )
    parser.add_argument("--width", default=0, type=int, help="Video width override.")
    parser.add_argument("--height", default=0, type=int, help="Video height override.")
    parser.add_argument("-a", "--artist", default=None, help="Audio artist.")
    parser.add_argument("-t", "--title", default=None, help="Audio title.")
    parser.add_argument("-s", "--silent", action="store_true", help="Silent send.")
    parser.add_argument(
        "--tree_state",
        type=Path,
        default=None,
        help=f"Folder upload resume JSON (default: {UPLOAD_TREE_STATE_DIR}/<folder>_<hash>.json).",
    )
    parser.add_argument(
        "--reset_tree",
        default=cfg_bool("RESET_TREE", False),
        action="store_true",
        help="Delete folder upload resume state and start from scratch.",
    )
    parser.add_argument(
        "--document_only",
        default=cfg_bool("DOCUMENT_ONLY", False),
        action="store_true",
        help="Send every file as a document (skip photo/video/audio detection).",
    )
    parser.add_argument(
        "--sleep",
        default=cfg_float("SLEEP", 1.0),
        type=float,
        help="Seconds to wait between uploads (default: 1).",
    )
    parser.add_argument("--prefix", default=None, help="Filename prefix.")
    parser.add_argument(
        "--hash_memory_limit",
        default=cfg_int("HASH_MEMORY_LIMIT", 1_000_000),
        type=int,
    )
    parser.add_argument(
        "--combine_memory_limit",
        default=cfg_int("COMBINE_MEMORY_LIMIT", 1_000_000),
        type=int,
    )
    parser.add_argument("--split_dir", default=cfg_str("SPLIT_DIR", SPLIT_DIR))
    parser.add_argument(
        "--combine_dir", default=cfg_str("COMBINE_DIR", COMBINE_DIR)
    )
    parser.add_argument("--thumb_dir", default=cfg_str("THUMB_DIR", THUMB_DIR))
    parser.add_argument("--no_update", action="store_true")

    # Download
    parser.add_argument("--dl", action="store_true", help="Enable download mode.")
    parser.add_argument(
        "--links",
        nargs="*",
        default=[],
        help="Telegram message links to download.",
    )
    parser.add_argument("--txt_file", default=None, help="Text file with links.")
    parser.add_argument(
        "-j", "--auto_combine", action="store_true", help="Auto combine part files."
    )
    parser.add_argument(
        "--range",
        dest="range_mode",
        action="store_true",
        help="Download range between two links/IDs.",
    )
    parser.add_argument(
        "--msg_id", nargs="*", type=int, default=[], help="Message IDs to download."
    )
    parser.add_argument(
        "--dl_dir", default=cfg_str("DL_DIR", DOWNLOADS_DIR), help="DL dir."
    )

    # Utility
    parser.add_argument("--env", action="store_true", help="Show resolved config values.")
    parser.add_argument("--file_info", default=None, help="Show file info and exit.")
    parser.add_argument("--hash", dest="hash_file", default=None, help="Compute hashes.")
    parser.add_argument(
        "--split_file", type=int, default=0, help="Split --path and exit (bytes)."
    )
    parser.add_argument(
        "--combine",
        nargs="*",
        default=[],
        help="Combine part files and exit.",
    )
    parser.add_argument(
        "--frame",
        type=int,
        default=None,
        help="Capture video frame at second and exit.",
    )
    parser.add_argument("--convert", default=None, help="Convert image to JPEG and exit.")

    # Misc
    parser.add_argument(
        "--device_model",
        default=cfg_str("DEVICE_MODEL", "better-tg-upload"),
    )
    parser.add_argument(
        "--system_version",
        default=default_system_version(),
    )
    parser.add_argument(
        "--session_dir",
        default=cfg_str("SESSION_DIR", SESSIONS_DIR),
        help="Directory for session files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=cfg_bool("VERBOSE", False),
        help="Enable verbose/debug logging.",
    )

    return parser
