"""Command-line entry point for the PR1ME-engine.

The CLI only bootstraps the application: it parses arguments, configures
structured logging, and dispatches to subcommands. It contains no business
logic and does not execute the pipeline.

Subcommands are registered through :func:`register_command` and resolved from
:data:`_COMMANDS`, so new commands can be added without touching the parser
construction or the dispatch loop.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from pr1me.core.config import Settings
from pr1me.core.logging import get_logger, setup_logging
from pr1me.version import __version__

#: Conventional process exit codes.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

logger = get_logger("pr1me.cli")

#: command name -> (help text, parser builder, handler).
CommandHandler = Callable[[argparse.Namespace, Settings], int]
ParserBuilder = Callable[[argparse.ArgumentParser], None]
_COMMANDS: dict[str, tuple[str, ParserBuilder | None, CommandHandler]] = {}


def register_command(
    name: str,
    help_text: str,
    *,
    add_parser: ParserBuilder | None = None,
) -> Callable[[CommandHandler], CommandHandler]:
    """Register a subcommand handler under ``name``.

    ``add_parser`` may customize the command's argument parser (flags, options);
    the ``--help`` text is always available.
    """

    def decorate(handler: CommandHandler) -> CommandHandler:
        _COMMANDS[name] = (help_text, add_parser, handler)
        return handler

    return decorate


# ------------------------------------------------------------------ build ---


def build_parser() -> argparse.ArgumentParser:
    """Construct the full argument surface for the CLI."""
    parser = argparse.ArgumentParser(
        prog="pr1me",
        description="PR1ME Labs YouTube Shorts automation engine.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default=None,
        help="override the configured log level (DEBUG|INFO|WARNING|ERROR)",
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        default=None,
        help="force structured JSON logs",
    )
    parser.add_argument(
        "--no-json-logs",
        action="store_true",
        dest="no_json_logs",
        help="force plain-text logs",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    for name, (help_text, add_parser, _handler) in _COMMANDS.items():
        sub = subparsers.add_parser(name, help=help_text)
        if add_parser is not None:
            add_parser(sub)
    return parser


# ------------------------------------------------------------------ main ----


def main(argv: Sequence[str] | None = None) -> int:
    """Bootstrap the application and dispatch to a subcommand.

    Returns the process exit code; never executed by the console script twice.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = Settings()
    setup_logging(level=args.log_level or settings.log_level, json=_json_chosen(args, settings))

    if args.command is None:
        parser.print_help()
        return EXIT_OK

    handler = _COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse guards the choice
        logger.error("event=cli.unknown_command", command=args.command)
        return EXIT_USAGE

    try:
        return handler[2](args, settings)
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        logger.exception("cli.failed", command=args.command, error=str(exc))
        return EXIT_ERROR


def entrypoint() -> None:
    """Console-script target; wraps :func:`main` with :func:`sys.exit`."""
    sys.exit(main())


# ------------------------------------------------------------- internals ----


def _json_chosen(args: argparse.Namespace, settings: Settings) -> bool:
    if args.json_logs:
        return True
    if args.no_json_logs:
        return False
    return bool(settings.log_json)


# Late import: registers the `run` subcommand into _COMMANDS without a
# circular import (run.py imports register_command/EXIT_* from this module).
import pr1me.cli.run as _run_command  # noqa: E402,F401  (registers the `run` subcommand)