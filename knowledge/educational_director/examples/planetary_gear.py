"""Worked example 2: "Planetary Gears".

Uses the real curated row (Planetary Gears, Mechanical Engineering / Gears)
from assets/knowledge_base.csv and prints the full EducationalPlan: a
progressive-disclosure teaching strategy with transparent housing and motion
visualization - not random macro shots.

Run:  python -m knowledge.educational_director.examples.planetary_gear
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples._print_plan import print_plan

PLANETARY_ROW: dict[str, str] = {
    "topic": "Planetary Gears",
    "difficulty": "A",
    "category": "Mechanical Engineering",
    "subcategory": "Gears",
    "keywords": '["planetary gear","epicyclic","sun gear","gear box"]',
    "search_intent": "how planetary gears work",
    "viewer_level": "Advanced",
    "learning_objective": (
        "The viewer understands the sun, ring, and carrier, and why planetary "
        "gears carry more load."
    ),
    "engineering_summary": (
        "A planetary gearset puts a sun gear, a ring gear, and planets spinning "
        "between them. Power can enter the sun, the ring, or the carrier, and "
        "each input gives a different ratio, including reverse and direct "
        "drive. That compactness is why planetary gears live in drills, "
        "automatic transmissions, and robot joints. The load splits across "
        "several planet teeth, so the set carries more torque than a pair of "
        "gears the same size. Staging several sets multiplies the ratios. When "
        "a mechanism needs a big reduction in a small space, planetary gears "
        "are usually the answer."
    ),
    "common_misconceptions": (
        '["Planetary gears need more space (they pack the most reduction per '
        'volume)","There is one fixed ratio (every input and output choice '
        'gives a new ratio)","Planet gears carry the load alone (the load '
        'spreads across all planet teeth)"]'
    ),
    "scene_count": "5",
}


def main() -> None:
    plan = EducationalDirector().direct_from_csv(PLANETARY_ROW)
    print("Educational Director - worked example: planetary gears\n")
    print_plan(plan)


if __name__ == "__main__":
    main()