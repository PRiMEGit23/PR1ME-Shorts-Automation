"""Worked example 1: "Why Gyroid Infill Is Stronger Than Grid".

Uses the real curated row (Infill Pattern Comparisons, Slicer & Print
Settings / Infill) straight from assets/knowledge_base.csv, runs it through
the Educational Director, and prints the full EducationalPlan.

Run:  python -m knowledge.educational_director.examples.gyroid
"""

from __future__ import annotations

from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.examples._print_plan import print_plan

GYROID_ROW: dict[str, str] = {
    "topic": "Infill Pattern Comparisons",
    "difficulty": "B",
    "category": "Slicer & Print Settings",
    "subcategory": "Infill",
    "keywords": '["infill patterns","gyroid","cubic","grid infill","honeycomb"]',
    "search_intent": "what infill pattern is strongest",
    "viewer_level": "Intermediate",
    "learning_objective": (
        "The viewer can compare gyroid, cubic, grid, and line patterns by "
        "strength, isotropy, and speed, and pick for the load."
    ),
    "engineering_summary": (
        "Infill patterns differ in strength per gram, directionality, and print "
        "speed. Gyroid is the engineering favorite: a triply periodic surface "
        "with no flat layers, giving near-isotropic strength, good energy "
        "absorption, and even stress distribution - at a small speed cost. "
        "Cubic builds stacked cubes for strong vertical structure but leaves "
        "45-degree weak zones and takes time. Grid is fast, but its crossing "
        "lines create stress concentration at intersections and strong "
        "directional anisotropy. Lines and triangles are cheap and fine for "
        "light duty. Rule of thumb: gyroid for structural parts and impact, "
        "cubic for tall columns, grid for speed and low-load parts."
    ),
    "common_misconceptions": (
        '["The strongest pattern is strongest everywhere (patterns are '
        'directional; gyroid is the isotropic exception)","Dense infill removes '
        'pattern differences (pattern matters most at 20-40% where parts '
        'actually print)","Pattern choice is cosmetic (strength, energy '
        'absorption, and printing time all change)"]'
    ),
    "scene_count": "5",
}


def main() -> None:
    plan = EducationalDirector().direct_from_csv(GYROID_ROW)
    print("Educational Director - worked example: gyroid infill\n")
    print_plan(plan)


if __name__ == "__main__":
    main()