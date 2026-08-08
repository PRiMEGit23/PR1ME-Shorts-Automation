"""Command-line interface for the PR1ME-engine.

Exposes :func:`entrypoint`, the console-script target wired in ``pyproject.toml``
as ``pr1me = "pr1me.cli.main:entrypoint"``.
"""

from pr1me.cli.main import entrypoint, main

__all__ = ["entrypoint", "main"]