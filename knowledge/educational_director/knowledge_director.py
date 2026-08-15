"""Knowledge Director: extracts the teaching-relevant facts from a curated row.

Pure, deterministic information extraction. It decides WHAT matters (concept,
misconception, phenomenon, visualization difficulty, objective, takeaway,
prior knowledge) without deciding HOW to show it - that is the Educational
Director's job.

The canonical input is the raw CSV row (the exact record produced by
build_knowledge_csv.py), because two teaching-critical fields (learning
objective, common misconceptions) are not modeled on KnowledgeBaseRow. The
modeled subset is still consumed through KnowledgeBaseRow so the pipeline
stays consistent with the rest of the knowledge base.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from knowledge.educational_director.educational_models import (
    EngineeringDomainHint,
    KnowledgeDirectorResult,
)
from knowledge.visual_intelligence.visual_intelligence import KnowledgeBaseRow


def _json_list(raw: str) -> list[str]:
    value = raw.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _first_sentence(text: str) -> str:
    for separator in (". ", ".", " - "):
        if separator in text:
            return text.split(separator)[0].strip()
    return text.strip()


def _last_sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    sentences = [s.strip() for s in cleaned.replace(" - ", ". ").split(".") if s.strip()]
    return sentences[-1] if sentences else cleaned


def _after_rule_of_thumb(text: str) -> str:
    marker = "rule of thumb"
    index = text.lower().find(marker)
    if index == -1:
        return ""
    tail = text[index + len(marker):].strip(" :;.,")
    return _first_sentence(tail) or tail


_CATEGORY_DOMAINS: tuple[tuple[str, EngineeringDomainHint], ...] = (
    ("slicer & print settings", EngineeringDomainHint.FDM_PRINTING),
    ("printer hardware", EngineeringDomainHint.FDM_PRINTING),
    ("advanced & industrial am", EngineeringDomainHint.INDUSTRIAL_AM),
    ("mechanical engineering", EngineeringDomainHint.MECHANISMS),
    ("materials science", EngineeringDomainHint.MATERIALS_SCIENCE),
    ("thermodynamics", EngineeringDomainHint.THERMODYNAMICS),
    ("metrology", EngineeringDomainHint.METROLOGY),
    ("tooling", EngineeringDomainHint.TOOLING),
    ("design cad", EngineeringDomainHint.DESIGN_CAD),
    ("finishing", EngineeringDomainHint.FINISHING),
    ("safety", EngineeringDomainHint.SAFETY),
    ("workshop", EngineeringDomainHint.WORKSHOP),
    ("sheet metal", EngineeringDomainHint.SHEET_METAL),
    ("electronics", EngineeringDomainHint.ELECTRONICS),
    ("cnc machining", EngineeringDomainHint.CNC_MACHINING),
)

_SCAN_DOMAINS: tuple[tuple[str, EngineeringDomainHint], ...] = (
    ("injection", EngineeringDomainHint.INJECTION_MOLDING),
    ("molding", EngineeringDomainHint.INJECTION_MOLDING),
    ("mold", EngineeringDomainHint.INJECTION_MOLDING),
    ("cnc", EngineeringDomainHint.CNC_MACHINING),
    ("machining", EngineeringDomainHint.CNC_MACHINING),
    ("sheet metal", EngineeringDomainHint.SHEET_METAL),
    ("pcb", EngineeringDomainHint.ELECTRONICS),
    ("electronics", EngineeringDomainHint.ELECTRONICS),
    ("gear", EngineeringDomainHint.MECHANISMS),
    ("mechanism", EngineeringDomainHint.MECHANISMS),
    ("alloy", EngineeringDomainHint.MATERIALS_SCIENCE),
    ("filament", EngineeringDomainHint.MATERIALS_SCIENCE),
    ("thermal", EngineeringDomainHint.THERMODYNAMICS),
    ("heat", EngineeringDomainHint.THERMODYNAMICS),
    ("caliper", EngineeringDomainHint.METROLOGY),
    ("tolerance", EngineeringDomainHint.METROLOGY),
    ("cad", EngineeringDomainHint.DESIGN_CAD),
)


def _scan(text: str) -> EngineeringDomainHint | None:
    for token, domain in _SCAN_DOMAINS:
        if token in text:
            return domain
    return None


def infer_domain(
    category: str,
    subcategory: str,
    keywords: Sequence[str],
) -> EngineeringDomainHint:
    """Infer the coarse engineering domain of a curated row, deterministically.

    Category wins (it is the curatorial label), then a token scan over
    category + subcategory + keywords, then a neutral fallback.
    """
    combined = f"{category} {subcategory} ".lower()
    for token, domain in _CATEGORY_DOMAINS:
        if token in combined:
            return domain
    scan_text = f"{combined} {' '.join(keywords)}".lower()
    scanned = _scan(scan_text)
    if scanned is not None:
        return scanned
    return EngineeringDomainHint.DESIGN_CAD


_DOMAIN_PRIOR_KNOWLEDGE: dict[EngineeringDomainHint, tuple[str, ...]] = {
    EngineeringDomainHint.FDM_PRINTING: (
        "what a 3D printer nozzle is",
        "layer-by-layer construction",
    ),
    EngineeringDomainHint.RESIN_AM: ("resin curing basics", "layer-by-layer construction"),
    EngineeringDomainHint.INDUSTRIAL_AM: (
        "why AM suits low volumes",
        "what a build platform is",
    ),
    EngineeringDomainHint.CNC_MACHINING: (
        "what a cutting tool is",
        "subtractive vs additive",
    ),
    EngineeringDomainHint.INJECTION_MOLDING: (
        "why tooling is a one-time cost",
        "what a closed mold is",
    ),
    EngineeringDomainHint.SHEET_METAL: ("what a bend radius is", "material thickness"),
    EngineeringDomainHint.ELECTRONICS: ("what a circuit is", "voltage vs current"),
    EngineeringDomainHint.MECHANISMS: (
        "what a gear tooth is",
        "the torque vs speed trade-off",
    ),
    EngineeringDomainHint.MATERIALS_SCIENCE: (
        "atoms and bonding basics",
        "why properties vary with structure",
    ),
    EngineeringDomainHint.THERMODYNAMICS: (
        "heat flows from hot to cold",
        "energy is conserved",
    ),
    EngineeringDomainHint.METROLOGY: ("what a measurement is", "units and error"),
    EngineeringDomainHint.TOOLING: ("what a fixture is", "why tooling costs money"),
    EngineeringDomainHint.DESIGN_CAD: ("what a CAD model is", "parametric editing"),
    EngineeringDomainHint.FINISHING: ("what surface finish is", "why finish matters"),
    EngineeringDomainHint.SAFETY: ("basic workshop safety", "why guards exist"),
    EngineeringDomainHint.WORKSHOP: ("basic workshop intuition",),
}

_CONCEPT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("isotropic strength from triply periodic infill", ("gyroid", "infill", "isotropic")),
    ("the molding cycle and tooling economics", ("molding cycle", "injection", "tooling cost")),
    ("load splitting across planet teeth", ("planetary", "planet teeth", "epicyclic")),
    ("gear ratio from tooth counts", ("gear ratio", "reduction ratio")),
    ("involute tooth geometry", ("involute", "gear teeth")),
    ("layer height resolution vs strength trade", ("layer height", "layer resolution")),
    ("wall thickness and strength", ("wall thickness", "perimeter")),
    ("bed adhesion and warping", ("bed adhesion", "warp", "first layer")),
    ("print speed vs quality", ("print speed", "quality")),
    ("bridging and overhang limits", ("bridging", "overhang")),
    ("support structure strategy", ("support", "overhang")),
    ("draft angle and undercut limits", ("draft angle", "undercut")),
    ("shrinkage and tolerance", ("shrinkage", "tolerance")),
    ("filament drying and moisture", ("moisture", "drying", "filament")),
    ("nozzle wear and materials", ("nozzle wear", "abrasive")),
    ("heat creep and hotend design", ("heat creep", "hotend")),
    ("retraction and stringing", ("retraction", "stringing")),
    ("the stress concentration effect", ("stress concentration", "stress riser")),
    ("the lever and torque trade", ("lever", "torque")),
    ("energy flow in a thermal system", ("heat flow", "thermal")),
)

_CONCEPT_FALLBACK = (
    "the physics that makes the difference between a good and a bad outcome"
)


def _concept_for(combined: str) -> str:
    for phrase, tokens in _CONCEPT_RULES:
        if any(token in combined for token in tokens):
            return phrase
    return _CONCEPT_FALLBACK


_PHENOMENON_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stress distribution through a lattice", ("isotropic", "infill", "stress distribution")),
    ("the injection molding cycle", ("molding cycle", "injection")),
    ("load sharing across planet teeth", ("planet", "epicyclic")),
    ("the meshing of gear teeth", ("gear teeth", "mesh", "involute")),
    ("thermal contraction during cooling", ("warp", "shrink", "cooling")),
    ("layer bonding strength", ("layer adhesion", "z-axis")),
    ("moisture absorption in filament", ("moisture", "drying")),
)

_DIFFICULT_VISUAL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stress distribution inside the volume", ("isotropic", "stress", "load path")),
    ("the sequence inside a closed steel mold", ("mold cavity", "injection", "ejector")),
    ("sun, ring, and planets moving simultaneously", ("planetary", "sun gear", "carrier")),
    ("internal structure hidden behind solid surfaces", ("internal", "inside", "hidden")),
    ("tooth surfaces rolling without sliding", ("involute", "gear teeth", "mesh")),
    ("the scale of a machined feature", ("micron", "tolerance", "dimension")),
)


class KnowledgeDirector:
    """Deterministic extraction of teaching-relevant facts from a CSV row."""

    def analyze(
        self,
        row: KnowledgeBaseRow,
        *,
        csv_row: dict[str, str] | None = None,
    ) -> KnowledgeDirectorResult:
        """Extract the teaching-relevant facts.

        `csv_row` is the raw record from build_knowledge_csv.py; it carries the
        learning objective and common misconceptions, which KnowledgeBaseRow
        does not model. When it is absent, heuristics over the modeled fields
        stand in.
        """
        raw = csv_row or {}
        summary = row.engineering_summary
        combined = " ".join(
            part
            for part in (
                row.topic,
                row.category,
                row.subcategory,
                " ".join(row.keywords),
                summary,
            )
            if part
        ).lower()

        misconceptions = _json_list(raw.get("common_misconceptions", ""))
        misconception = misconceptions[0] if misconceptions else _last_sentence(summary)

        concept = _concept_for(combined)
        phenomenon = next(
            (
                phrase
                for phrase, tokens in _PHENOMENON_RULES
                if any(token in combined for token in tokens)
            ),
            concept,
        )
        difficult = next(
            (
                phrase
                for phrase, tokens in _DIFFICULT_VISUAL_RULES
                if any(token in combined for token in tokens)
            ),
            f"the geometry of {concept}",
        )
        takeaway = _after_rule_of_thumb(summary) or _last_sentence(summary)
        domain = infer_domain(row.category, row.subcategory, row.keywords)

        return KnowledgeDirectorResult(
            topic=row.topic,
            domain_hint=domain,
            most_important_concept=concept,
            common_misconception=misconception,
            difficult_visualization=difficult,
            key_phenomenon=phenomenon,
            primary_objective=raw.get("learning_objective", "")
            or f"Understand {concept}",
            critical_takeaway=takeaway,
            required_prior_knowledge=list(_DOMAIN_PRIOR_KNOWLEDGE.get(
                domain, ("basic engineering intuition",)
            )),
            category=row.category,
            subcategory=row.subcategory,
            viewer_level=row.viewer_level,
        )