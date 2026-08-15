"""Worked example: the injection molding manufacturing-sequence film.

Run: ``python -m knowledge.model_director.examples.injection_molding``
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.model_director import ModelDirector
from knowledge.model_director.examples._print import print_model_output


def run() -> str:
    """Direct the injection molding film and print the model brief."""
    plan = EducationalDirector().direct_from_csv(INJECTION_ROW)
    brief = AIDirector().direct(plan)
    output = ModelDirector().direct(brief)
    print_model_output(output)
    return output.topic


if __name__ == "__main__":
    run()
