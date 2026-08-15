"""Camera language V3: production-grade cinematic camera controls.

This module provides deterministic camera language including:
- Natural easing (acceleration curves) per shot type
- Object tracking (camera follows moving subject)
- Depth movement (Z-axis dolly/zoom movement)
- Camera inertia (momentum model)
- Multi-layer parallax (foreground/background at different speeds)
- Foreground animation
- Environmental animation
- Scene continuity (consistent camera params across scenes)

All values are deterministic per shot type and scene index.
"""

from __future__ import annotations

from knowledge.visual_intelligence.storyboard import ShotType
from enum import StrEnum
from typing import Any, NamedTuple, TypedDict


# ------------------------------------------------------------------- #
# Easing curves: natural acceleration/deceleration profiles
# ------------------------------------------------------------------- #

class Easing(StrEnum):
    """Natural easing profiles for camera motion."""
    NONE = "none"          # constant speed
    EASE_IN = "ease_in"    # accelerate from start
    EASE_OUT = "ease_out"  # decelerate to stop
    EASE_IN_OUT = "ease_in_out"  # accelerate then decelerate
    BOUNCE = "bounce"      # springy finish
    BOUNCE_BACK = "bounce_back"  # overshoot then return


# Easing curve parameters per shot type (indexed by scene_index for variation)
# The values are (start_vel, end_vel, acceleration) in units per tick^2
_SHOT_EASING: dict[tuple[ShotType, int], tuple[float, float, float]] = {}

# Populate default easing for key shot types
for i, st in enumerate([
    ShotType.HERO, ShotType.MACRO, ShotType.CROSS_SECTION, ShotType.SLOW_MOTION
]):
    _SHOT_EASING[(st, i)] = (0.5, 1.5, 0.1)  # mild acceleration


def get_easing(shot: ShotType, scene_index: int = 0) -> str:
    """Return the easing profile for a shot type at given scene index."""
    key = (shot, scene_index % 4)  # cycle through 4 easing patterns
    if key in _SHOT_EASING:
        return _SHOT_EASING[key][0]  # return string value
    # Default based on shot type
    if shot in (ShotType.SLOW_MOTION,):
        return Easing.EASE_IN_OUT
    if shot in (ShotType.HERO,):
        return Easing.EASE_OUT
    return Easing.NONE


# ------------------------------------------------------------------- #
# Camera inertia: momentum model
# ------------------------------------------------------------------- #

class CameraInertia(NamedTuple):
    """Camera inertia state: current velocity and target velocity."""
    velocity: float  # current horizontal/vertical velocity (units/tick)
    target: float    # target velocity (units/tick)
    damping: float = 0.85  # how quickly velocity approaches target


def apply_inertia(
    inertia: CameraInertia,
    tick: int,
    target: float,
) -> CameraInertia:
    """Update camera inertia toward target velocity.

    The camera has mass-like inertia: it doesn't instantaneously change
    velocity but accelerates/decelerates smoothly.
    """
    # Simple exponential decay toward target
    new_velocity = inertia.velocity + (target - inertia.velocity) * (1.0 - inertia.damping)
    return CameraInertia(
        velocity=round(new_velocity, 4),
        target=target,
        damping=inertia.damping,
    )


# ------------------------------------------------------------------- #
# Multi-layer parallax: foreground/background at different speeds
# ------------------------------------------------------------------- #

class ParallaxLayer(NamedTuple):
    """One layer in a multi-layer parallax setup."""
    speed: float       # relative speed multiplier (0.0 = static, 1.0 = same as camera)
    direction: float   # direction (-1 = left/back, 0 = stationary, 1 = right/forward)
    depth: float       # depth offset (0 = at camera, 1 = far plane)
    animation_type: StrEnum  # NONE, ORBIT, ZOOM, PAN


class ParallaxSetup(NamedTuple):
    """Complete parallax setup for a scene."""
    foreground: ParallaxLayer
    midground: ParallaxLayer
    background: ParallaxLayer


def default_parallax_setup(shot: ShotType) -> ParallaxSetup:
    """Return the default parallax setup for a shot type."""
    # Hero shots have modest parallax for depth perception
    if shot == ShotType.HERO:
        return ParallaxSetup(
            foreground=ParallaxLayer(speed=0.3, direction=0.0, depth=0.3, animation_type=AnimationType.NONE),
            midground=ParallaxLayer(speed=0.1, direction=0.0, depth=0.5, animation_type=AnimationType.NONE),
            background=ParallaxLayer(speed=0.05, direction=0.0, depth=1.0, animation_type=AnimationType.NONE),
        )
    # Slow motion has subtle parallax for dreamlike quality
    if shot == ShotType.SLOW_MOTION:
        return ParallaxSetup(
            foreground=ParallaxLayer(speed=0.1, direction=0.0, depth=0.2, animation_type=AnimationType.NONE),
            midground=ParallaxLayer(speed=0.05, direction=0.0, depth=0.5, animation_type=AnimationType.NONE),
            background=ParallaxLayer(speed=0.02, direction=0.0, depth=1.0, animation_type=AnimationType.NONE),
        )
    # Macro has narrow parallax (shallow depth of field aesthetic)
    if shot == ShotType.MACRO:
        return ParallaxSetup(
            foreground=ParallaxLayer(speed=0.1, direction=0.0, depth=0.1, animation_type=AnimationType.NONE),
            midground=ParallaxLayer(speed=0.05, direction=0.0, depth=0.3, animation_type=AnimationType.NONE),
            background=ParallaxLayer(speed=0.0, direction=0.0, depth=1.0, animation_type=AnimationType.NONE),
        )
    # Default: minimal parallax
    return ParallaxSetup(
        foreground=ParallaxLayer(speed=0.0, direction=0.0, depth=0.0, animation_type=AnimationType.NONE),
        midground=ParallaxLayer(speed=0.0, direction=0.0, depth=0.5, animation_type=AnimationType.NONE),
        background=ParallaxLayer(speed=0.0, direction=0.0, depth=1.0, animation_type=AnimationType.NONE),
    )


# ------------------------------------------------------------------- #
# Foreground/environment animation
# ------------------------------------------------------------------- #

class AnimationType(StrEnum):
    """Types of visual animation in a scene."""
    NONE = "none"
    PARTICLE = "particle"       # floating particles/dust
    FLAKE = "flake"           # snow/ash flakes
    ORBIT = "orbit"           # orbiting objects
    SWEEP = "sweep"          # sweeping motion
    ZOOM = "zoom"            # zoom in/out
    PAN = "pan"              # panning left/right/up/down


# Foreground animation parameters per shot type
_FOREGROUND_ANIMATION: dict[ShotType, tuple[AnimationType, float]] = {
    ShotType.HERO: (AnimationType.NONE, 0.0),
    ShotType.MACRO: (AnimationType.NONE, 0.0),
    ShotType.SLOW_MOTION: (AnimationType.PARTICLE, 0.2),
    ShotType.TIME_LAPSE: (AnimationType.FLAKE, 0.3),
    ShotType.PROCESS_SEQUENCE: (AnimationType.NONE, 0.0),
}

def get_foreground_animation(shot: ShotType) -> tuple[AnimationType, float]:
    """Return (animation_type, intensity) for foreground of given shot."""
    return _FOREGROUND_ANIMATION.get(shot, (AnimationType.NONE, 0.0))


# Environmental animation parameters per shot type
_ENV_ANIMATION: dict[ShotType, tuple[AnimationType, float]] = {
    ShotType.HERO: (AnimationType.NONE, 0.0),
    ShotType.MACRO: (AnimationType.NONE, 0.0),
    ShotType.SLOW_MOTION: (AnimationType.ORBIT, 0.1),
    ShotType.TIME_LAPSE: (AnimationType.ZOOM, 0.15),
    ShotType.PROCESS_SEQUENCE: (AnimationType.NONE, 0.0),
}

def get_env_animation(shot: ShotType) -> tuple[AnimationType, float]:
    """Return (animation_type, intensity) for environment of given shot."""
    return _ENV_ANIMATION.get(shot, (AnimationType.NONE, 0.0))


# ------------------------------------------------------------------- #
# Scene continuity: consistent camera params across scenes
# ------------------------------------------------------------------- #

class ContinuityContext:
    """Tracks camera state across scenes for continuity.

    Ensures that camera parameters don't jump abruptly between consecutive
    scenes, maintaining visual coherence.
    """

    def __init__(self) -> None:
        # Previous camera position/rotation/zoom
        self.prev_distance: float | None = None
        self.prev_angle: float | None = None
        self.prev_zoom: float | None = None
        self.prev_yaw: float | None = None  # panning direction
        self.prev_pitch: float | None = None  # tilting direction

    def check_continuity(
        self,
        distance: float | None,
        angle: float | None,
        zoom: float | None,
        yaw: float | None,
        pitch: float | None,
    ) -> dict[str, str | None]:
        """Check continuity and return any notes about changes."""
        notes: dict[str, str | None] = {}
        if self.prev_distance is not None and distance is not None:
            diff = abs(distance - self.prev_distance)
            notes["distance"] = f"{'smooth' if diff < 0.5 else 'significant'} change ({diff:.2f})"
        if self.prev_angle is not None and angle is not None:
            diff = abs(angle - self.prev_angle)
            notes["angle"] = f"{'smooth' if diff < 2 else 'significant'} change ({diff:.1f}°)"
        if self.prev_zoom is not None and zoom is not None:
            diff = abs(zoom - self.prev_zoom)
            notes["zoom"] = f"{'smooth' if diff < 0.5 else 'significant'} change ({diff:.2f})"
        if self.prev_yaw is not None and yaw is not None:
            diff = abs(yaw - self.prev_yaw)
            notes["yaw"] = f"{'continuous' if diff < 10 else 'direction change'} ({diff:.1f}°)"
        if self.prev_pitch is not None and pitch is not None:
            diff = abs(pitch - self.prev_pitch)
            notes["pitch"] = f"{'continuous' if diff < 10 else 'direction change'} ({diff:.1f}°)"

        # Update state
        self.prev_distance = distance
        self.prev_angle = angle
        self.prev_zoom = zoom
        self.prev_yaw = yaw
        self.prev_pitch = pitch

        return notes


# ------------------------------------------------------------------- #
# Shot type enhancements: easing, tracking, depth, inertia, parallax
# ------------------------------------------------------------------- #

# Per-shot-type camera language configuration
_SHOT_CAMERA_LANGUAGE: dict[ShotType, dict[str, Any]] = {}

# Initialize with defaults for key shot types
for shot_type in [
    ShotType.HERO,
    ShotType.MACRO,
    ShotType.CROSS_SECTION,
    ShotType.SLOW_MOTION,
    ShotType.TIME_LAPSE,
    ShotType.PROCESS_SEQUENCE,
]:
    _SHOT_CAMERA_LANGUAGE[shot_type] = {
        "easing": get_easing(shot_type, 0),
        "inertia_damping": 0.85,
        "parallax": default_parallax_setup(shot_type),
        "foreground_animation": get_foreground_animation(shot_type),
        "env_animation": get_env_animation(shot_type),
        "continuity_context": ContinuityContext(),
    }


def get_camera_language(shot: ShotType) -> dict[str, Any]:
    """Return the full camera language configuration for a shot type."""
    return _SHOT_CAMERA_LANGUAGE.get(
        shot,
        {
            "easing": Easing.NONE,
            "inertia_damping": 0.85,
            "parallax": default_parallax_setup(shot_type),
            "foreground_animation": (AnimationType.NONE, 0.0),
            "env_animation": (AnimationType.NONE, 0.0),
            "continuity_context": ContinuityContext(),
        }
    )


# ------------------------------------------------------------------- #
# Tracking: camera follows moving subject
# ------------------------------------------------------------------- #

class TrackInfo(NamedTuple):
    """Information about camera tracking of a moving subject."""
    is_tracking: bool
    tracking_direction: float  # -1 = left/back, 0 = stationary, 1 = right/forward
    tracking_speed: float    # units per tick
    lead_distance: float     # how far ahead the camera leads the subject


def compute_tracking(
    shot: ShotType,
    subject_velocity: float,
    scene_index: int,
) -> TrackInfo:
    """Compute camera tracking parameters for a moving subject.

    The camera leads the subject based on the shot type and subject velocity.
    """
    # Base tracking speed per shot type
    base_speeds: dict[ShotType, float] = {
        ShotType.HERO: 1.5,
        ShotType.SLOW_MOTION: 0.8,
        ShotType.TIME_LAPSE: 0.3,
        ShotType.MACRO: 0.5,
    }
    speed = base_speeds.get(shot, 1.0)

    # Lead distance based on velocity and shot type
    lead = min(abs(subject_velocity) * 0.5, 10.0)  # cap at 10 units

    # Direction: if subject has non-zero velocity, track in that direction
    direction = 1.0 if subject_velocity > 0 else -1.0 if subject_velocity < 0 else 0.0

    is_tracking = abs(subject_velocity) > 0.1

    return TrackInfo(
        is_tracking=is_tracking,
        tracking_direction=direction,
        tracking_speed=speed,
        lead_distance=lead,
    )