"""Worked example 3: "Injection Molding".

Uses the real curated row (Injection Molding, Manufacturing Processes /
Molding) from assets/knowledge_base.csv and prints the full EducationalPlan:
a manufacturing-sequence strategy with exploded mold, flow visualization, and
cooling - not random part shots.

Run:  python -m knowledge.educational_director.examples.injection_molding
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples._print_plan import print_plan

INJECTION_ROW: dict[str, str] = {
    "topic": "Injection Molding",
    "difficulty": "B",
    "category": "Manufacturing Processes",
    "subcategory": "Molding",
    "keywords": '["injection molding","mold","plastic molding","molded parts"]',
    "search_intent": "how injection molding works",
    "viewer_level": "Beginner",
    "learning_objective": (
        "The viewer can explain the molding cycle and why the tooling cost "
        "forces high production volumes."
    ),
    "engineering_summary": (
        "Injection molding melts polymer pellets and injects them under high "
        "pressure (thousands of psi) into a closed steel mold cavity. The part "
        "cools, the mold opens along the parting line, ejector pins push the "
        "part out, and the cycle repeats in seconds. The mold is "
        "precision-machined steel costing tens of thousands of dollars, so "
        "per-part cost collapses only at high volumes. Break-even analysis "
        "decides when a part should be molded instead of printed or machined."
    ),
    "common_misconceptions": (
        '["Molding is always cheaper (tooling dominates until volume pays it '
        'back)","Molded parts are weaker than printed parts (they are typically '
        'stronger with no layer interfaces)","Any geometry can be molded '
        '(undercuts need slides, and draft angles are mandatory)"]'
    ),
    "scene_count": "5",
}


def main() -> None:
    plan = EducationalDirector().direct_from_csv(INJECTION_ROW)
    print("Educational Director - worked example: injection molding\n")
    print_plan(plan)


if __name__ == "__main__":
    main()