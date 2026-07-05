"""First-time CLI setup under the user home directory."""

from __future__ import annotations

from importlib import resources

from .config import app_home, default_config_path, ensure_workspace


def run_init(*, force: bool = False) -> None:
    """Create ``~/.better-tg-upload`` with config and workspace folders."""
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    config_path = default_config_path()

    if config_path.exists() and not force:
        ensure_workspace()
        print(f"Already initialized: {home}")
        print(f"Config: {config_path}")
        print("Use --force with --init to overwrite config.py.")
        return

    sample = resources.files("better_tg_upload.templates").joinpath("config_sample.py")
    config_path.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
    workspace = ensure_workspace()

    print(f"Initialized: {home}")
    print(f"Config: {config_path}")
    print(f"Workspace: {workspace}")
    print("Next: edit config.py (API_ID, API_HASH, PROFILE), then run:")
    print("  better-tg-upload -p myprofile --login_only")
