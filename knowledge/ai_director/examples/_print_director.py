"""Shared DirectorOutput printing for the AI Director examples."""

from __future__ import annotations

from knowledge.ai_director.director_models import DirectorOutput


def print_director(output: DirectorOutput) -> None:
    """Render one DirectorOutput as readable terminal output."""
    print(f"Topic                  : {output.topic}")
    print(f"Version                : {output.version}")
    print(f"Teaching strategy      : {output.teaching_strategy.value}")
    print(f"Scene count            : {output.scene_count}")
    print(f"Emotion arc            : {output.emotion_arc}")
    print(f"Pacing profile         : {output.pacing_profile}")
    print(f"Reveal plan            : {output.reveal_plan}")
    print(f"Hero scene             : {output.hero_scene_id}")
    print(f"Thumbnail scene        : {output.thumbnail_scene_id}")
    print(f"Recap scene            : {output.recap_scene_id}")
    print(f"Predicted retention    : {output.predicted_retention}%")
    print(f"Predicted attention    : {output.predicted_attention}%")
    print(f"Summary                : {output.summary}")
    print("Scene directives:")
    for directive in output.scene_directives:
        roles = ", ".join(
            role
            for role in ("hero", "thumbnail", "recap")
            if getattr(directive, f"is_{role}")
        )
        print(
            f"  {directive.scene_id}: {directive.visual_goal.value:<24} "
            f"{directive.shot_type.value:<18} imp {directive.importance} "
            f"budget {directive.visual_budget}/10 motion {directive.motion_budget}/10 "
            f"camera {directive.camera_intensity}/10 light {directive.lighting_priority}/10 "
            f"diagram {directive.diagram_priority}/10 compare {directive.comparison_emphasis}/10 "
            f"emotion {directive.emotion} pacing {directive.pacing} "
            f"reveal {directive.reveal_order} transition {directive.transition.type.value} "
            f"attention {directive.expected_attention}% retention {directive.retention_score}%"
            + (f" [{roles}]" if roles else "")
        )
