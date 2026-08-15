"""Example: Visual Intelligence Engine on "Why Gyroid Infill Is Stronger Than Grid".

Takes the V2 VisualArchitecture from the Phase 1 conversion example, directs
it through the VisualIntelligenceEngine (goals, shot types, camera/lighting/
composition plans, engineering visualizations, transitions, thumbnail pick),
compiles the storyboard through the SDXL compiler, and prints the goals,
plans, transitions, and prompts alongside the Phase 1 compiler output.

Run:  python -m knowledge.visual_intelligence.examples.gyroid_storyboard
"""

from __future__ import annotations

from knowledge.compiler import compile_for_model, compile_for_storyboard
from knowledge.compiler.examples.gyroid_v2 import TOPIC, build_gyroid_architecture
from knowledge.visual_intelligence import VisualIntelligenceEngine

_KEYWORDS = ["infill patterns", "gyroid", "cubic", "grid infill", "honeycomb"]

_COMPARED_GOALS = (
    "The goal chain now carries real intent. The Phase 1 prompt and the "
    "storyboard prompt describe the same physical content, but the storyboard "
    "decided WHY each scene exists before any phrasing happened."
)


def _why_superior() -> str:
    return (
        "\nWhy the storyboard is superior:\n"
        "  1. Goal-driven shots: the director classified S1 introduce, S2 reveal "
        "internal geometry (infill), S3 explain force flow (load), S4 highlight "
        "difference (its shear/stress signal repeated the force-flow intent, so "
        "the director turned it into a comparison), S5 summarize. Phase 1 simply "
        "carried the spec's modalities through.\n"
        "  2. Shot types encode intent: S3 became an annotated diagram with force "
        "arrows instead of a bare diagram; S4 became a before/after comparison "
        "instead of a third diagram.\n"
        "  3. Cinematic plans are derived, not hand-written: camera, lighting, "
        "composition, and transitions fall out of the goal table and material "
        "rules, so any curated topic gets the same disciplined framing.\n"
        "  4. Engineering overlays are explicit: 'white force arrows showing load "
        "paths, compression and tension arrows' is a structured visualization "
        "the compiler phrases verbatim, never invented.\n"
        "  5. Thumbnail is chosen by score: S5 (hero, summarize, explicit "
        "candidate) wins 17 to S4's 12 - the same judgment a curator makes, "
        "computed deterministically.\n"
        "  6. Still model-agnostic: the storyboard stores no prompt strings; "
        "FLUX/GPT Image compilers will consume the same plans."
    )


def main() -> None:
    architecture = build_gyroid_architecture()
    engine = VisualIntelligenceEngine()
    storyboard = engine.plan_storyboard(
        architecture,
        topic=TOPIC,
        keywords=_KEYWORDS,
    )

    compiled_legacy = compile_for_model(architecture, "sdxl", topic=TOPIC)
    compiled_story = compile_for_storyboard(storyboard, "sdxl", topic=TOPIC)

    print(f"Visual Intelligence Engine example: {TOPIC}\n")
    for scene in storyboard.scenes:
        legacy = compiled_legacy.scenes[scene.scene_id]
        generated = compiled_story.scenes[scene.scene_id]
        intent = scene.intent
        print(f"--- Scene {scene.scene_id} (index {scene.scene_index}) ---")
        print(
            f"GOAL    : {intent.goal.value} via {intent.shot_type.value} "
            f"({intent.rationale})"
        )
        viz = " / ".join(v.type.value for v in intent.engineering_visualizations) or "none"
        print(f"ENG-VIZ : {viz}")
        camera = scene.camera
        print(
            f"CAMERA  : {camera.distance.value} / {camera.angle.value} / "
            f"{camera.lens.value} / {camera.framing.value} / {camera.height.value}"
        )
        print(f"LIGHTING: {scene.lighting.direction.value} / {scene.lighting.style.value}")
        print(f"TRANS   : {scene.transition.type.value} ({scene.transition.rationale})")
        print(f"THUMB   : rank {scene.thumbnail_priority.rank} "
              f"(score {scene.thumbnail_priority.score})")
        print(f"PHASE 1 (V2 SDXL):\n  {legacy.prompt}")
        print(f"STORYBOARD (V2 SDXL):\n  {generated.prompt}")
        print(f"  negative: {generated.negative_prompt}\n")

    print("--- Thumbnail ---")
    winner = next(s for s in storyboard.scenes if s.scene_id == storyboard.thumbnail_scene_id)
    print(
        f"Winner scene: {storyboard.thumbnail_scene_id} "
        f"(score {winner.thumbnail_priority.score})"
    )
    print(f"PHASE 1 (V2 SDXL):\n  {compiled_legacy.thumbnail.prompt}")
    print(f"STORYBOARD (V2 SDXL):\n  {compiled_story.thumbnail.prompt}")
    print(f"  negative: {compiled_story.thumbnail.negative_prompt}")
    print(_COMPARED_GOALS)
    print(_why_superior())


if __name__ == "__main__":
    main()