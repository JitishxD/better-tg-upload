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
SESSION_DIR = ".sessions_tg_upload"

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

# --- Paths ---
SPLIT_DIR = "split_tg_upload"
COMBINE_DIR = "combine_tg_upload"
DL_DIR = "downloads_tg_upload"
THUMB_DIR = "thumb_tg_upload"

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
