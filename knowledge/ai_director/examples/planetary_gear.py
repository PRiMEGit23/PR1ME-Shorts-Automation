"""Worked example 2: the AI Director directs the planetary gear topic.

A mechanism-heavy topic: the director must decide between diagram-first
and photoreal treatment, and the staggered reveal should push the gear
teeth reveal after the comparison beat.

Run:  python -m knowledge.ai_director.examples.planetary_gear
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.ai_director.examples._print_director import print_director
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW


def main() -> None:
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    output = AIDirector().direct(plan)
    print("AI Director - worked example: planetary gear\n")
    print_director(output)


if __name__ == "__main__":
    main()
