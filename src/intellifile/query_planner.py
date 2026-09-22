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
from .domain.composition import CompositionalQuery

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
    compositional_query: Optional[CompositionalQuery] = None


# Semantic Vocabulary Roots for Generalized Role Decomposition
PREPOSITIONS: Set[str] = {"in", "with", "wearing", "on", "at", "near", "holding", "by", "under", "beside", "of"}

SUBJECT_ROOTS: Set[str] = {
    "guy", "man", "woman", "girl", "boy", "person", "people", "child", "children", "baby",
    "elderly", "dog", "cat", "puppy", "kitten", "bird", "animal", "student", "teacher",
    "character", "hero", "superhero", "friend", "selfie", "someone", "somebody", "men", "women"
}

SUBJECT_EXPANSIONS: Dict[str, List[str]] = {
    "guy": ["guy", "man", "person"],
    "man": ["man", "guy", "person"],
    "woman": ["woman", "lady", "girl", "person"],
    "girl": ["girl", "woman", "person"],
    "boy": ["boy", "guy", "person", "child"],
    "person": ["person", "man", "woman", "individual"],
    "child": ["child", "kid", "baby", "boy", "girl"],
    "baby": ["baby", "infant", "newborn", "child"],
    "dog": ["dog", "canine", "puppy", "hound"],
    "cat": ["cat", "feline", "kitten"],
}

CLOTHING_ROOTS: Set[str] = {
    "dress", "shirt", "t-shirt", "tshirt", "jacket", "pants", "suit", "sweater",
    "cardigan", "hoodie", "coat", "jeans", "shorts", "skirt", "saree", "kurta",
    "jersey", "uniform", "socks", "shoes", "hat", "cap", "backpack", "bag", "glasses",
    "sunglasses", "outfit", "costume", "garment", "cloth", "tie", "scarf", "vest"
}

SCENE_ROOTS: Set[str] = {
    "grass", "park", "kitchen", "beach", "street", "city", "room", "skyline",
    "ground", "field", "outdoor", "indoor", "forest", "office", "snow", "water",
    "sea", "mountain", "table", "floor", "wall", "background"
}

ACTION_VERBS: Set[str] = {
    "wearing", "holding", "sitting", "standing", "walking", "running", "carrying",
    "riding", "driving", "posing", "eating", "cooking", "reading", "looking", "taking"
}

COMMON_ATTRIBUTES: Set[str] = {
    "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown", "black",
    "white", "gray", "grey", "cyan", "maroon", "gold", "golden", "silver", "dark", "light",
    "bright", "striped", "plain", "knitted", "leather", "wooden", "metal", "cooked", "fresh",
    "big", "small", "tall", "short", "young", "old", "vintage", "modern", "casual", "formal"
}


def decompose_compositional_query(cleaned_query: str) -> CompositionalQuery:
    """
    Decomposes a query into structured semantic roles using open grammar patterns:
      SUBJECT + ATTRIBUTE + CLOTHING/OBJECT + ACTION/RELATION + SCENE
    """
    tokens = [t.strip().lower() for t in re.sub(r"[^\w\s-]|_", " ", cleaned_query).split() if t.strip()]
    if not tokens:
        return CompositionalQuery(raw_query=cleaned_query)

    subjects: List[str] = []
    attributes: List[str] = []
    clothing: List[str] = []
    objects: List[str] = []
    actions: List[str] = []
    scene: List[str] = []
    relationships: List[str] = []
    bound_pairs: List[Tuple[str, str]] = []

    # 1. Subject extraction
    remaining_tokens: List[str] = []
    for t in tokens:
        if t in SUBJECT_ROOTS:
            exp = SUBJECT_EXPANSIONS.get(t, [t])
            for s in exp:
                if s not in subjects:
                    subjects.append(s)
        else:
            remaining_tokens.append(t)

    # 2. Sequential grammatical pattern extraction
    j = 0
    words = remaining_tokens
    while j < len(words):
        w = words[j]
        if w in {"a", "an", "the"}:
            j += 1
            continue

        if w in ACTION_VERBS:
            actions.append(w)
            j += 1
            if j < len(words) and words[j] in PREPOSITIONS:
                relationships.append(f"{w} {words[j]}")
                j += 1
            if j < len(words) and words[j] in {"a", "an", "the"}:
                j += 1
            curr_attr = None
            if j < len(words) and (words[j] in COMMON_ATTRIBUTES or (j + 1 < len(words) and words[j+1] not in PREPOSITIONS)):
                curr_attr = words[j]
                attributes.append(curr_attr)
                j += 1
            if j < len(words):
                target = words[j]
                if target in CLOTHING_ROOTS:
                    clothing.append(target)
                elif target in SCENE_ROOTS:
                    scene.append(target)
                else:
                    objects.append(target)
                if curr_attr:
                    bound_pairs.append((curr_attr, target))
                    relationships.append(f"{w} {curr_attr} {target}")
                else:
                    relationships.append(f"{w} {target}")
                j += 1
            continue

        if w in PREPOSITIONS:
            prep = w
            j += 1
            if j < len(words) and words[j] in {"a", "an", "the"}:
                j += 1
            curr_attr = None
            if j < len(words) and (words[j] in COMMON_ATTRIBUTES or (j + 1 < len(words) and words[j+1] not in PREPOSITIONS)):
                curr_attr = words[j]
                attributes.append(curr_attr)
                j += 1
            if j < len(words):
                target = words[j]
                if target in CLOTHING_ROOTS:
                    clothing.append(target)
                elif target in SCENE_ROOTS:
                    scene.append(target)
                elif target in SUBJECT_ROOTS:
                    for s in SUBJECT_EXPANSIONS.get(target, [target]):
                        if s not in subjects:
                            subjects.append(s)
                else:
                    objects.append(target)
                if curr_attr:
                    bound_pairs.append((curr_attr, target))
                    relationships.append(f"{prep} {curr_attr} {target}")
                else:
                    relationships.append(f"{prep} {target}")
                j += 1
            elif curr_attr:
                clothing.append(curr_attr)
                relationships.append(f"{prep} {curr_attr}")
            continue

        # Standalone modifier preceding a noun
        is_known_attr = w in COMMON_ATTRIBUTES
        next_is_visual_target = (j + 1 < len(words) and (words[j+1] in CLOTHING_ROOTS or words[j+1] in SCENE_ROOTS or words[j+1] in SUBJECT_ROOTS))
        if is_known_attr or next_is_visual_target:
            curr_attr = w
            attributes.append(curr_attr)
            j += 1
            if j < len(words) and words[j] not in PREPOSITIONS and words[j] not in ACTION_VERBS:
                target = words[j]
                if target in CLOTHING_ROOTS:
                    clothing.append(target)
                elif target in SCENE_ROOTS:
                    scene.append(target)
                elif target in SUBJECT_ROOTS:
                    for s in SUBJECT_EXPANSIONS.get(target, [target]):
                        if s not in subjects:
                            subjects.append(s)
                elif target not in {"file", "filename", "content", "document", "text", "folder", "code", "script"}:
                    objects.append(target)
                bound_pairs.append((curr_attr, target))
                relationships.append(f"{curr_attr} {target}")
                j += 1
            continue

        # Direct nouns
        if w in CLOTHING_ROOTS:
            clothing.append(w)
        elif w in SCENE_ROOTS:
            scene.append(w)
        elif w not in {"a", "an", "the"}:
            objects.append(w)
        j += 1

    roles_count = sum(1 for r in [subjects, attributes, clothing, objects, actions, scene] if r)
    is_comp = (roles_count >= 2) or bool(bound_pairs)

    return CompositionalQuery(
        raw_query=cleaned_query,
        subjects=subjects,
        attributes=attributes,
        clothing=clothing,
        objects=objects,
        actions=actions,
        scene=scene,
        relationships=relationships,
        bound_pairs=bound_pairs,
        is_compositional=is_comp,
    )


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

        # 5. Compositional decomposition
        cq = decompose_compositional_query(cleaned)

        # 6. Detect structural document types and visual modalities
        detected_doc_types = []
        for dt in STRUCTURAL_DOC_TYPES:
            if re.search(r"\b" + re.escape(dt) + r"\b", lower_q):
                detected_doc_types.append(dt)

        is_explicitly_visual = any(re.search(r"\b" + re.escape(vt) + r"\b", lower_q) for vt in VISUAL_MODALITY_TERMS)
        has_visual_role = (
            cq.is_compositional
            or bool(cq.clothing)
            or bool(cq.scene)
            or (bool(cq.subjects) and bool(cq.attributes))
            or (bool(cq.attributes) and bool(cq.objects))
            or any(s in {"dog", "cat", "animal", "bird"} for s in cq.subjects)
        )
        is_visual = is_explicitly_visual or len(detected_doc_types) > 0 or has_visual_role

        # 7. Check academic acronyms and technical abbreviations
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

        # Academic queries are strictly textual/document, not visual
        if is_academic:
            is_visual = False

        # Check compound word variants
        for compound_src, compound_target in COMPOUND_PAIRS.items():
            if compound_src in lower_q and compound_target not in search_terms:
                search_terms.append(compound_target)

        if not search_terms:
            search_terms = [cleaned]
        elif cleaned not in search_terms:
            search_terms.insert(0, cleaned)

        target_cat = None
        if is_explicitly_visual and not is_academic:
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
            compositional_query=cq,
        )
