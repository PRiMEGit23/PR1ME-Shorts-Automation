"""Stage contract models.

One ``{input, output}`` pair per stage, mirroring the JSON contracts declared
in the prompt library. All models are plain data: no business logic, no prompt
text, no IO. Stage implementations live under :mod:`pr1me.stages`.
"""

from pr1me.models.contracts.base import (
    InputT,
    OutputT,
    StageInput,
    StageOutput,
    ValidationOutput,
)

__all__ = [
    "InputT",
    "OutputT",
    "StageInput",
    "StageOutput",
    "ValidationOutput",
]