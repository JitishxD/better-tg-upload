# Copy this file to config.py and edit (config.py is gitignored).
#
#   cp config_sample.py config.py   # Linux/macOS
#   copy config_sample.py config.py   # Windows
#
# CLI flags always override these values.

# --- Auth / session ---
PROFILE = "myprofile"
API_ID = 0
API_HASH = ""
PHONE = ""
BOT_TOKEN = ""
SESSION_STRING = ""

# --- Workspace ---
WORKSPACE_DIR = ".tg_upload"
# Defaults under WORKSPACE_DIR: sessions/, downloads/, split/, combine/, thumb/, upload_resume/, upload_tree/
# Override individual dirs only if needed:
# SESSION_DIR = ".tg_upload/sessions"
# SPLIT_DIR = ".tg_upload/split"
# COMBINE_DIR = ".tg_upload/combine"
# DL_DIR = ".tg_upload/downloads"
# THUMB_DIR = ".tg_upload/thumb"
# UPLOAD_RESUME_DIR = ".tg_upload/upload_resume"
# UPLOAD_TREE_STATE_DIR = ".tg_upload/upload_tree"

# --- Upload target ---
PATH = ""
CHAT_ID = "me"
CAPTION = ""
CAPJSON = ""
THUMB = ""
THUMB_SEEK = 0  # 0 = middle of video; e.g. 2.5 for frame at 2.5 seconds
FILENAME = ""
PARSE_MODE = "DEFAULT"
DURATION = 0

# --- Upload behaviour ---
EQUAL_SPLITS = False
NO_RESUME = False
KEEP_SPLIT_PARTS = False
RESET_TREE = False
DOCUMENT_ONLY = False
DISABLE_STREAM = False
SLEEP = 1.0
REPLY_TO = 0
SELF_DESTRUCT = 0

# --- Download ---
# Set DL = True to default to download mode (usually leave False; use --dl flag)
DL = False

# --- Client ---
PROXY = ""
IPV6 = False
DEVICE_MODEL = "better-tg-upload"
SYSTEM_VERSION = ""
VERBOSE = False

# --- Utility limits ---
HASH_MEMORY_LIMIT = 1_000_000
COMBINE_MEMORY_LIMIT = 1_000_000
