# Copy this file to config.py and edit (config.py is gitignored).
#
#   cp config_sample.py config.py   # Linux/macOS
#   copy config_sample.py config.py   # Windows
#
# CLI flags always override these values.
# Run `better-tg-upload --env` to inspect resolved settings.

# --- workspace ---
WORKSPACE_DIR = ".tg_upload"
# path_overrides — uncomment only when a path should differ from WORKSPACE_DIR layout:
# SESSION_DIR = ".tg_upload/sessions"
# SPLIT_DIR = ".tg_upload/split"
# COMBINE_DIR = ".tg_upload/combine"
# DL_DIR = ".tg_upload/downloads"
# THUMB_DIR = ".tg_upload/thumb"
# UPLOAD_RESUME_DIR = ".tg_upload/upload_resume"
# UPLOAD_TREE_STATE_DIR = ".tg_upload/upload_tree"

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

# --- Utility limits ---
HASH_MEMORY_LIMIT = 1_000_000
COMBINE_MEMORY_LIMIT = 1_000_000
