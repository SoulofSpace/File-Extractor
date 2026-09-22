"""
composition.py — Domain dataclasses and contracts for Compositional Visual Retrieval.
Represents multi-modal queries and candidates as structured semantic roles:
  SUBJECT + ATTRIBUTE + CLOTHING/OBJECT + ACTION/RELATIONSHIP + SCENE
Enables semantic attribute binding, coordination scoring, and explicit contradiction handling.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class CompositionalQuery:
    """Structured semantic role decomposition of a user search query."""
    raw_query: str
    subjects: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    clothing: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    scene: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    bound_pairs: List[Tuple[str, str]] = field(default_factory=list)  # (attribute, target_noun)
    is_compositional: bool = False

    def active_roles(self) -> List[str]:
        """Returns the names of all non-empty semantic roles."""
        roles = []
        if self.subjects:
            roles.append("subject")
        if self.attributes:
            roles.append("attribute")
        if self.clothing:
            roles.append("clothing")
        if self.objects:
            roles.append("object")
        if self.actions:
            roles.append("action")
        if self.scene:
            roles.append("scene")
        if self.relationships:
            roles.append("relationship")
        return roles

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "subjects": self.subjects,
            "attributes": self.attributes,
            "clothing": self.clothing,
            "objects": self.objects,
            "actions": self.actions,
            "scene": self.scene,
            "relationships": self.relationships,
            "bound_pairs": self.bound_pairs,
            "is_compositional": self.is_compositional,
            "active_roles": self.active_roles(),
        }


@dataclass
class CandidateEvidence:
    """Structured semantic evidence extracted from document understanding / VLM records."""
    file_id: Optional[int] = None
    path: str = ""
    has_vlm: bool = False
    subjects: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    clothing: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    scene: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    bound_entities: Dict[str, List[str]] = field(default_factory=dict)  # noun -> [modifying_attributes]
    raw_description: str = ""
    document_type: str = ""

    @classmethod
    def from_du_dict(cls, du: Dict[str, Any], path: str = "") -> CandidateEvidence:
        """Constructs CandidateEvidence from a raw SQLite document_understanding dictionary."""
        if not du:
            return cls(path=path, has_vlm=False)

        def _parse_json_list(val: Any) -> List[str]:
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str) and val.strip():
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
                return [s.strip() for s in val.split(",") if s.strip()]
            return []

        subjects = _parse_json_list(du.get("people"))
        entities = _parse_json_list(du.get("entities"))
        for ent in entities:
            if ent not in subjects:
                subjects.append(ent)

        objects_raw = _parse_json_list(du.get("objects"))
        colors_raw = _parse_json_list(du.get("colors"))
        activities_raw = _parse_json_list(du.get("activities"))
        concepts_raw = _parse_json_list(du.get("visual_concepts"))
        tags_raw = _parse_json_list(du.get("semantic_tags"))
        locations_raw = _parse_json_list(du.get("locations"))
        relationships_raw = _parse_json_list(du.get("relationships"))
        desc = str(du.get("description") or "").strip()
        doc_type = str(du.get("document_type") or "").strip()

        # Separate clothing from generic physical objects
        CLOTHING_INDICATORS = {
            "dress", "shirt", "t-shirt", "tshirt", "jacket", "pants", "suit", "sweater",
            "cardigan", "hoodie", "coat", "jeans", "shorts", "skirt", "saree", "kurta",
            "jersey", "uniform", "sock", "socks", "shoes", "hat", "cap", "glove", "gloves",
            "vest", "tie", "scarf", "outfit", "costume", "garment", "cloth", "stripes"
        }
        clothing_list: List[str] = []
        regular_objects: List[str] = []
        for obj in objects_raw:
            low_obj = obj.lower()
            if any(re.search(r"\b" + re.escape(c) + r"\b", low_obj) for c in CLOTHING_INDICATORS):
                clothing_list.append(obj)
            else:
                regular_objects.append(obj)

        # Build bound entities map: entity/noun -> modifying attributes/colors
        # Extracted by inspecting multi-word object tags and description phrases
        bound_entities: Dict[str, List[str]] = {}
        all_item_phrases = objects_raw + [desc]
        for phrase in all_item_phrases:
            phrase_low = phrase.lower()
            # Look for patterns like "<attr> <noun>"
            for attr in colors_raw + ["striped", "knitted", "leather", "wooden", "metal", "cooked", "fresh"]:
                if attr.lower() in phrase_low:
                    # Find nouns in the phrase
                    words = phrase_low.split()
                    for idx, w in enumerate(words):
                        if attr.lower() in w and idx + 1 < len(words):
                            target_noun = words[idx + 1].strip(".,;:()")
                            if len(target_noun) > 2:
                                bound_entities.setdefault(target_noun, []).append(attr)

        return cls(
            file_id=du.get("file_id") or du.get("id"),
            path=path or str(du.get("path") or ""),
            has_vlm=True,
            subjects=subjects,
            attributes=list(set(colors_raw + concepts_raw)),
            clothing=clothing_list,
            objects=regular_objects,
            actions=activities_raw,
            scene=locations_raw + [t for t in tags_raw if t in {"outdoor", "indoor", "urban", "nature", "snow", "kitchen", "street"}],
            relationships=relationships_raw,
            bound_entities=bound_entities,
            raw_description=desc,
            document_type=doc_type,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "path": self.path,
            "has_vlm": self.has_vlm,
            "subjects": self.subjects,
            "attributes": self.attributes,
            "clothing": self.clothing,
            "objects": self.objects,
            "actions": self.actions,
            "scene": self.scene,
            "relationships": self.relationships,
            "bound_entities": self.bound_entities,
            "raw_description": self.raw_description,
            "document_type": self.document_type,
        }


@dataclass
class CompositionalMatchScore:
    """Detailed score breakdown across all semantic query components and coordination."""
    subject_match: float = 0.0
    attribute_match: float = 0.0
    clothing_match: float = 0.0
    object_match: float = 0.0
    action_match: float = 0.0
    relationship_match: float = 0.0
    scene_match: float = 0.0
    bound_attribute_match: float = 0.0
    coordination_score: float = 0.0
    contradiction_penalty: float = 0.0
    vlm_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, float]:
        return {
            "subject_match": round(self.subject_match, 4),
            "attribute_match": round(self.attribute_match, 4),
            "clothing_match": round(self.clothing_match, 4),
            "object_match": round(self.object_match, 4),
            "action_match": round(self.action_match, 4),
            "relationship_match": round(self.relationship_match, 4),
            "scene_match": round(self.scene_match, 4),
            "bound_attribute_match": round(self.bound_attribute_match, 4),
            "coordination": round(self.coordination_score, 4),
            "contradiction": round(self.contradiction_penalty, 4),
            "vlm": round(self.vlm_score, 4),
        }
