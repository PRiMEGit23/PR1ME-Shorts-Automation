"""Stage 1: Knowledge Extractor.

Distills the approved narration into engineering knowledge: concepts,
mechanisms, objects, materials, processes, scale, physics, motion,
relationships, critical visual elements, and forbidden inaccuracies.

The deterministic core scans the narration against a canonical engineering
domain lexicon (substring matching on word boundaries) and clusters the hits by
category. When a provider is configured, the LLM template in
:mod:`pr1me.visual_architecture.prompts` produces the same contract and the
deterministic core validates its substance (falling back when it is empty).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pr1me.visual_architecture._common import (
    VisualContext,
    llm_or_fallback,
    make_logger,
    model_dump_safe,
    script_text,
)
from pr1me.visual_architecture.contracts import (
    KnowledgeOutput,
    Mechanism,
    ScaleDescriptor,
    VisualArchitectureInput,
)
from pr1me.visual_architecture.prompts import KNOWLEDGE_EXTRACTOR_PROMPT

__all__ = ["KnowledgeExtractor", "domain_lexicon", "match_terms"]

#: Canonical engineering vocabulary used by the deterministic core, grouped by
#: knowledge category. Terms are matched on word boundaries, so "nozzle"
#: matches "nozzle" and "nozzles" but not "nozzlehead" misuse.
_DOMAIN_LEXICON: dict[str, dict[str, tuple[str, ...]]] = {
    "objects": {
        "extruder": ("extruder", "extrusion head"),
        "nozzle": ("nozzle", "print nozzle"),
        "build plate": ("build plate", "buildplate", "print bed", "bed surface"),
        "hotend": ("hotend", "hot end", "heater block"),
        "layer": ("layer", "layer line"),
        "stepper motor": ("stepper motor", "stepper", "stepper driver"),
        "lead screw": ("lead screw", "leadscrew", "threaded rod"),
        "gear": ("gear", "gears"),
        "bearing": ("bearing", "bearings", "linear rail", "rails"),
        "frame": ("frame", "gantry"),
        "fan": ("fan", "part cooling fan", "blower"),
        "heat sink": ("heat sink", "heatsink", "radiator"),
        "thermistor": ("thermistor", "temperature sensor"),
        "filament": ("filament", "filament spool", "spool"),
        "shaft": ("shaft", "drive shaft"),
        "piston": ("piston", "cylinder"),
        "valve": ("valve", "valves"),
        "chamber": ("chamber", "enclosure"),
        "cutting tool": ("cutting tool", "cutter", "drill bit", "end mill"),
        "mold": ("mold", "mould", "die"),
        "fixture": ("fixture", "clamp", "vise"),
    },
    "materials": {
        "PLA": ("pla",),
        "PETG": ("petg",),
        "ABS": ("abs",),
        "ASA": ("asa",),
        "nylon": ("nylon", "polyamide"),
        "carbon fiber": ("carbon fiber", "carbon fibre", "cf nylon"),
        "aluminum": ("aluminum", "aluminium", "alu"),
        "steel": ("steel", "stainless steel"),
        "copper": ("copper",),
        "brass": ("brass",),
        "titanium": ("titanium",),
        "silicone": ("silicone",),
        "glass": ("glass", "glass bed"),
        "polycarbonate": ("polycarbonate", "pc filament"),
        "TPU": ("tpu",),
        "composite": ("composite", "composites"),
    },
    "processes": {
        "extrusion": ("extrusion", "extrude", "extruding"),
        "injection molding": ("injection molding", "injection moulding", "molding"),
        "CNC machining": ("cnc", "cnc machining", "machining", "milling", "turning"),
        "welding": ("welding", "weld"),
        "soldering": ("soldering", "solder"),
        "annealing": ("annealing", "annealed"),
        "sintering": ("sintering", "sintered"),
        "casting": ("casting", "cast"),
        "laser cutting": ("laser cutting", "laser cut"),
        "3d printing": ("3d printing", "3d print", "3d-printing", "additive manufacturing"),
        "slicing": ("slicing", "slicer"),
        "calibration": ("calibration", "calibrate", "leveling", "bed leveling"),
        "post-processing": ("post-processing", "post processing", "finishing"),
        "assembly": ("assembly", "assembling", "assembled"),
    },
    "physics": {
        "friction": ("friction", "frictional"),
        "adhesion": ("adhesion", "adhesive", "bond", "bonding"),
        "cooling": ("cooling", "cool", "cooled", "fan speed"),
        "thermal expansion": ("thermal expansion", "shrinkage", "shrink", "contraction"),
        "tension": ("tension", "tensile"),
        "compression": ("compression", "compressive", "squish"),
        "shear": ("shear", "shearing"),
        "stress": ("stress", "strain", "load bearing"),
        "torque": ("torque", "rotational force"),
        "gravity": ("gravity", "gravitational"),
        "surface tension": ("surface tension", "capillary"),
        "viscosity": ("viscosity", "viscous", "flow rate"),
        "melting point": ("melting point", "melt", "melts", "glass transition"),
        "warping": ("warping", "warp", "curling", "elephant foot"),
        "crystallization": ("crystallization", "crystalline"),
    },
    "motion": {
        "rotation": ("rotation", "rotat", "spin", "spinning", "orbit"),
        "translation": ("translation", "move", "moving", "travel", "slide"),
        "oscillation": ("oscillation", "oscillat", "vibration", "vibrat"),
        "pushing": ("push", "pushing", "press", "pressing", "squish"),
        "pulling": ("pull", "pulling", "tension pulling"),
        "feeding": ("feed", "feeding", "feeder"),
        "layering": ("deposit", "depositing", "layering", "layer-by-layer"),
    },
    "concepts": {
        "layer adhesion": ("layer adhesion", "adhesion between layers"),
        "overhang": ("overhang", "overhangs", "steep angle"),
        "tolerance": ("tolerance", "clearance", "precision fit"),
        "repeatability": ("repeatability", "repeatable", "consistency of prints"),
        "bed leveling": ("bed leveling", "level the bed", "z offset", "z-offset"),
        "first layer": ("first layer", "first-layer", "first layer squish"),
        "bridging": ("bridging", "bridge"),
        "stringing": ("stringing", "string"),
        "infill": ("infill", "infill pattern"),
        "perimeter": ("perimeter", "perimeters", "walls of the print"),
        "flow calibration": ("flow calibration", "flow rate", "e-steps", "extrusion multiplier"),
        "retraction": ("retraction", "retract"),
        "supports": ("supports", "support material"),
        "dimensional accuracy": ("dimensional accuracy", "dimensional", "measured dimensions"),
    },
}

#: Longest-first ordering so "build plate" wins over "plate" style overlaps.
_TERM_ORDER: list[tuple[str, str]] = sorted(
    (
        (term, category)
        for category, terms in _DOMAIN_LEXICON.items()
        for term, aliases in terms.items()
        for _ in aliases
    ),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

#: Global hygiene list injected into every knowledge block.
_FORBIDDEN_BASE = (
    "no glowing circuits",
    "no sci-fi or fantasy hardware",
    "no impossible mechanisms",
    "no invented materials",
    "no floating or levitating parts",
    "no cartoon or anime styling",
    "no exaggerated proportions",
    "no visible text or logos on the subject",
)

#: Scale description template used when the narration does not name one.
_SCALE_FALLBACK = "macro to close-up detail range of the primary mechanism"


def domain_lexicon() -> dict[str, dict[str, tuple[str, ...]]]:
    """Return the canonical domain lexicon (immutable by convention)."""
    return {category: dict(terms) for category, terms in _DOMAIN_LEXICON.items()}


def match_terms(text: str, categories: Iterable[str] | None = None) -> list[tuple[str, str]]:
    """Return ``(term, category)`` hits found in ``text`` (word-boundary match).

    Terms are matched longest-first against the lower-cased text. A term only
    hits when it appears as a whole word (or common plural/inflected form), so
    unrelated engineering vocabulary cannot leak in.
    """
    haystack = f" {text.lower()} "
    wanted = set(categories) if categories is not None else set(_DOMAIN_LEXICON)
    hits: list[tuple[str, str]] = []
    for term, category in _TERM_ORDER:
        if category not in wanted:
            continue
        for alias in _DOMAIN_LEXICON[category][term]:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", haystack):
                hits.append((term, category))
                break
    return hits


class KnowledgeExtractor:
    """Stage 1 engine: narration -> engineering knowledge block."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("knowledge_extractor")

    async def run(self, payload: VisualArchitectureInput) -> KnowledgeOutput:
        """Extract the knowledge block, preferring the LLM when configured."""
        self._logger.info(
            "event=knowledge_extractor.started",
            topic=payload.topic,
            word_count=payload.word_count,
        )
        knowledge = await llm_or_fallback(
            context=self._context,
            logger=self._logger,
            template=KNOWLEDGE_EXTRACTOR_PROMPT,
            variables=model_dump_safe(payload),
            output_model=KnowledgeOutput,
            fallback=lambda: self._deterministic(payload),
            predicate=lambda value: value.is_substantive(),
        )
        self._logger.info(
            "event=knowledge_extractor.completed",
            n_concepts=len(knowledge.concepts),
            n_objects=len(knowledge.objects),
            n_materials=len(knowledge.materials),
            n_mechanisms=len(knowledge.mechanisms),
        )
        return knowledge

    # ------------------------------------------------------------- internals --

    @staticmethod
    def _deterministic(payload: VisualArchitectureInput) -> KnowledgeOutput:
        text = script_text(
            payload.topic,
            hook=payload.hook,
            explanation=payload.explanation,
            practical_insight=payload.practical_insight,
            ending=payload.ending,
        )
        hits = match_terms(text)

        concepts = _unique(term for term, category in hits if category == "concepts")
        objects = _unique(term for term, category in hits if category == "objects")
        materials = _unique(term for term, category in hits if category == "materials")
        processes = _unique(term for term, category in hits if category == "processes")
        physics = _unique(term for term, category in hits if category == "physics")
        motion = _unique(term for term, category in hits if category == "motion")

        mechanisms = KnowledgeExtractor._derive_mechanisms(objects, processes, physics, concepts)
        relationships = KnowledgeExtractor._derive_relationships(objects, processes, physics)
        scale_reference = KnowledgeExtractor._pick_scale_reference(objects, payload.topic)
        critical = KnowledgeExtractor._critical_elements(concepts, objects, mechanisms)

        if not concepts and not objects and not mechanisms:
            concepts = ["engineering process"]

        return KnowledgeOutput(
            concepts=concepts,
            mechanisms=mechanisms,
            objects=objects,
            materials=materials,
            processes=processes,
            scale=ScaleDescriptor(
                reference_object=scale_reference,
                description=_SCALE_FALLBACK,
            ),
            physics=physics,
            motion=motion,
            relationships=relationships,
            critical_visual_elements=critical,
            forbidden_inaccuracies=list(_FORBIDDEN_BASE),
        )

    @staticmethod
    def _derive_mechanisms(
        objects: list[str],
        processes: list[str],
        physics: list[str],
        concepts: list[str],
    ) -> list[Mechanism]:
        mechanisms: list[Mechanism] = []
        driver = next(iter(objects), "")
        process = next(iter(processes), "")
        if driver and process:
            mechanisms.append(
                Mechanism(
                    name=f"{driver} {process}",
                    purpose=f"The narration explains how the {driver} works through {process}.",
                    physics_principles=physics[:3],
                )
            )
        if concepts:
            mechanisms.append(
                Mechanism(
                    name=concepts[0],
                    purpose=f"The narration teaches {concepts[0]} and why it matters.",
                    physics_principles=physics[:2],
                )
            )
        return mechanisms

    @staticmethod
    def _derive_relationships(
        objects: list[str],
        processes: list[str],
        physics: list[str],
    ) -> list[str]:
        relationships: list[str] = []
        if objects and physics:
            relationships.append(f"{objects[0]} is governed by {physics[0]}")
        if objects and processes:
            relationships.append(f"{objects[0]} is produced by {processes[0]}")
        return relationships

    @staticmethod
    def _critical_elements(
        concepts: list[str],
        objects: list[str],
        mechanisms: list[Mechanism],
    ) -> list[str]:
        elements: list[str] = []
        if mechanisms:
            elements.append(f"the {mechanisms[0].name} interface")
        if objects:
            elements.append(f"the {objects[0]}")
        if concepts:
            elements.append(f"the {concepts[0]} state")
        return elements[:4]

    @staticmethod
    def _pick_scale_reference(objects: list[str], topic: str) -> str:
        if objects:
            return objects[0]
        if topic.strip():
            return topic.strip()
        return "engineering mechanism"


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
