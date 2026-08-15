"""Concrete model compilers. Importing this package registers them."""

from knowledge.compiler.compilers import sdxl  # noqa: F401

__all__ = ["sdxl"]
