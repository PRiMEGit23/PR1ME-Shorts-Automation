"""Worked examples: the closed-loop engine end to end, artifacts on disk.

Phase 6 deliverable: demonstrate the autonomous generation engine on the
three canonical Knowledge Base rows plus a retry-budget exhaustion case.
Each example runs the full deterministic chain - Knowledge row -> Educational
Director -> Storyboard -> Prompt Compiler -> render -> QA -> optimize ->
re-render - and saves every attempt's artifacts (render prompt, workflow
JSON, QA report, optimization report, image) under
``<output_root>/<example>/...`` as ``attempt_01``, ``attempt_02``, ... plus a
replayable ``history.json``.

Scenarios (all deterministic, verified by the unit suite):

1. ``gyroid``           - QA passes on the first render (1 attempt)
2. ``planetary_gear``   - full repair: QA rejects, optimizer prescribes a
                          plan, the re-render passes (2 attempts)
3. ``injection_molding``- converges after one optimization round
                          (2 attempts)
4. ``budget_exhaustion``- a renderer that never cures burns the whole retry
                          budget: attempt_01..attempt_03 all FAILED, proving
                          the engine stops when the budget runs out

Run:  python -m runtime.examples.run_worked_examples
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.image_qa.qa_models import GeneratedImageMetadata
from knowledge.visual_architecture import EngineeringDomain, Modality
from runtime.models import (
    RenderRequest,
    RenderResult,
    RenderSessionResult,
    SessionConfig,
)
from runtime.render_session import RenderSession
from runtime.renderer import Renderer, SimulatedRenderer, tiny_png


@dataclass(frozen=True)
class WorkedExample:
    """One canonical scenario: a row, a scene, a seed, and its expected arc."""

    name: str
    row: dict[str, str]
    scene_id: str
    seed: int
    engineering_domain: EngineeringDomain
    max_attempts: int = 3


WORKED_EXAMPLES: tuple[WorkedExample, ...] = (
    WorkedExample(
        name="gyroid",
        row=GYROID_ROW,
        scene_id="S2",
        seed=29,
        engineering_domain=EngineeringDomain.FDM,
    ),
    WorkedExample(
        name="planetary_gear",
        row=PLANETARY_ROW,
        scene_id="S2",
        seed=42,
        engineering_domain=EngineeringDomain.MECHANISMS,
    ),
    WorkedExample(
        name="injection_molding",
        row=INJECTION_ROW,
        scene_id="S2",
        seed=42,
        engineering_domain=EngineeringDomain.INJECTION_MOLDING,
    ),
    WorkedExample(
        name="budget_exhaustion",
        row=PLANETARY_ROW,
        scene_id="S2",
        seed=3,
        engineering_domain=EngineeringDomain.MECHANISMS,
    ),
)


def _stuck_metadata(scene_id: str) -> GeneratedImageMetadata:
    """Metadata that fails every QA check but stays within model caps."""
    return GeneratedImageMetadata(
        scene_id=scene_id,
        subject_present=True,
        subject_prominence=0.35,
        subject_occluded=True,
        hierarchy_clear=False,
        engineering_accuracy=0.3,
        geometry_correct=False,
        geometry_quality=0.35,
        material_correct=False,
        material_quality=0.35,
        camera_distance_matches=False,
        camera_angle_matches=False,
        lens_matches=False,
        lighting_direction_matches=False,
        lighting_style_matches=False,
        composition_rule_matches=False,
        composition_quality=0.35,
        clutter_level=0.7,
        visual_clarity=0.45,
        method_implemented=False,
        annotations_present=False,
        annotation_quality=0.35,
        comparison_axis_present=False,
        thumbnail_contrast=0.35,
        thumbnail_focus=0.35,
        thumbnail_negative_space=False,
        scene_consistency=0.4,
        consistency_violations=["palette drift"],
        prompt_term_mismatches=["missing terms"],
    )


class StuckRenderer:
    """Deterministic renderer that never cures: every attempt fails QA.

    Stands in for a real ComfyUI deployment that cannot be repaired by the
    optimizer. The loop must burn the retry budget and stop, saving all
    attempts.
    """

    def render(self, request: RenderRequest) -> RenderResult:
        return RenderResult(
            metadata=_stuck_metadata(request.scene_id),
            image_bytes=tiny_png(request.seed, request.attempt_index),
        )


def generate(output_root: Path | None = None) -> dict[str, RenderSessionResult]:
    """Run every worked example and return name -> session result.

    Artifacts are saved under ``output_root / <name>``; with ``None`` the
    default session output root (``output/runtime``) is used.
    """
    output_root = output_root or Path("output/runtime") / "worked_examples"
    results: dict[str, RenderSessionResult] = {}
    for example in WORKED_EXAMPLES:
        renderer: Renderer
        if example.name == "budget_exhaustion":
            renderer = StuckRenderer()
        else:
            renderer = SimulatedRenderer()
        session = RenderSession(renderer=renderer)
        results[example.name] = session.run(
            example.row,
            example.scene_id,
            seed=example.seed,
            engineering_domain=example.engineering_domain,
            modality=Modality.PHOTOREAL,
            config=SessionConfig(
                output_root=output_root / example.name,
                max_attempts=example.max_attempts,
            ),
        )
    return results


def main() -> None:
    print("Runtime - worked examples: closed-loop generation\n")
    results = generate()
    for name, result in results.items():
        statuses = ", ".join(a.status.value for a in result.attempts)
        winner = result.winner
        print(
            f"{name:18s} passed={result.passed}  attempts=[{statuses}]  "
            f"winner={winner.attempt_id if winner else '-'}"
        )


if __name__ == "__main__":
    main()
