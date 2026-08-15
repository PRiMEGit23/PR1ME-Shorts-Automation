"""Worked example 3: the AI Director directs the injection molding topic.

A manufacturing-sequence topic: the director should split the arc to six
scenes (the evidence beat earns its own scene) and push engineering
emphasis onto the reveal and process beats.

Run:  python -m knowledge.ai_director.examples.injection_molding
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.ai_director.examples._print_director import print_director
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW


def main() -> None:
    plan = EducationalDirector().direct_from_csv(INJECTION_ROW)
    output = AIDirector().direct(plan)
    print("AI Director - worked example: injection molding\n")
    print_director(output)


if __name__ == "__main__":
    main()
