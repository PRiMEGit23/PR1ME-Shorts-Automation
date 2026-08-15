"""Worked example: the gyroid infill comparison film through the Model Director.

Run: ``python -m knowledge.model_director.examples.gyroid``
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.model_director import ModelDirector
from knowledge.model_director.examples._print import print_model_output


def run() -> str:
    """Direct the gyroid film and print the model brief; returns the topic."""
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    brief = AIDirector().direct(plan)
    output = ModelDirector().direct(brief)
    print_model_output(output)
    return output.topic


if __name__ == "__main__":
    run()
