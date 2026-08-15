"""Example: Knowledge Base V2 conversion of "Why Gyroid Infill Is Stronger Than Grid".

Mirrors the current V1 row "Grid vs Gyroid vs Cubic" (Slicer & Print Settings /
Infill) as a structured VisualArchitecture, compiles it through the SDXL
compiler, and prints the legacy V1 prompts side by side with the generated V2
prompts.

Run:  python -m knowledge.compiler.examples.gyroid_v2
"""

from __future__ import annotations

from knowledge.compiler import compile_for_model
from knowledge.visual_architecture import (
    Background,
    Camera,
    CameraAngle,
    CameraDistance,
    CameraHeight,
    ColorPalette,
    Composition,
    CompositionRule,
    Contrast,
    Depth,
    DepthOfField,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    Lighting,
    LightingStyle,
    Material,
    Modality,
    Mood,
    Motion,
    MotionSpeed,
    MotionType,
    NegativeSpace,
    ScaleReference,
    Scene,
    Subject,
    SubjectHierarchy,
    SurfaceFinish,
    TextPosition,
    TextSlot,
    Thumbnail,
    TransitionHint,
    TransitionType,
    VisualArchitecture,
)

TOPIC = "Why Gyroid Infill Is Stronger Than Grid"
WORLD_ID = "pr1me_lab_v1"

LEGACY_PROMPTS: dict[str, str] = {
    "S1": (
        "photograph of three infill cubes cut open, neutral lab lighting, workbench, "
        "medium shot of three infill cubes cut open, neutral lab light, Centered subject, "
        "rule of thirds for screen elements, generous negative space for overlays, "
        "clean technical render, modern engineering lab, precise machined surfaces, "
        "subtle depth of field"
    ),
    "S2": (
        "photograph of a diagram of grid infill, clean engineering visualization on a dark "
        "background, diagram-style shot of grid infill crossing lines, clean viewport light, "
        "Centered subject, rule of thirds for screen elements, generous negative space for "
        "overlays, clean technical render, modern engineering lab, precise machined surfaces, "
        "subtle depth of field"
    ),
    "S3": (
        "photograph of a diagram of cubic infill, clean engineering visualization on a dark "
        "background, diagram-style shot of cubic infill in three axes, clean viewport light, "
        "Centered subject, rule of thirds for screen elements, generous negative space for "
        "overlays, clean technical render, modern engineering lab, precise machined surfaces, "
        "subtle depth of field"
    ),
    "S4": (
        "photograph of a diagram of gyroid infill, clean engineering visualization on a dark "
        "background, diagram-style shot of the gyroid wave structure, clean viewport light, "
        "Centered subject, rule of thirds for screen elements, generous negative space for "
        "overlays, clean technical render, modern engineering lab, precise machined surfaces, "
        "subtle depth of field"
    ),
    "S5": (
        "studio photograph of infill samples on a bench, dark engineering lab, cinematic key "
        "light, wide hero shot of infill samples on a bench, studio key with rim, Centered "
        "subject, rule of thirds for screen elements, generous negative space for overlays, "
        "open framing, clean technical render, modern engineering lab, precise machined "
        "surfaces, subtle depth of field"
    ),
}

LEGACY_THUMBNAIL = (
    "photograph of three cut cubes showing grid, cubic, and gyroid infill on a bench, "
    "hard key light with rim, dark workshop, ultra sharp detail. ultra sharp, high detail, "
    "strong subject contrast, bold readable composition, professional YouTube thumbnail "
    "style, vertical 9:16"
)

_CUBE_SUFFIX = ["FDM extrusion", "0.4 mm brass nozzle"]


def _grid_cube() -> Subject:
    return Subject(
        entity="grid infill cube",
        description="cut-open cube with rectilinear grid lines crossing in one plane",
        state="sliced open, infill exposed",
        materials=[Material.PLA],
        surface_finish=[SurfaceFinish.LAYER_LINES],
        manufacturing_details=_CUBE_SUFFIX,
        visible_geometry=["crossing lines in one horizontal plane", "square 0.30 mm cells"],
    )


def _cubic_cube() -> Subject:
    return Subject(
        entity="cubic infill cube",
        description="cut-open cube with cubic cells stacked in three axes",
        state="sliced open, infill exposed",
        materials=[Material.PLA],
        surface_finish=[SurfaceFinish.LAYER_LINES],
        manufacturing_details=_CUBE_SUFFIX,
        visible_geometry=["stacked cube cells in all three axes", "vertical load paths"],
    )


def _gyroid_cube() -> Subject:
    return Subject(
        entity="gyroid infill cube",
        description=(
            "cut-open cube exposing a continuous gyroid lattice with smooth "
            "interconnected internal cells"
        ),
        state="sliced open along the center plane, lattice exposed",
        materials=[Material.PLA],
        surface_finish=[SurfaceFinish.LAYER_LINES, SurfaceFinish.SMOOTH],
        manufacturing_details=_CUBE_SUFFIX + ["gyroid minimal surface geometry"],
        visible_geometry=["smooth curved lattice sheets", "interconnected cells", "no sharp corners"],
    )


def _bench_lighting() -> Lighting:
    return Lighting(
        direction=LightDirection.SIDE,
        style=LightingStyle.RAKING,
        practical_sources=["bench lamp"],
        key_color="neutral",
    )


def _dark_palette() -> ColorPalette:
    return ColorPalette(
        base="dark slate",
        accent="natural PLA",
        note="cube colors must read as real filament",
    )


def build_gyroid_architecture() -> VisualArchitecture:
    trio = Subject(
        entity="set of three cut-open infill cubes",
        description="PLA cubes sliced open along the center plane to expose their infill",
        state="on a dark workbench",
        materials=[Material.PLA],
        surface_finish=[SurfaceFinish.LAYER_LINES],
        manufacturing_details=_CUBE_SUFFIX,
        visible_geometry=[
            "grid cross lines",
            "stacked cubic cells",
            "continuous gyroid lattice with smooth interconnected internal cells",
        ],
    )

    s1 = Scene(
        scene_id="S1",
        modality=Modality.CROSS_SECTION,
        primary_subject=trio,
        secondary_subjects=[],
        subject_hierarchy=SubjectHierarchy(
            primary=trio.entity,
            background="workbench",
            focus_object=trio.entity,
        ),
        engineering_goal="Hook: three cubes",
        teaching_goal="Same shell, three insides",
        visual_focus="the three cut faces side by side",
        camera=Camera(
            distance=CameraDistance.MEDIUM,
            angle=CameraAngle.SLIGHTLY_LOW,
            lens=Lens.STANDARD_35,
            framing=Framing.CENTER_ROW,
            height=CameraHeight.TABLE,
        ),
        composition=Composition(
            rule=CompositionRule.CENTER_ROW,
            emphasis="the three infill patterns in a row",
            negative_space=NegativeSpace.OVERLAY_TOP,
        ),
        depth=Depth(
            foreground=None,
            midground=trio.entity,
            background="workbench",
            dof=DepthOfField.MEDIUM,
        ),
        lighting=_bench_lighting(),
        color_palette=_dark_palette(),
        mood=Mood.COMPARATIVE,
        motion=Motion(
            type=MotionType.PAN,
            path="left to right across the three cut faces",
            speed=MotionSpeed.SLOW,
        ),
        scale_reference=ScaleReference(entity="US quarter coin", size="25 mm"),
        objects_to_avoid=["people", "hands", "text", "logos", "fused infill geometry"],
        consistency_tags=["gyroid_infill_cube_set", "pr1me_lab_bench"],
        branding_tags=["pr1me_overlay_top"],
        transition_hint=TransitionHint(type=TransitionType.CUT),
        scene_importance=4,
    )

    s2 = Scene(
        scene_id="S2",
        modality=Modality.DIAGRAM,
        primary_subject=_grid_cube(),
        secondary_subjects=[],
        subject_hierarchy=SubjectHierarchy(
            primary="grid infill cube",
            background="dark viewport",
            focus_object="grid infill cube",
        ),
        engineering_goal="The grid",
        teaching_goal="Fast, simple, planar",
        visual_focus="the crossing line pattern",
        camera=Camera(
            distance=CameraDistance.CLOSE,
            angle=CameraAngle.EYE,
            lens=Lens.STANDARD_35,
            framing=Framing.SUBJECT_CENTER,
            height=CameraHeight.EYE_LEVEL,
        ),
        composition=Composition(
            rule=CompositionRule.CENTERED,
            emphasis="crossing grid lines",
            negative_space=NegativeSpace.OVERLAY_TOP,
        ),
        depth=Depth(
            foreground=None,
            midground="grid line lattice",
            background="viewport",
            dof=DepthOfField.FULL,
        ),
        environment="viewport",
        lighting=Lighting(
            direction=LightDirection.KEY,
            style=LightingStyle.STUDIO,
            key_color="neutral",
        ),
        color_palette=ColorPalette(base="graphite", accent="white", note="flat diagram tones"),
        mood=Mood.CLINICAL,
        motion=Motion(type=MotionType.STATIC),
        objects_to_avoid=["glow", "photo shadows", "people", "hands"],
        consistency_tags=["gyroid_infill_cube_set", "grid_infill_diagram"],
        transition_hint=TransitionHint(type=TransitionType.CUT),
        scene_importance=3,
    )

    s3 = Scene(
        scene_id="S3",
        modality=Modality.DIAGRAM,
        primary_subject=_cubic_cube(),
        secondary_subjects=[],
        subject_hierarchy=SubjectHierarchy(
            primary="cubic infill cube",
            background="dark viewport",
            focus_object="cubic infill cube",
        ),
        engineering_goal="The cubic",
        teaching_goal="Load from any side",
        visual_focus="the stacked cubic cells",
        camera=Camera(
            distance=CameraDistance.CLOSE,
            angle=CameraAngle.SLIGHTLY_LOW,
            lens=Lens.STANDARD_35,
            framing=Framing.SUBJECT_CENTER,
            height=CameraHeight.EYE_LEVEL,
        ),
        composition=Composition(
            rule=CompositionRule.CENTERED,
            emphasis="stacked cubic cells with load arrows",
            negative_space=NegativeSpace.OVERLAY_TOP,
        ),
        depth=Depth(
            foreground=None,
            midground="cubic cell lattice",
            background="viewport",
            dof=DepthOfField.FULL,
        ),
        environment="viewport",
        lighting=Lighting(
            direction=LightDirection.KEY,
            style=LightingStyle.STUDIO,
            key_color="neutral",
        ),
        color_palette=ColorPalette(base="graphite", accent="white", note="flat diagram tones"),
        mood=Mood.CLINICAL,
        motion=Motion(type=MotionType.STATIC),
        objects_to_avoid=["glow", "photo shadows", "people", "hands"],
        consistency_tags=["gyroid_infill_cube_set", "cubic_infill_diagram"],
        transition_hint=TransitionHint(type=TransitionType.CUT),
        scene_importance=3,
    )

    s4 = Scene(
        scene_id="S4",
        modality=Modality.DIAGRAM,
        primary_subject=_gyroid_cube(),
        secondary_subjects=[],
        subject_hierarchy=SubjectHierarchy(
            primary="gyroid infill cube",
            background="dark viewport",
            focus_object="gyroid infill cube",
        ),
        engineering_goal="The gyroid",
        teaching_goal="Smooth wave, shear resistant",
        visual_focus="the curved lattice waves",
        camera=Camera(
            distance=CameraDistance.CLOSE,
            angle=CameraAngle.SLIGHTLY_LOW,
            lens=Lens.STANDARD_35,
            framing=Framing.SUBJECT_CENTER,
            height=CameraHeight.EYE_LEVEL,
        ),
        composition=Composition(
            rule=CompositionRule.CENTERED,
            emphasis="the continuous wave sheets",
            negative_space=NegativeSpace.OVERLAY_TOP,
        ),
        depth=Depth(
            foreground=None,
            midground="gyroid lattice",
            background="viewport",
            dof=DepthOfField.FULL,
        ),
        environment="viewport",
        lighting=Lighting(
            direction=LightDirection.KEY,
            style=LightingStyle.STUDIO,
            key_color="neutral",
        ),
        color_palette=ColorPalette(base="graphite", accent="white", note="flat diagram tones"),
        mood=Mood.CLINICAL,
        motion=Motion(type=MotionType.STATIC),
        objects_to_avoid=["glow", "photo shadows", "people", "hands"],
        consistency_tags=["gyroid_infill_cube_set", "gyroid_wave_diagram"],
        transition_hint=TransitionHint(type=TransitionType.CUT),
        scene_importance=4,
        thumbnail_candidate=True,
    )

    s5 = Scene(
        scene_id="S5",
        modality=Modality.PHOTOREAL,
        primary_subject=Subject(
            entity="infill sample set",
            description="three cut-open infill cubes on a workbench",
            state="finished prints, natural PLA colors",
            materials=[Material.PLA],
            surface_finish=[SurfaceFinish.LAYER_LINES],
            manufacturing_details=_CUBE_SUFFIX,
            visible_geometry=["grid cross lines", "cubic cells", "gyroid waves"],
        ),
        secondary_subjects=[
            Subject(
                entity="gyroid infill cube",
                description="cut-open cube with a continuous gyroid lattice",
                materials=[Material.PLA],
            )
        ],
        subject_hierarchy=SubjectHierarchy(
            primary="infill sample set",
            secondary=["gyroid infill cube"],
            background="dark lab",
            focus_object="gyroid infill cube",
        ),
        engineering_goal="Takeaway",
        teaching_goal="Pick by the load",
        visual_focus="the gyroid cube leading the set",
        camera=Camera(
            distance=CameraDistance.WIDE,
            angle=CameraAngle.SLIGHTLY_LOW,
            lens=Lens.STANDARD_35,
            framing=Framing.SUBJECT_LEFT,
            height=CameraHeight.EYE_LEVEL,
        ),
        composition=Composition(
            rule=CompositionRule.LEFT_HEAVY,
            emphasis="the three cubes receding to the right",
            negative_space=NegativeSpace.OVERLAY_LEFT,
        ),
        depth=Depth(
            foreground="bench edge",
            midground="infill sample set",
            background="dark lab",
            dof=DepthOfField.SHALLOW,
        ),
        environment="dark lab",
        lighting=Lighting(
            direction=LightDirection.RIM,
            style=LightingStyle.STUDIO,
            practical_sources=["bench lamp"],
            key_color="neutral",
        ),
        color_palette=_dark_palette(),
        mood=Mood.PRECISE,
        motion=Motion(type=MotionType.ORBIT, speed=MotionSpeed.SLOW),
        objects_to_avoid=["people", "hands", "text", "logos"],
        consistency_tags=["gyroid_infill_cube_set", "pr1me_lab_bench"],
        transition_hint=TransitionHint(type=TransitionType.FADE),
        scene_importance=5,
        thumbnail_candidate=True,
    )

    thumbnail = Thumbnail(
        modality=Modality.PHOTOREAL,
        primary_subject=Subject(
            entity="gyroid infill cube",
            description="cut-open cube with a continuous gyroid lattice",
            state="on a dark bench, cut face toward the lens",
            materials=[Material.PLA],
            surface_finish=[SurfaceFinish.SMOOTH],
            manufacturing_details=["FDM extrusion"],
            visible_geometry=["smooth interconnected lattice cells"],
        ),
        secondary_subjects=[
            Subject(
                entity="grid infill cube",
                description="cut-open cube behind",
                materials=[Material.PLA],
            ),
            Subject(
                entity="cubic infill cube",
                description="cut-open cube behind",
                materials=[Material.PLA],
            ),
        ],
        background=Background(environment="dark workshop blur", depth=DepthOfField.SHALLOW),
        focus_object="gyroid infill cube",
        composition=Composition(
            rule=CompositionRule.CENTERED,
            emphasis="gyroid cube leading, grid and cubic cubes behind",
            negative_space=NegativeSpace.NONE,
            note="bold readable at 60 percent zoom",
        ),
        text_slot=TextSlot(
            string="PICK BY THE LOAD",
            position=TextPosition.UPPER_THIRD,
            max_chars=16,
            contrast=Contrast.HIGH,
        ),
        camera=Camera(
            distance=CameraDistance.CLOSE,
            angle=CameraAngle.SLIGHTLY_LOW,
            lens=Lens.MACRO_100,
            framing=Framing.SUBJECT_CENTER,
            height=CameraHeight.TABLE,
        ),
        lighting=Lighting(
            direction=LightDirection.SIDE,
            style=LightingStyle.RAKING,
            key_color="neutral",
        ),
        color_palette=_dark_palette(),
        mood=Mood.COMPARATIVE,
        exclude=["people", "hands", "watermarks", "fused lattice geometry"],
        consistency_tags=["gyroid_infill_cube_set"],
        branding_tags=["pr1me_orange_overlay_zone"],
    )

    return VisualArchitecture(
        version="2.0",
        world_id=WORLD_ID,
        engineering_domain=EngineeringDomain.FDM,
        modality=Modality.PHOTOREAL,
        scenes=[s1, s2, s3, s4, s5],
        thumbnail=thumbnail,
    )


def _why_superior() -> str:
    return (
        "\nWhy the generated prompt is superior:\n"
        "  1. Hierarchy: the cut-open cube set is the primary subject with an explicit focus\n"
        "     object; nothing competes equally. The V1 prompt lists three bare nouns\n"
        "     ('grid cube', 'cubic cube', 'gyroid cube') with no role assignment.\n"
        "  2. Modality: V1 says 'photograph of a diagram'; the spec declares CROSS_SECTION\n"
        "     and DIAGRAM, so the compiler picks the correct cutaway/diagram syntax and\n"
        "     adds diagram-appropriate negatives (photographic shadows, 3d render).\n"
        "  3. Engineering detail: 'continuous gyroid lattice with smooth interconnected\n"
        "     internal cells' comes verbatim from the spec instead of the vague 'gyroid\n"
        "     wave structure'. Materials, surface finish, and manufacturing detail are\n"
        "     structured fields, so they survive compilation.\n"
        "  4. No boilerplate: the repeated 'clean technical render, modern engineering\n"
        "     lab, precise machined surfaces, subtle depth of field' and the duplicated\n"
        "     'neutral lab lighting, ... neutral lab light' clauses are gone. Quality\n"
        "     tokens live in the SDXL profile, one place, tunable per model.\n"
        "  5. Model-agnostic: the same spec compiles to FLUX/GPT Image paragraphs later;\n"
        "     V1 prompts are SDXL-bound prose with no semantic structure to reuse.\n"
        "  6. Semantics-first negatives: excludes ('fused infill geometry') are declared\n"
        "     once and merged with the model's negative tokens by the compiler."
    )


def main() -> None:
    architecture = build_gyroid_architecture()
    compiled = compile_for_model(architecture, "sdxl", topic=TOPIC)

    print(f"Knowledge Base V2 conversion example: {TOPIC}\n")
    for scene in architecture.scenes:
        legacy = LEGACY_PROMPTS[scene.scene_id]
        generated = compiled.scenes[scene.scene_id]
        print(f"--- Scene {scene.scene_id} ({scene.modality.value}) ---")
        print(f"LEGACY   (V1 CSV):\n  {legacy}")
        print(f"GENERATED (V2 SDXL):\n  {generated.prompt}")
        print(f"  negative: {generated.negative_prompt}\n")

    print("--- Thumbnail ---")
    print(f"LEGACY   (V1 CSV):\n  {LEGACY_THUMBNAIL}")
    print(f"GENERATED (V2 SDXL):\n  {compiled.thumbnail.prompt}")
    print(f"  negative: {compiled.thumbnail.negative_prompt}")
    print(_why_superior())


if __name__ == "__main__":
    main()
