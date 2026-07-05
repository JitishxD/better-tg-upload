"""Pre-parse global flags that must apply before config load."""

from __future__ import annotations

import sys
from pathlib import Path


def preparse_bootstrap_args(argv: list[str] | None = None) -> tuple[Path | None, Path | None]:
    """Return ``(--config``, ``--workspace``) paths if present on the command line."""
    args = argv if argv is not None else sys.argv[1:]
    config_path: Path | None = None
    workspace_path: Path | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--config":
            if index + 1 >= len(args):
                raise SystemExit("error: --config requires a path")
            config_path = Path(args[index + 1])
            index += 2
            continue
        if arg.startswith("--config="):
            config_path = Path(arg.partition("=")[2])
            index += 1
            continue
        if arg == "--workspace":
            if index + 1 >= len(args):
                raise SystemExit("error: --workspace requires a path")
            workspace_path = Path(args[index + 1])
            index += 2
            continue
        if arg.startswith("--workspace="):
            workspace_path = Path(arg.partition("=")[2])
            index += 1
            continue
        index += 1
    return config_path, workspace_path
