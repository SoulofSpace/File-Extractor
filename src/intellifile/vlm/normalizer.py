"""
normalizer.py — Concept and entity canonicalization for FILE XTRACTOR V3.
Standardizes terminology, separates core physical concepts from ambient descriptors,
and deduplicates tokens to prevent concept drift.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

# Common descriptors that are ambient/stylistic rather than core physical objects
AMBIENT_MODIFIERS: Set[str] = {
    "vibrant", "cinematic", "aesthetic", "cozy", "moody", "warm", "cool",
    "serene", "dramatic", "modern", "vintage", "clean", "minimalist",
    "beautiful", "nice", "stunning", "blurred", "clear", "bright", "dark",
    "soft lighting", "high contrast", "realistic", "high quality"
}

# Canonical alias mapping for visual terms
CANONICAL_SYNONYMS: Dict[str, str] = {
    "qr-code": "qr code",
    "qrcode": "qr code",
    "bar-code": "barcode",
    "id-card": "id card",
    "idcard": "id card",
    "time-table": "timetable",
    "schedule": "timetable",
    "pup": "dog",
    "puppy": "dog",
    "hound": "dog",
    "canine": "dog",
    "kitten": "cat",
    "feline": "cat",
    "automobile": "car",
    "vehicle": "car",
    "laptop computer": "laptop",
    "notebook": "laptop",
    "flyer": "poster",
    "pamphlet": "poster",
    "infographic": "diagram",
    "flowchart": "diagram",
}


@dataclass
class NormalizedConcepts:
    """Separated and canonicalized concept representations."""
    core_concepts: List[str] = field(default_factory=list)
    secondary_concepts: List[str] = field(default_factory=list)
    searchable_tokens: List[str] = field(default_factory=list)


class ConceptNormalizer:
    """
    Standardizes raw outputs from VLM inference into structured,
    search-optimized tokens with tiered relevance weighting.
    """

    @staticmethod
    def clean_term(term: str) -> str:
        """Strip punctuation and standardize internal whitespace."""
        if not term:
            return ""
        cleaned = re.sub(r"[^\w\s-]|_", " ", term.lower()).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return CANONICAL_SYNONYMS.get(cleaned, cleaned)

    @classmethod
    def normalize_list(cls, terms: List[str]) -> List[str]:
        """Clean and deduplicate a list of terms preserving order."""
        seen = set()
        result = []
        for t in terms:
            clean = cls.clean_term(t)
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result

    @classmethod
    def categorize_concepts(
        cls,
        objects: List[str],
        visual_concepts: List[str],
        semantic_tags: List[str],
    ) -> NormalizedConcepts:
        """
        Partition terms into Core Concepts (physical objects, concrete tags)
        and Secondary Concepts (ambient visual modifiers, styles).
        """
        core: List[str] = []
        secondary: List[str] = []
        all_tokens: Set[str] = set()

        # Objects are almost always Core
        for obj in cls.normalize_list(objects):
            core.append(obj)
            all_tokens.add(obj)
            for word in obj.split():
                if len(word) >= 2:
                    all_tokens.add(word)

        # Semantic tags are Core
        for tag in cls.normalize_list(semantic_tags):
            if tag not in core:
                core.append(tag)
            all_tokens.add(tag)
            for word in tag.split():
                if len(word) >= 2:
                    all_tokens.add(word)

        # Visual concepts split between Core and Secondary
        for vc in cls.normalize_list(visual_concepts):
            is_ambient = any(m in vc for m in AMBIENT_MODIFIERS)
            if is_ambient:
                if vc not in secondary:
                    secondary.append(vc)
            else:
                if vc not in core:
                    core.append(vc)
            all_tokens.add(vc)
            for word in vc.split():
                if len(word) >= 2:
                    all_tokens.add(word)

        return NormalizedConcepts(
            core_concepts=core,
            secondary_concepts=secondary,
            searchable_tokens=sorted(all_tokens),
        )
