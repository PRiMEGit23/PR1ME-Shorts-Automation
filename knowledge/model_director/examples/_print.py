"""Pretty-print one ModelOutput as the terminal renderer."""

from __future__ import annotations

from knowledge.model_director.model_profiles import ModelOutput


def print_model_output(output: ModelOutput) -> None:
    """Deterministic terminal rendering of one model brief."""
    print(f"Model Director - {output.topic} ({output.version})")
    print(f"  {output.summary}")
    for plan in output.scene_plans:
        profile = plan.model_profile
        print(f"  {plan.scene_id} {profile.image_model} ({profile.render_profile.value})")
        print(
            f"    sampler={profile.sampler} scheduler={profile.scheduler} "
            f"cfg={profile.cfg} steps={profile.steps} "
            f"res={profile.resolution} {profile.aspect_ratio}"
        )
        print(
            f"    vae={profile.vae} loras={','.join(profile.loras) or 'none'} "
            f"controlnet={profile.controlnet} ip_adapter={profile.ip_adapter} "
            f"upscaler={profile.upscaler} refiner={profile.refiner}"
        )
        print(
            f"    video={profile.video_model} ({profile.animation_backend}) "
            f"quality={profile.quality_target}"
        )
        print(
            f"    predicted: qa {plan.expected_qa_score} "
            f"success {plan.expected_success_probability:.2f} "
            f"retries {plan.expected_retry_count} "
            f"vram {plan.expected_vram_mb}MiB "
            f"time {plan.estimated_time_seconds}s"
        )
