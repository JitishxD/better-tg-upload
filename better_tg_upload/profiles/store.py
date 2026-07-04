from pathlib import Path


def ensure_session_dir(path: str) -> Path:
    session_dir = Path(path)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir
