"""
query_planner.py — Generalized Multi-Modal Query Planner for FILE XTRACTOR V3.
Extracts query intents, filters, acronym expansions, document types,
and visual modalities without brittle hardcoded concept lists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .domain.interfaces import QueryPlanInterface

# Conversational fillers stripped from start/end of queries
CONVERSATIONAL_FILLERS = [
    r"^(can you\s+)?(please\s+)?(find|show|get|search|display|locate|open|retrieve|look for|give me)\s+(me\s+)?(my\s+|the\s+|all\s+|a\s+|some\s+)?",
    r"^(where is|where are|do you have|i need|i want)\s+(my\s+|the\s+|all\s+|a\s+|some\s+)?",
    r"\s+please$",
    r"\s+for me$",
]

# Canonical academic acronyms & curriculum expansion
ACRONYM_MAP: Dict[str, List[str]] = {
    "dbms": ["Database Management System", "Database Management Systems", "Database"],
    "dsa": ["Data Structures and Algorithms", "Data Structures & Algorithms", "Data Structures"],
    "os": ["Operating System", "Operating Systems"],
    "cn": ["Computer Networks", "Computer Network"],
    "ai": ["Artificial Intelligence"],
    "ml": ["Machine Learning"],
    "dl": ["Deep Learning"],
    "nlp": ["Natural Language Processing"],
    "oops": ["Object Oriented Programming", "Object-Oriented Programming"],
    "oop": ["Object Oriented Programming", "Object-Oriented Programming"],
    "se": ["Software Engineering"],
    "daa": ["Design and Analysis of Algorithms"],
    "toc": ["Theory of Computation"],
    "id": ["ID", "Identity", "Identification", "ID Card"],
}

ASSIGNMENT_REGEX = re.compile(r"\b(da|la|lab|assignment|assessment)\s*[-_]?\s*(\d+)\b", re.IGNORECASE)

# Standard compound word variations (open/closed/hyphenated)
COMPOUND_PAIRS: Dict[str, str] = {
    "timetable": "time table",
    "time table": "timetable",
    "flowchart": "flow chart",
    "flow chart": "flowchart",
    "screenshot": "screen shot",
    "screen shot": "screenshot",
    "wireframe": "wire frame",
    "wire frame": "wireframe",
}

# Generalized document types that imply visual/document structure
STRUCTURAL_DOC_TYPES = {
    "poster", "flyer", "infographic", "timetable", "schedule", "id card", "identity card",
    "certificate", "receipt", "invoice", "bill", "ticket", "diagram", "chart", "flowchart",
    "wireframe", "screenshot", "presentation", "slide", "slides"
}

VISUAL_MODALITY_TERMS = {
    "photo", "picture", "image", "pic", "selfie", "camera", "snapshot", "drawing",
    "illustration", "artwork", "graphic", "logo", "wallpaper",
    "portrait", "dress", "shirt", "wearing", "clothes", "clothing", "outfit", "tshirt",
}


@dataclass
class QueryPlan:
    """Structured execution plan for multi-modal retrieval."""
    raw_query: str
    cleaned_query: str
    is_visual: bool = False
    is_academic: bool = False
    target_category: Optional[str] = None
    search_terms: List[str] = field(default_factory=list)
    explanation: str = ""
    size_filter: Optional[Tuple[str, int]] = None       # ('gt'/'lt', bytes)
    ext_filter: Optional[str] = None
    detected_doc_types: List[str] = field(default_factory=list)
    target_entities: List[str] = field(default_factory=list)


class QueryPlanner(QueryPlanInterface):
    """
    Open-vocabulary query planner converting free-form user language
    into structured multi-branch retrieval instructions.
    """

    def parse_query(self, raw_query: str) -> QueryPlan:
        q = raw_query.strip()
        cleaned = q

        # 1. Strip conversational filler phrases
        for pattern in CONVERSATIONAL_FILLERS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # 2. Extract natural language extension filters (e.g. ext:pdf, type:jpg)
        ext_filter = None
        ext_match = re.search(r"\b(ext|type):([A-Za-z0-9]+)\b", cleaned, re.IGNORECASE)
        if ext_match:
            ext_filter = "." + ext_match.group(2).lower()
            cleaned = re.sub(r"\b(ext|type):[A-Za-z0-9]+\b", "", cleaned, flags=re.IGNORECASE).strip()

        # 3. Extract natural language size filters (e.g. size:>10MB, size:<500KB)
        size_filter = None
        size_match = re.search(r"\bsize:([><]=?)\s*(\d+(?:\.\d+)?)\s*(kb|mb|gb)?\b", cleaned, re.IGNORECASE)
        if size_match:
            op = "gt" if ">" in size_match.group(1) else "lt"
            val = float(size_match.group(2))
            unit = (size_match.group(3) or "mb").lower()
            multipliers = {"kb": 1024, "mb": 1024 * 1024, "gb": 1024 * 1024 * 1024}
            size_bytes = int(val * multipliers.get(unit, 1024 * 1024))
            size_filter = (op, size_bytes)
            cleaned = re.sub(r"\bsize:[><]=?\s*\d+(?:\.\d+)?\s*(?:kb|mb|gb)?\b", "", cleaned, flags=re.IGNORECASE).strip()

        # 4. Normalize separators to whitespace for routing
        norm_cleaned = re.sub(r"[^\w\s]|_", " ", cleaned).strip()
        norm_cleaned = re.sub(r"\s+", " ", norm_cleaned)
        lower_q = norm_cleaned.lower()

        # 5. Detect structural document types and visual modalities
        detected_doc_types = []
        for dt in STRUCTURAL_DOC_TYPES:
            if re.search(r"\b" + re.escape(dt) + r"\b", lower_q):
                detected_doc_types.append(dt)

        is_explicitly_visual = any(re.search(r"\b" + re.escape(vt) + r"\b", lower_q) for vt in VISUAL_MODALITY_TERMS)
        is_visual = is_explicitly_visual or len(detected_doc_types) > 0

        # 6. Check academic acronyms and technical abbreviations
        search_terms: List[str] = []
        is_academic = False
        explanations: List[str] = []

        # Check assignment patterns (e.g. "DA 3" or "LA 3")
        assign_match = ASSIGNMENT_REGEX.search(cleaned)
        if assign_match:
            is_academic = True
            prefix = assign_match.group(1).upper()
            num = assign_match.group(2)
            search_terms.extend([
                f"{prefix} {num}",
                f"{prefix}{num}",
                f"{prefix}-{num}",
                f"la {num}",
                f"la{num}",
                f"da {num}",
                f"Assignment {num}",
                f"Assessment {num}",
            ])
            explanations.append(f"Assignment #{num}")

        # Check acronyms (e.g., DBMS, OS, CN)
        words = re.findall(r"\b[A-Za-z0-9]+\b", lower_q)
        for w in words:
            if w in ACRONYM_MAP:
                if w != "id":
                    is_academic = True
                expansions = ACRONYM_MAP[w]
                search_terms.extend(expansions)
                explanations.append(f"{w.upper()} ({expansions[0]})")

        # Check compound word variants
        for compound_src, compound_target in COMPOUND_PAIRS.items():
            if compound_src in lower_q and compound_target not in search_terms:
                search_terms.append(compound_target)

        if not search_terms:
            search_terms = [cleaned]
        elif cleaned not in search_terms:
            search_terms.insert(0, cleaned)

        target_cat = None
        if is_visual and not is_academic:
            target_cat = "Image"
        elif is_academic:
            target_cat = "Document"

        explanation_str = " + ".join(explanations) if explanations else ""

        return QueryPlan(
            raw_query=q,
            cleaned_query=cleaned,
            is_visual=is_visual,
            is_academic=is_academic,
            target_category=target_cat,
            search_terms=search_terms,
            explanation=explanation_str,
            size_filter=size_filter,
            ext_filter=ext_filter,
            detected_doc_types=detected_doc_types,
        )
