from asyncio import run
from sys import exit

from .cli.bootstrap import preparse_bootstrap_args
from .cli.parser import build_parser
from .core.config import load_user_config, set_config_path, set_workspace_path
from .core.exceptions import CliError
from .core.runner import run_cli
from .utils.log import setup_logging

_INTERRUPT_EXIT = 130


def main() -> int:
    try:
        config_override, workspace_override = preparse_bootstrap_args()
        if config_override is not None:
            set_config_path(config_override)
        if workspace_override is not None:
            set_workspace_path(workspace_override)
    except CliError as exc:
        print(f"Error: {exc}")
        return 1

    load_user_config()
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(verbose=bool(args.verbose))
    try:
        return run(run_cli(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return _INTERRUPT_EXIT


if __name__ == "__main__":
    exit(main())
