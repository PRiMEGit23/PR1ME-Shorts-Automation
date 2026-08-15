"""Worked example 1: the AI Director directs the gyroid infill topic.

Takes the real curated row (Infill Pattern Comparisons) that the
Educational Director example uses, runs it through the Educational
Director and then through the AI Director, and prints the full creative
brief - the decisions every downstream module will consume.

Run:  python -m knowledge.ai_director.examples.gyroid
"""

from __future__ import annotations

from knowledge.ai_director import AIDirector
from knowledge.ai_director.examples._print_director import print_director
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples.gyroid import GYROID_ROW


def main() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    output = AIDirector().direct(plan)
    print("AI Director - worked example: gyroid infill\n")
    print_director(output)


if __name__ == "__main__":
    main()
