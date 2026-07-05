# Global config for better-tg-upload (created by `better-tg-upload init`).
# Default location: ~/.better-tg-upload/config.py
#
# CLI flags always override these values.
# Run `better-tg-upload --env` to inspect resolved settings.

# --- workspace ---
# All runtime data (sessions, downloads, split, …) lives under this folder.
WORKSPACE_DIR = "~/.better-tg-upload/.tg_upload"
# path_overrides — uncomment only when a subfolder should differ from WORKSPACE_DIR:
# SESSION_DIR = "/custom/sessions"
# SPLIT_DIR = "/custom/split"
# COMBINE_DIR = "/custom/combine"
# DL_DIR = "/custom/downloads"
# THUMB_DIR = "/custom/thumb"
# UPLOAD_RESUME_DIR = "/custom/upload_resume"
# UPLOAD_TREE_STATE_DIR = "/custom/upload_tree"

# --- auth ---
PROFILE = "myprofile"
API_ID = 0
API_HASH = ""
PHONE = ""
BOT_TOKEN = ""
SESSION_STRING = ""

# --- target ---
PATH = ""
CHAT_ID = "me"
CAPTION = ""
CAPJSON = ""
FILENAME = ""
THUMB = ""
THUMB_SEEK = 0  # 0 = middle of video; e.g. 2.5 for frame at 2.5 seconds
DURATION = 0
PARSE_MODE = "DEFAULT"
REPLY_TO = 0
SELF_DESTRUCT = 0

# --- upload ---
EQUAL_SPLITS = False
NO_RESUME = False
KEEP_SPLIT_PARTS = False
DOCUMENT_ONLY = False
DISABLE_STREAM = False
RESET_TREE = False
SLEEP = 1.0

# --- download ---
# Set DL = True to default to download mode (usually leave False; use --dl flag)
DL = False

# --- client ---
PROXY = ""
IPV6 = False
DEVICE_MODEL = "better-tg-upload"
SYSTEM_VERSION = ""
VERBOSE = False

# --- limits ---
HASH_MEMORY_LIMIT = 1_000_000
COMBINE_MEMORY_LIMIT = 1_000_000
