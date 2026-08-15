"""Model registry: every supported image and video model (Phase 10).

The registry is the single source of truth for what a model can do: its
kind (image / video), its measured capability scores (photoreal fidelity,
diagram quality, macro detail, engineering accuracy, prompt adherence),
its resource footprint (VRAM, relative speed), and the exact set of
parameters it supports (samplers, schedulers, VAEs, resolutions, aspect
ratios, ControlNet / IPAdapter / depth / segmentation / upscaler /
refiner / animation backends).

Future models join through :meth:`ModelRegistry.register` - nothing else
in the Model Director needs to change to support a new model.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ModelKind(StrEnum):
    """What a model generates."""

    IMAGE = "image"
    VIDEO = "video"


class ModelSpec(BaseModel):
    """One deterministic, immutable capability record for a model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    family: str = Field(min_length=1, max_length=40)
    kind: ModelKind

    #: Capability scores (0-100) on the axes the quality predictor uses.
    photoreal: float = Field(ge=0.0, le=100.0)
    diagram: float = Field(ge=0.0, le=100.0)
    macro_detail: float = Field(ge=0.0, le=100.0)
    engineering: float = Field(ge=0.0, le=100.0)
    adherence: float = Field(ge=0.0, le=100.0)
    #: Video models only: how well the model conveys motion.
    motion_quality: float = Field(default=0.0, ge=0.0, le=100.0)

    #: Resource + reliability facts used by the predictors.
    vram_mb: int = Field(ge=512)
    speed_factor: float = Field(gt=0.0)
    reliability: float = Field(ge=0.0, le=1.0)
    steps_range: tuple[int, int] = Field(default=(20, 40))

    #: Supported parameters (used by the compatibility checker).
    supported_samplers: tuple[str, ...] = Field(default_factory=tuple)
    supported_schedulers: tuple[str, ...] = Field(default_factory=tuple)
    supported_vaes: tuple[str, ...] = Field(default_factory=tuple)
    supported_resolutions: tuple[str, ...] = Field(default_factory=tuple)
    supported_aspect_ratios: tuple[str, ...] = Field(default_factory=tuple)
    supported_controlnet: tuple[str, ...] = Field(default_factory=tuple)
    supported_ip_adapters: tuple[str, ...] = Field(default_factory=tuple)
    supported_depth: tuple[str, ...] = Field(default_factory=tuple)
    supported_segmentation: tuple[str, ...] = Field(default_factory=tuple)
    supported_upscalers: tuple[str, ...] = Field(default_factory=tuple)
    supported_refiners: tuple[str, ...] = Field(default_factory=tuple)
    supported_animation_backends: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def is_video(self) -> bool:
        return self.kind is ModelKind.VIDEO


#: The default model family when nothing is requested.
DEFAULT_MODEL_KEY = "sdxl"
DEFAULT_VIDEO_MODEL_KEY = "wan-2-2"
#: Canonical tie-break order: registry order wins on equal scores.
_MODEL_ORDER: tuple[str, ...] = (
    # image
    "flux-dev",
    "flux-schnell",
    "sdxl",
    "juggernaut-xl",
    "realvis-xl",
    "qwen-image",
    "gpt-image",
    "hiredream",
    # video
    "wan-2-2",
    "ltx-video",
    "hunyuan-video",
    "cogvideox",
    "animatediff",
)

MODELS: dict[str, ModelSpec] = {}


def _register(
    key: str,
    name: str,
    family: str,
    kind: ModelKind,
    *,
    photoreal: float,
    diagram: float,
    macro_detail: float,
    engineering: float,
    adherence: float,
    motion_quality: float = 0.0,
    vram_mb: int,
    speed_factor: float,
    reliability: float,
    steps_range: tuple[int, int] = (20, 40),
    samplers: tuple[str, ...],
    schedulers: tuple[str, ...],
    vaes: tuple[str, ...],
    resolutions: tuple[str, ...],
    aspect_ratios: tuple[str, ...] = ("9:16",),
    controlnet: tuple[str, ...] = (),
    ip_adapters: tuple[str, ...] = (),
    depth: tuple[str, ...] = (),
    segmentation: tuple[str, ...] = (),
    upscalers: tuple[str, ...] = (),
    refiners: tuple[str, ...] = (),
    animation_backends: tuple[str, ...] = (),
) -> None:
    MODELS[key] = ModelSpec(
        key=key,
        name=name,
        family=family,
        kind=kind,
        photoreal=photoreal,
        diagram=diagram,
        macro_detail=macro_detail,
        engineering=engineering,
        adherence=adherence,
        motion_quality=motion_quality,
        vram_mb=vram_mb,
        speed_factor=speed_factor,
        reliability=reliability,
        steps_range=steps_range,
        supported_samplers=samplers,
        supported_schedulers=schedulers,
        supported_vaes=vaes,
        supported_resolutions=resolutions,
        supported_aspect_ratios=aspect_ratios,
        supported_controlnet=controlnet,
        supported_ip_adapters=ip_adapters,
        supported_depth=depth,
        supported_segmentation=segmentation,
        supported_upscalers=upscalers,
        supported_refiners=refiners,
        supported_animation_backends=animation_backends,
    )


# ------------------------------------------------------------------ images --

_register(
    "flux-dev",
    "FLUX Dev",
    "flux",
    ModelKind.IMAGE,
    photoreal=95.0,
    diagram=78.0,
    macro_detail=90.0,
    engineering=88.0,
    adherence=92.0,
    vram_mb=16384,
    speed_factor=1.0,
    reliability=0.95,
    steps_range=(20, 50),
    samplers=("euler", "dpmpp_2m", "flow_mg"),
    schedulers=("flow_matching", "euler", "normal"),
    vaes=("flux-vae",),
    resolutions=("832x1216", "1024x1792", "896x1568"),
    aspect_ratios=("9:16", "1:1"),
    controlnet=("canny", "depth", "lineart"),
    ip_adapters=("style_transfer",),
    depth=("monocular",),
    segmentation=("none",),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
)
_register(
    "flux-schnell",
    "FLUX Schnell",
    "flux",
    ModelKind.IMAGE,
    photoreal=88.0,
    diagram=74.0,
    macro_detail=82.0,
    engineering=80.0,
    adherence=86.0,
    vram_mb=12288,
    speed_factor=1.4,
    reliability=0.93,
    steps_range=(1, 8),
    samplers=("euler", "dpmpp_2m", "flow_mg"),
    schedulers=("flow_matching", "normal"),
    vaes=("flux-vae",),
    resolutions=("832x1216", "1024x1792"),
    aspect_ratios=("9:16", "1:1"),
    controlnet=("canny", "depth"),
    ip_adapters=("style_transfer",),
    depth=("monocular",),
    segmentation=("none",),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
)
_register(
    "sdxl",
    "SDXL",
    "sdxl",
    ModelKind.IMAGE,
    photoreal=80.0,
    diagram=82.0,
    macro_detail=85.0,
    engineering=84.0,
    adherence=85.0,
    vram_mb=8192,
    speed_factor=1.8,
    reliability=0.98,
    steps_range=(20, 40),
    samplers=("dpmpp_2m", "euler_a", "ddim", "dpmpp_sde"),
    schedulers=("karras", "normal", "sde"),
    vaes=("sdxl-vae-fp16-fix",),
    resolutions=("832x1216", "768x1280", "1024x1792"),
    aspect_ratios=("9:16", "1:1", "4:5"),
    controlnet=("canny", "depth", "lineart", "pose"),
    ip_adapters=("style_transfer",),
    depth=("monocular", "depth_map"),
    segmentation=("sam",),
    upscalers=("esrgan", "4x_ultrasharp"),
    refiners=("sdxl-refiner",),
    animation_backends=("animatediff",),
)
_register(
    "juggernaut-xl",
    "Juggernaut XL",
    "sdxl",
    ModelKind.IMAGE,
    photoreal=86.0,
    diagram=80.0,
    macro_detail=88.0,
    engineering=84.0,
    adherence=87.0,
    vram_mb=8192,
    speed_factor=1.7,
    reliability=0.96,
    steps_range=(20, 40),
    samplers=("dpmpp_2m", "euler_a", "ddim"),
    schedulers=("karras", "normal"),
    vaes=("sdxl-vae-fp16-fix",),
    resolutions=("832x1216", "768x1280", "1024x1792"),
    aspect_ratios=("9:16", "1:1", "4:5"),
    controlnet=("canny", "depth", "lineart"),
    ip_adapters=("style_transfer",),
    depth=("monocular", "depth_map"),
    segmentation=("sam",),
    upscalers=("esrgan", "4x_ultrasharp"),
    refiners=("sdxl-refiner",),
    animation_backends=("animatediff",),
)
_register(
    "realvis-xl",
    "RealVis XL",
    "sdxl",
    ModelKind.IMAGE,
    photoreal=87.0,
    diagram=78.0,
    macro_detail=86.0,
    engineering=85.0,
    adherence=86.0,
    vram_mb=8192,
    speed_factor=1.7,
    reliability=0.96,
    steps_range=(20, 40),
    samplers=("dpmpp_2m", "euler_a", "ddim"),
    schedulers=("karras", "normal"),
    vaes=("sdxl-vae-fp16-fix",),
    resolutions=("832x1216", "768x1280", "1024x1792"),
    aspect_ratios=("9:16", "1:1", "4:5"),
    controlnet=("canny", "depth", "lineart"),
    ip_adapters=("style_transfer",),
    depth=("monocular", "depth_map"),
    segmentation=("sam",),
    upscalers=("esrgan", "4x_ultrasharp"),
    refiners=("sdxl-refiner",),
    animation_backends=("animatediff",),
)
_register(
    "qwen-image",
    "Qwen Image",
    "qwen",
    ModelKind.IMAGE,
    photoreal=90.0,
    diagram=70.0,
    macro_detail=84.0,
    engineering=86.0,
    adherence=88.0,
    vram_mb=16384,
    speed_factor=0.8,
    reliability=0.90,
    steps_range=(20, 50),
    samplers=("dpmpp_2m", "euler"),
    schedulers=("flow_matching", "normal"),
    vaes=("qwen-vae",),
    resolutions=("1024x1792", "768x1280", "832x1216"),
    aspect_ratios=("9:16", "1:1"),
    controlnet=(),
    ip_adapters=("style_transfer",),
    depth=(),
    segmentation=(),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
)
_register(
    "gpt-image",
    "GPT Image",
    "gpt_image",
    ModelKind.IMAGE,
    photoreal=93.0,
    diagram=75.0,
    macro_detail=86.0,
    engineering=84.0,
    adherence=94.0,
    vram_mb=12288,
    speed_factor=0.7,
    reliability=0.92,
    steps_range=(10, 30),
    samplers=("dpmpp_2m",),
    schedulers=("normal",),
    vaes=("gpt-image-vae",),
    resolutions=("1024x1792", "832x1216"),
    aspect_ratios=("9:16", "1:1"),
    controlnet=(),
    ip_adapters=(),
    depth=(),
    segmentation=(),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
)
_register(
    "hiredream",
    "HiDream",
    "hiredream",
    ModelKind.IMAGE,
    photoreal=92.0,
    diagram=80.0,
    macro_detail=88.0,
    engineering=87.0,
    adherence=90.0,
    vram_mb=12288,
    speed_factor=0.9,
    reliability=0.94,
    steps_range=(20, 50),
    samplers=("euler", "dpmpp_2m"),
    schedulers=("euler_ancestral", "normal"),
    vaes=("hiredream-vae",),
    resolutions=("832x1216", "1024x1792"),
    aspect_ratios=("9:16", "1:1"),
    controlnet=(),
    ip_adapters=("style_transfer",),
    depth=(),
    segmentation=(),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
)


# ------------------------------------------------------------------ videos --

_register(
    "wan-2-2",
    "WAN 2.2",
    "wan",
    ModelKind.VIDEO,
    photoreal=90.0,
    diagram=60.0,
    macro_detail=84.0,
    engineering=82.0,
    adherence=88.0,
    motion_quality=92.0,
    vram_mb=18432,
    speed_factor=0.7,
    reliability=0.93,
    steps_range=(20, 40),
    samplers=("euler", "dpmpp_2m"),
    schedulers=("flow_matching", "normal"),
    vaes=("wan-vae",),
    resolutions=("832x1216", "1280x768"),
    aspect_ratios=("9:16", "16:9"),
    controlnet=("canny", "depth"),
    ip_adapters=(),
    depth=("monocular",),
    segmentation=(),
    upscalers=("4x_ultrasharp",),
    refiners=("none",),
    animation_backends=("wan_video_2.2",),
)
_register(
    "ltx-video",
    "LTX Video",
    "ltx",
    ModelKind.VIDEO,
    photoreal=84.0,
    diagram=55.0,
    macro_detail=78.0,
    engineering=76.0,
    adherence=82.0,
    motion_quality=86.0,
    vram_mb=14336,
    speed_factor=1.2,
    reliability=0.92,
    steps_range=(25, 50),
    samplers=("dpmpp_2m", "euler"),
    schedulers=("flow_matching", "normal"),
    vaes=("ltx-vae",),
    resolutions=("768x1280", "832x1216"),
    aspect_ratios=("9:16",),
    controlnet=(),
    ip_adapters=(),
    depth=(),
    segmentation=(),
    upscalers=(),
    refiners=("none",),
    animation_backends=("ltx_video",),
)
_register(
    "hunyuan-video",
    "Hunyuan Video",
    "hunyuan",
    ModelKind.VIDEO,
    photoreal=88.0,
    diagram=58.0,
    macro_detail=80.0,
    engineering=78.0,
    adherence=84.0,
    motion_quality=90.0,
    vram_mb=24576,
    speed_factor=0.6,
    reliability=0.90,
    steps_range=(30, 60),
    samplers=("euler", "dpmpp_2m"),
    schedulers=("flow_matching", "normal"),
    vaes=("hyvideo-vae",),
    resolutions=("848x1512", "832x1216"),
    aspect_ratios=("9:16",),
    controlnet=("canny",),
    ip_adapters=(),
    depth=(),
    segmentation=(),
    upscalers=(),
    refiners=("none",),
    animation_backends=("hunyuan_video",),
)
_register(
    "cogvideox",
    "CogVideoX",
    "cogvideo",
    ModelKind.VIDEO,
    photoreal=82.0,
    diagram=50.0,
    macro_detail=76.0,
    engineering=74.0,
    adherence=80.0,
    motion_quality=84.0,
    vram_mb=16384,
    speed_factor=0.9,
    reliability=0.91,
    steps_range=(30, 50),
    samplers=("euler",),
    schedulers=("flow_matching",),
    vaes=("cogvideox-vae",),
    resolutions=("832x1216", "720x1280"),
    aspect_ratios=("9:16",),
    controlnet=(),
    ip_adapters=(),
    depth=(),
    segmentation=(),
    upscalers=(),
    refiners=("none",),
    animation_backends=("cogvideox",),
)
_register(
    "animatediff",
    "AnimateDiff",
    "animatediff",
    ModelKind.VIDEO,
    photoreal=75.0,
    diagram=70.0,
    macro_detail=74.0,
    engineering=72.0,
    adherence=78.0,
    motion_quality=80.0,
    vram_mb=8192,
    speed_factor=1.3,
    reliability=0.95,
    steps_range=(20, 30),
    samplers=("dpmpp_2m", "euler_a"),
    schedulers=("karras", "normal"),
    vaes=("sdxl-vae-fp16-fix",),
    resolutions=("512x896", "768x1280"),
    aspect_ratios=("9:16",),
    controlnet=("canny", "depth", "lineart"),
    ip_adapters=("style_transfer",),
    depth=("monocular",),
    segmentation=(),
    upscalers=(),
    refiners=("none",),
    animation_backends=("animatediff",),
)


class ModelRegistry:
    """The deterministic registry; future models join via register()."""

    def __init__(self, specs: dict[str, ModelSpec] | None = None) -> None:
        self._specs: dict[str, ModelSpec] = dict(specs if specs is not None else MODELS)

    def register(self, spec: ModelSpec) -> None:
        """Add a future model to the registry."""
        if spec.key in self._specs:
            raise ValueError(f"model {spec.key!r} is already registered")
        self._specs[spec.key] = spec

    def get(self, key: str) -> ModelSpec:
        """Fetch a spec, failing loudly on unknown keys."""
        try:
            return self._specs[key]
        except KeyError as exc:
            raise KeyError(f"no model registered under {key!r}") from exc

    def all(self) -> list[ModelSpec]:
        """All models in canonical registry order (ties break by this order)."""
        return [self._specs[key] for key in _MODEL_ORDER if key in self._specs]

    def of_kind(self, kind: ModelKind) -> list[ModelSpec]:
        """All models of one kind, in canonical order."""
        return [spec for spec in self.all() if spec.kind is kind]

    def families(self) -> set[str]:
        return {spec.family for spec in self.all()}


REGISTRY = ModelRegistry()


def model_count() -> tuple[int, int]:
    """(image models, video models) - used by validation tests."""
    images = [spec for spec in REGISTRY.all() if spec.kind is ModelKind.IMAGE]
    videos = [spec for spec in REGISTRY.all() if spec.kind is ModelKind.VIDEO]
    return len(images), len(videos)
