from asyncio import run
from sys import exit

from .cli.parser import build_parser
from .core.config import load_user_config
from .core.runner import run_cli
from .utils.log import setup_logging

_INTERRUPT_EXIT = 130


def main() -> int:
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
