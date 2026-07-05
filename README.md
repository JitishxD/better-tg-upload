# better-tg-upload

A convenient CLI tool to upload and download files to/from Telegram directly from the command line using MTProto.


## **📑 INDEX**

* [**📋 Requirements**](#requirements)
  * [Installing ffmpeg](#installing-ffmpeg)
* [**📦 Installation**](#installation)
* [**⚙️ Configuration (setup once)**](#configuration-setup-once)
* [**🚀 Quick Start**](#quick-start)
  * [Login (first time)](#login)
  * [Upload](#upload)
    * [Captions](#captions)
    * [Single file](#single-file)
    * [Folder upload](#folder-upload)
    * [Large files (auto-split)](#large-files-auto-split)
    * [Resume / temp files](#upload-resume-temp-files)
    * [Saved Messages](#saved-messages)
  * [Download](#download)
  * [Utilities](#utilities)
  * [Session Management](#session-management)
* [**📁 Large file uploads**](#large-file-uploads)
  * [How it works](#large-file-how-it-works)
  * [Split methods](#split-methods)
  * [Split modes](#split-modes)
  * [Resume and temp files](#large-file-resume-temp-files)
* [**⬆️ Upload Options**](#upload-options)
* [**⬇️ Download Options**](#download-options)
* [**📝 Caption template variables**](#caption-template-variables)
* [**🔧 Configuration reference**](#configuration-reference)
  * [`config.py`](#config-py)
  * [`proxy.json`](#proxy-json)
  * [`caption.json`](#caption-json)
* [**🔗 Supported link formats**](#supported-link-formats)
* [**✂️ Split file naming**](#split-file-naming)
* [**🛠️ Troubleshooting**](#troubleshooting)
* [**❤️ Credits**](#credits)
* [**📄 License**](#license)

## Requirements

| Requirement | Notes |
|-------------|-------|
| **Python 3.10+** | Tested on 3.12 |
| **ffmpeg / ffprobe** | Thumbnails, media detection, **video split** (`-c copy`), frame capture |
| **GNU split** (optional) | On Linux/macOS, archive splitting uses `split` when available; Python fallback otherwise |
| **Telegram API credentials** | `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org) |

<a id="installing-ffmpeg"></a>

### Installing ffmpeg

**Windows (winget):**
```powershell
winget install Gyan.FFmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

Verify:
```bash
ffmpeg -version
ffprobe -version
```

## Installation

### Install from GitHub (pip)

Usable when launched as a Python module:

```bash
python -m pip install git+https://github.com/JitishxD/better-tg-upload.git
```

### Install from a local clone (development)

```bash
git clone https://github.com/JitishxD/better-tg-upload.git
cd better-tg-upload

# Create a virtual environment (recommended)
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install .

# Editable install while hacking on the code
pip install -e .
```

### Updating

Update according to your install method:

**From GitHub (pip):**

```bash
python -m pip install --force-reinstall git+https://github.com/JitishxD/better-tg-upload.git
```

**From local clone:**

```bash
cd better-tg-upload
git pull
pip install .
```

For an editable clone, `pip install -e .` again after `git pull` is enough.

### Run

After installation, the `better-tg-upload` command is available:

```bash
better-tg-upload --version
```

Or as a module:

```bash
python -m better_tg_upload --help
```

## Configuration (setup once)

```bash
better-tg-upload --init
```

This creates:

```
~/.better-tg-upload/
├── config.py
├── proxy.json          # optional, add when using --proxy
├── caption.json        # optional, add when using --capjson
└── .tg_upload/
    ├── sessions/
    ├── downloads/
    ├── split/
    ├── combine/
    ├── thumb/
    ├── upload_resume/
    └── upload_tree/
```

On Windows, `~` is your user profile folder (e.g. `C:\Users\you\.better-tg-upload`).

Edit `~/.better-tg-upload/config.py` — minimum for daily use:

```python
PROFILE = "myprofile"
API_ID = 12345678          # from https://my.telegram.org
API_HASH = "your_api_hash"
PHONE = "+1234567890"      # first login only
CHAT_ID = "-1001234567890" # default upload target (or @channel)
# WORKSPACE_DIR = "D:/telegram-data/.tg_upload"  # optional; default ~/.better-tg-upload/.tg_upload
```

Run from **any directory** after setup. Optional overrides:

| Flag | Purpose |
|------|---------|
| `--config PATH` | Use a different config file |
| `--workspace PATH` | Use a different data directory |

**Priority for reading variable** (highest wins):

1. CLI flags (`-p`, `-l`, `-c`, …)
2. `config.py`
3. Built-in defaults

If a required setting is still missing, the CLI reports it

Check what is active:

```bash
better-tg-upload --env
```

See [Configuration reference](#configuration-reference) for all keys.

## Quick Start

<a id="login"></a>

### 1. Login (first time)

Put `API_ID` and `API_HASH` in `~/.better-tg-upload/config.py`, then:

```bash
# User account — prompted for OTP
better-tg-upload -p myprofile --login_only

# Or pass everything on the CLI (no config.py)
better-tg-upload --profile myprofile --api_id 12345 --api_hash abc123 --phone +1234567890 --login_only

# Bot login
better-tg-upload --profile mybot --api_id 12345 --api_hash abc123 --bot "123456:ABCdefGHI" --login_only

# Session string (no OTP prompt)
better-tg-upload --profile myprofile --login_string "BQC..." --login_only
```

Sessions and all runtime data live under **`~/.better-tg-upload/.tg_upload/`** (override with `--workspace` or `WORKSPACE_DIR` in `config.py`):

```
~/.better-tg-upload/.tg_upload/
├── sessions/        # Telegram session files
├── downloads/       # --dl output
├── split/           # local split parts
├── combine/         # offline --combine output
├── thumb/           # temp thumbnails
├── upload_resume/   # split upload progress
└── upload_tree/     # folder upload progress
```

Sessions are stored in `~/.better-tg-upload/.tg_upload/sessions/` by default.

### Private channels and numeric IDs

- You can target private channels/supergroups directly with numeric IDs like `-1001234567890`.
- In PowerShell, quote negative IDs so they are not parsed as CLI flags.

```powershell
better-tg-upload -p myprofile -l file.zip -c "-1001234567890"
```

- The account in `--profile` must already be a member/admin of that chat.
- `chat_id` values starting with `100...` are normalized to `-100...` internally for PowerShell compatibility.

<a id="upload"></a>

### 2. Upload

`-l` / `--path` is **what to upload** — a file or a folder.

| `--path` | What happens |
|----------|----------------|
| **File** | Upload one file (media auto-detection, large-file split) |
| **Folder** | Walk the tree: post each **subfolder name** as a text message, then upload files inside |

<a id="captions"></a>

#### Captions

- **Default:** the **filename** is used as the message caption (e.g. `lecture01.mp4`).
- **Custom:** pass `-z "..."` or use `--capjson` with `caption.json` (see [Caption templates](#caption-template-variables)).
- **Split parts:** caption is `<code>file.zip.001</code>` (HTML).

<a id="single-file"></a>

#### Single file

```bash
better-tg-upload -p myprofile -l video.mp4 -c @mychannel
better-tg-upload -p myprofile -l photo.png -c @mychannel --as_photo
better-tg-upload -p myprofile -l song.mp3 -c @mychannel --as_audio --artist "Artist" --title "Song"
better-tg-upload -p myprofile -l file.zip -c @mychannel -z "Size: {file_size_mb:.2f} MB"
```

<a id="folder-upload"></a>

#### Folder upload (course, archive, project tree)

Your disk:

```
folder/
├── chapter1/
│   ├── intro.mp4
│   └── notes.pdf
└── chapter2/
    └── lab.zip
```

Telegram channel after upload:

```
chapter1          ← text message (folder name)
intro.mp4         ← caption: intro.mp4
notes.pdf         ← caption: notes.pdf
chapter2
lab.zip           ← caption: lab.zip
```

**Examples:**

```powershell
# With config.py (PROFILE + CHAT_ID already set)
python -m better_tg_upload -l .\folder\

# Full CLI
python -m better_tg_upload -p myprofile -l .\folder\ -c "-1004486493608"

# Resume after Ctrl+C — same command again
python -m better_tg_upload -l .\folder\

# Start over (delete folder resume state)
python -m better_tg_upload -l .\folder\ --reset_tree

# Skip ffprobe — send everything as documents
python -m better_tg_upload -l .\folder\ --document_only

# Verbose logging
python -m better_tg_upload -l .\folder\ -v
```

<a id="large-files-auto-split"></a>

#### Large files (auto-split)

When a file exceeds your account limit (**2 GB** standard / **4 GB** premium), it is split and each part is uploaded as its own message:

```bash
better-tg-upload -p myprofile -l huge.mkv -c @mychannel
better-tg-upload -p myprofile -l huge.zip -c @mychannel --equal_splits
```

Re-run the same command to resume an interrupted split upload.

<a id="upload-resume-temp-files"></a>

#### Resume / temp files

| Path | Used for |
|------|----------|
| `~/.better-tg-upload/.tg_upload/upload_tree/<folder>_<hash>.json` | Folder upload progress |
| `~/.better-tg-upload/.tg_upload/upload_resume/` | Single-file split upload progress |
| `~/.better-tg-upload/.tg_upload/split/<hash>/` | Local split part files on disk |

Flags: `--no_resume`, `--reset_tree`, `--keep_split_parts`.

<a id="saved-messages"></a>

#### Saved Messages

```bash
better-tg-upload -p myprofile -l file.txt
# default chat is "me" when -c is omitted (me is the saved_messages chat of user)
```

<a id="download"></a>

### 3. Download

```bash
# Download by link
better-tg-upload -p myprofile --dl --links https://t.me/channel/123

# Download multiple links
better-tg-upload -p myprofile --dl --links https://t.me/channel/100 https://t.me/channel/101

# Download range (all messages between two links)
better-tg-upload -p myprofile --dl --links https://t.me/channel/100 https://t.me/channel/200 --range

# Download by message ID
better-tg-upload -p myprofile --dl --chat_id @mychannel --msg_id 100 101 102

# Download from text file of links (one per line)
better-tg-upload -p myprofile --dl --txt_file links.txt

# Download and auto-combine split parts (file.zip.001, movie.part001.mkv, …)
better-tg-upload -p myprofile --dl --links https://t.me/c/123/100 https://t.me/c/123/105 --range --auto_combine

# Custom download directory
better-tg-upload -p myprofile --dl --links https://t.me/channel/123 --dl_dir ./my_downloads
```

Files save to **`~/.better-tg-upload/.tg_upload/downloads/`** by default (or `--dl_dir` / `DL_DIR`). The CLI prints the full path:

```
Download directory: C:\Users\you\.better-tg-upload\.tg_upload\downloads
Saved -> C:\Users\you\.better-tg-upload\.tg_upload\downloads\dummy.bin.001
```

With **`--auto_combine`**, split parts (`.001`, `.002`, …) merge into the base filename in the same folder, then parts are deleted.

<a id="utilities"></a>

### 4. Utilities (no Telegram connection needed)

```bash
# Initialize config + workspace
better-tg-upload --init

# Compute file hashes
better-tg-upload --hash myfile.zip

# Show file info
better-tg-upload --file_info myfile.zip

# Split a file offline (creates bigfile.zip.001, bigfile.zip.002, …)
better-tg-upload -l bigfile.zip --split_file 2000000000

# Combine split parts offline
better-tg-upload --combine bigfile.zip.001 bigfile.zip.002 bigfile.zip.003

# Convert image to JPEG
better-tg-upload --convert image.png

# Capture video frame at 30 seconds
better-tg-upload --frame 30 -l video.mp4

# Show current config / env mapping
better-tg-upload --env
```

<a id="session-management"></a>

### 5. Session Management

```bash
# Export session string (for use on other machines)
better-tg-upload -p myprofile --export_string

# Show account info
better-tg-upload -p myprofile --info

# Logout / terminate session
better-tg-upload -p myprofile --logout
```

## Large file uploads

<a id="large-file-how-it-works"></a>

### How it works

1. **Detect account limit** — `get_me().is_premium` → **2 GB** (standard) or **4 GB** (premium).
2. **Compare file size** — if the file is **under** the limit, upload normally (video/photo/audio/document).
3. **If over the limit** — split, then upload **each part as its own message** with caption `<code>part-filename</code>` and a progress bar.

<a id="split-methods"></a>

### Split methods

| File type | Tool | Part names on disk |
|-----------|------|-------------------|
| **Video** (mp4, mkv, …) | ffmpeg `-c copy` | `movie.part001.mkv`, `movie.part002.mkv` |
| **Archives & other** (zip, rar, …) | GNU `split` or Python | `archive.zip.001`, `archive.zip.002` |

If ffmpeg split fails for a video, the tool falls back to GNU/binary split (`movie.mkv.001`, …). Those parts are **not** individually streamable.

<a id="split-modes"></a>

### Split modes

| Mode | Flag | Behavior |
|------|------|----------|
| **Fixed** (default) | — | Each part ≤ account limit (with a small safety margin). Last part may be smaller. |
| **Equal** | `--equal_splits` | Same number of parts as fixed mode, but sizes are as equal as possible. |

<a id="large-file-resume-temp-files"></a>

### Resume and temp files

| Path | Purpose |
|------|---------|
| `~/.better-tg-upload/.tg_upload/split/<hash>/` | Local split parts |
| `~/.better-tg-upload/.tg_upload/upload_resume/` | JSON progress (next part to upload) |

Re-run the **same command** after Ctrl+C or a disconnect to continue. Use `--no_resume` to ignore saved progress, or `--keep_split_parts` to keep local parts after success.

## Global Options

| Flag | Description |
|------|-------------|
| `--init` | Create `~/.better-tg-upload/` (config + workspace) |
| `--force` | With `--init`, overwrite an existing `config.py` |
| `--config PATH` | Config file (default: `~/.better-tg-upload/config.py`) |
| `--workspace PATH` | Data directory (default: `~/.better-tg-upload/.tg_upload`) |
| `--env` | Show resolved config (JSON) |

## Upload Options

| Flag | Short | Description |
|------|-------|-------------|
| `--path` | `-l` | File or folder to upload (folder → tree walk with subfolder messages) |
| `--filename` | `-n` | Custom output filename |
| `--thumb` | `-i` | Thumbnail path or `auto` |
| `--thumb_seek` | | Auto video thumb seek time in seconds (default: `0` = middle of video) |
| `--caption` | `-z` | Caption template (empty = filename as caption) |
| `--chat_id` | `-c` | Target chat ID or username (default: `me`) |
| `--profile` | `-p` | Session profile name |
| `--as_photo` | | Send as photo |
| `--as_video` | | Send as video |
| `--as_audio` | | Send as audio |
| `--as_voice` | | Send as voice message |
| `--as_video_note` | | Send as video note (round video) |
| `--equal_splits` | | Split oversized files into equal-sized parts |
| `--split_dir` | | Local split parts directory (default: under workspace `split/`) |
| `--no_resume` | | Do not resume interrupted uploads |
| `--keep_split_parts` | | Keep local split part files after success |
| `--tree_state` | | Folder resume JSON path |
| `--reset_tree` | | Delete folder upload resume state |
| `--document_only` | | Send every file as a document |
| `--sleep` | | Seconds between uploads (default: `1`) |
| `--silent` | `-s` | Send without notification |
| `--spoiler` | `-b` | Media spoiler |
| `--protect` | | Protect content from forwarding |
| `--delete_on_done` | `-d` | Delete source files after success |
| `--reply_to` | | Reply to message ID |
| `--prefix` | | Add prefix to filenames |
| `--replace` | | Replace text in filenames (`--replace FROM TO`) |
| `--disable_stream` | | Disable streaming for video |
| `--parse_mode` | | `DEFAULT` / `HTML` / `MARKDOWN` / `DISABLED` |
| `--capjson` | | Caption template key from `caption.json` |
| `--verbose` | `-v` | Enable debug logging |

## Download Options

| Flag | Short | Description |
|------|-------|-------------|
| `--dl` | | Enable download mode |
| `--links` | | Telegram message links |
| `--txt_file` | | Text file containing links (one per line) |
| `--msg_id` | | Message IDs to download |
| `--range` | | Download all messages between first and last link/ID |
| `--auto_combine` | `-j` | Auto-combine split parts after download |
| `--dl_dir` | | Download directory (default: under workspace `downloads/`) |
| `--chat_id` | `-c` | Source chat for `--msg_id` downloads |

## Caption template variables

Use in `-z` / `--caption` or in `caption.json` (when set, replaces default filename caption):

| Variable | Description |
|----------|-------------|
| `{file_name}` | File name without extension |
| `{file_format}` | File extension |
| `{file_size_b}` | File size in bytes |
| `{file_size_kb}` | File size in KB |
| `{file_size_mb}` | File size in MB |
| `{file_size_gb}` | File size in GB |
| `{file_sha256}` | SHA-256 hash |
| `{file_md5}` | MD5 hash |
| `{path}` | Full file path |

## Complete Configuration reference

<a id="config-py"></a>

### `config.py` (recommended)

Created by `better-tg-upload --init` at `~/.better-tg-upload/config.py`. All keys:

| Key | CLI flag | Description |
|-----|----------|-------------|
| `PROFILE` | `-p` | Session profile name |
| `API_ID` | `--api_id` | Telegram API ID |
| `API_HASH` | `--api_hash` | Telegram API hash |
| `PHONE` | `--phone` | Phone for user login |
| `BOT_TOKEN` | `--bot` | Bot token |
| `SESSION_STRING` | `--login_string` | Session string login |
| `WORKSPACE_DIR` | `--workspace` | Data directory; subfolders (`sessions/`, `downloads/`, …) are created under it |
| `SESSION_DIR` | `--session_dir` | Session files (default: `{WORKSPACE_DIR}/sessions`) |
| `PATH` | `-l` | Default upload path |
| `CHAT_ID` | `-c` | Default target chat |
| `CAPTION` | `-z` | Caption template (empty = use filename) |
| `CAPJSON` | `--capjson` | Key from `caption.json` |
| `THUMB` | `-i` | Thumbnail path or `auto` |
| `THUMB_SEEK` | `--thumb_seek` | Auto video thumb seek time in seconds (default: `0` = middle of video) |
| `FILENAME` | `-n` | Custom output filename |
| `PARSE_MODE` | `--parse_mode` | `DEFAULT` / `HTML` / `MARKDOWN` / `DISABLED` |
| `EQUAL_SPLITS` | `--equal_splits` | Equal-sized split parts |
| `NO_RESUME` | `--no_resume` | Disable resume |
| `KEEP_SPLIT_PARTS` | `--keep_split_parts` | Keep local parts after upload |
| `RESET_TREE` | `--reset_tree` | Clear folder upload state |
| `DOCUMENT_ONLY` | `--document_only` | Force document uploads |
| `SLEEP` | `--sleep` | Seconds between uploads |
| `SPLIT_DIR` | `--split_dir` | Split parts (default under workspace `split/`) |
| `COMBINE_DIR` | `--combine_dir` | Offline combine output (default under workspace `combine/`) |
| `DL_DIR` | `--dl_dir` | Download directory (default under workspace `downloads/`) |
| `THUMB_DIR` | `--thumb_dir` | Temp thumbnails (default under workspace `thumb/`) |
| `UPLOAD_RESUME_DIR` | | Split upload resume JSON (default under workspace `upload_resume/`) |
| `UPLOAD_TREE_STATE_DIR` | | Folder upload resume JSON (default under workspace `upload_tree/`) |
| `PROXY` | `--proxy` | Proxy name from `proxy.json` |
| `VERBOSE` | `-v` | Debug logging |

**Minimal `config.py`:**

```python
PROFILE = "myprofile"
API_ID = 12345678
API_HASH = "abcdef0123456789abcdef0123456789"
CHAT_ID = "-1004486493608"
```

```powershell
python -m better_tg_upload -l .\folder\
```

<a id="proxy-json"></a>

### `proxy.json`

Place in `~/.better-tg-upload/proxy.json`.

```json
{
  "myproxy": {
    "scheme": "socks5",
    "hostname": "127.0.0.1",
    "port": 1080,
    "username": "user",
    "password": "pass"
  }
}
```

```bash
better-tg-upload -p myprofile --proxy myproxy -l file.zip -c @channel
```

<a id="caption-json"></a>

### `caption.json`

Place in `~/.better-tg-upload/caption.json`.

```json
{
  "my_template": {
    "text": "**{file_name}**\nSize: {file_size_mb:.2f} MB",
    "mode": "MARKDOWN"
  }
}
```

```bash
better-tg-upload -p myprofile -l file.zip -c @channel --capjson my_template
```

## Supported link formats

| Format | Example |
|--------|---------|
| Public channel/group | `https://t.me/channel/123` |
| Private channel/supergroup | `https://t.me/c/1234567890/123` |
| Message range in URL | `https://t.me/channel/100-200` |
| Private message | `tg://openmessage?user_id=123&message_id=456` |
| Private channel post | `tg://privatepost?channel=1234567890&post=123` |

## Split file naming

**Archives and non-video files** (GNU — suffix after the full filename):

```
myfile.zip.001
myfile.zip.002
myfile.zip.003
```

**Video files** (ffmpeg):

```
myvideo.part001.mkv
myvideo.part002.mkv
```

Legacy `myfile.zip.part0` parts from older versions are still recognized for combine/resume.

`--auto_combine` (download) scans for `.001`, `.002`, … groups and `*.part001.*` ffmpeg groups, merges them into the base filename, and deletes the parts.

## Troubleshooting

### 1. `Kurigram is required`

```bash
pip install kurigram tgcrypto
```

### 2. `unable to open database file` on login

Pyrogram stores sessions as `{session_dir}/{profile}.session`. Pass only the profile name via `--profile`; do not embed the session directory in the profile name.

Ensure the session directory exists and is writable (default: `~/.better-tg-upload/.tg_upload/sessions/`):

```bash
better-tg-upload --init
better-tg-upload -p myprofile --api_id ... --api_hash ... --phone ... --login_only
# creates ~/.better-tg-upload/.tg_upload/sessions/myprofile.session
```

### 3. `PROFILE is missing`

Run `better-tg-upload --init`, set `PROFILE` in `config.py`, or pass `-p` / `--profile`.

### 4. `API_ID` / `API_HASH` is missing

Required on first login when no session file exists yet. Run `better-tg-upload --init`, set them in `config.py`, or pass `--api_id` and `--api_hash`.

### 5. `PATH is missing`

Set `PATH` in `config.py` or pass `-l` / `--path`.

### 6. `CHAT_ID` is missing

Set `CHAT_ID` in `config.py` (e.g. `CHAT_ID = "me"`) or pass `-c` / `--chat_id`.

### 7. `Invalid Telegram link format`

Supported formats are listed above. Private supergroup links use `/c/` in the URL.

### 8. `CHANNEL_INVALID` / `USERNAME_INVALID` while uploading

- Pass a valid target (`@username`, `-100...`, `me`, or `-100...|topic_id`).
- Ensure the logged-in profile is in that chat/channel.
- For PowerShell, quote negative channel IDs:

```powershell
better-tg-upload -p myprofile -l .\myfile.zip -c "-1005720877997"
```

### 9. ffmpeg split failed / wrong part names

Ensure `ffmpeg` and `ffprobe` are on your `PATH`. If ffmpeg cannot split a video, the tool falls back to GNU-style `filename.ext.001` parts (not streamable). Check `~/.better-tg-upload/.tg_upload/split/` for existing parts before re-running.

### 10. `Frame capture failed` / thumbnail errors

Ensure `ffmpeg` and `ffprobe` are on your `PATH`. Test with `ffmpeg -version`.

### 11. FloodWait / rate limits

The tool retries automatically with the wait time Telegram specifies. For large batches, uploads include a 1-second delay between files.

### 12. Ctrl+C during transfer

Press Ctrl+C to interrupt (exit code `130`).

- **Folder upload:** re-run the same command; progress in `~/.better-tg-upload/.tg_upload/upload_tree/`
- **Split file:** re-run the same command; parts in `~/.better-tg-upload/.tg_upload/split/`, progress in `~/.better-tg-upload/.tg_upload/upload_resume/`

### 13. Bot file size limit

Bots can upload files up to ~50 MB. For larger files, use a **user account** session (`--phone`) instead of a bot token.

### Development setup

```bash
# Install editable
pip install -e .

# Run with verbose logging
python -m better_tg_upload -v --env

# See remaining work
cat TODO.md
```

<a id="credits"></a>

## Credits ❤️

- [mirror-leech-telegram-bot](https://github.com/anasty17/mirror-leech-telegram-bot) — transfer pipeline patterns (retry, progress, media detection, upload fallback, split strategy)
- [tg-upload](https://github.com/TheCaduceus/tg-upload) — original CLI design and feature surface inspiration
- [Kurigram](https://github.com/KurimuzonAkuma/kurigram) — modern Telegram MTProto framework

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.