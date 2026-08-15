"""Worked-example runner: direct all three canonical topics in one command.

Each example builds the EducationalPlan from a real curated Knowledge Base
row, runs the deterministic AI Director, and returns the DirectorOutput.
The runner is the entry point the worked-example test calls.

Run:  python -m knowledge.ai_director.examples.run_worked_examples
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.ai_director.director_models import DirectorOutput
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW

WORKED_EXAMPLES: tuple[tuple[str, dict[str, str]], ...] = (
    ("gyroid", GYROID_ROW),
    ("planetary_gear", PLANETARY_ROW),
    ("injection_molding", INJECTION_ROW),
)


def direct_all() -> dict[str, DirectorOutput]:
    """Direct every canonical worked-example row; deterministic output."""
    director = AIDirector()
    educational = EducationalDirector()
    return {
        name: director.direct(educational.direct_from_csv(row))
        for name, row in WORKED_EXAMPLES
    }


def main() -> None:
    outputs = direct_all()
    for name, output in outputs.items():
        print(f"===== {name} =====")
        print(output.summary)
        print()


if __name__ == "__main__":
    main()
