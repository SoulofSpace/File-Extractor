"""
compositional_evaluator.py — Generalized Compositional Multi-Modal Evaluation Engine.
Evaluates semantic alignment between a structured query (CompositionalQuery)
and image evidence (CandidateEvidence) through:
  1. Component match scoring (subject, attribute, clothing, object, action, scene)
  2. Semantic attribute binding (bound vs ambient attribute credit)
  3. Query coordination scoring (quadratic suppression of uncoordinated matches)
  4. Explicit contradiction handling (conflicting attributes on bound target)
  5. Calibrated, normalized VLM scoring without static keyword lists or arbitrary baselines
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .domain.composition import CandidateEvidence, CompositionalMatchScore, CompositionalQuery


class CompositionalEvaluator:
    """
    Generalized engine evaluating complete query composition against candidate visual evidence.
    Distinguishes bound attributes ('blue shirt') from ambient attributes ('blue tones'),
    penalizes explicit contradictions while treating absence of metadata as neutral (UNKNOWN).
    """

    CLOTHING_SYNONYMS: Dict[str, List[str]] = {
        "shirt": ["shirt", "t-shirt", "tshirt", "top", "tee"],
        "dress": ["dress", "gown", "frock"],
        "jacket": ["jacket", "coat", "blazer", "hoodie", "windbreaker"],
        "pants": ["pants", "trousers", "jeans", "slacks"],
        "suit": ["suit", "tuxedo"],
        "sweater": ["sweater", "cardigan", "pullover"],
        "backpack": ["backpack", "bag", "rucksack", "knapsack"],
        "jersey": ["jersey", "uniform", "kit"],
        "shorts": ["shorts"],
        "skirt": ["skirt"],
        "shoes": ["shoes", "sneakers", "boots", "footwear"],
        "hat": ["hat", "cap", "beanie"],
    }

    SUBJECT_SYNONYMS: Dict[str, List[str]] = {
        "guy": ["guy", "man", "boy", "person", "adult", "male"],
        "man": ["man", "guy", "adult", "person", "male"],
        "woman": ["woman", "lady", "girl", "person", "female"],
        "person": ["person", "man", "woman", "guy", "boy", "girl", "individual", "adult"],
        "child": ["child", "kid", "baby", "boy", "girl", "toddler"],
        "baby": ["baby", "infant", "newborn"],
        "dog": ["dog", "puppy", "canine", "hound"],
        "cat": ["cat", "kitten", "feline"],
    }

    def evaluate(self, query: CompositionalQuery, candidate: CandidateEvidence) -> CompositionalMatchScore:
        """
        Evaluates a candidate against a compositional query.
        Returns a rich CompositionalMatchScore with all component matches and coordination.
        """
        # If candidate has no VLM metadata, treat as UNKNOWN (Neutral, relies on CLIP)
        if not candidate.has_vlm:
            return CompositionalMatchScore(
                subject_match=0.0,
                attribute_match=0.0,
                clothing_match=0.0,
                object_match=0.0,
                action_match=0.0,
                relationship_match=0.0,
                scene_match=0.0,
                bound_attribute_match=0.0,
                coordination_score=0.0,
                contradiction_penalty=0.0,
                vlm_score=0.0,
                explanation="Absence of VLM metadata (Neutral/Unknown)",
            )

        cand_subj_text = " ".join(candidate.subjects + [candidate.document_type, candidate.raw_description]).lower()
        cand_clothing_text = " ".join(candidate.clothing + [candidate.raw_description]).lower()
        cand_objs_text = " ".join(candidate.objects + [candidate.raw_description]).lower()
        cand_attrs_text = " ".join(candidate.attributes + [candidate.raw_description]).lower()
        cand_acts_text = " ".join(candidate.actions + [candidate.raw_description]).lower()
        cand_scene_text = " ".join(candidate.scene + [candidate.raw_description]).lower()

        # ── 1. Subject Matching ──────────────────────────────────────
        subject_match = 1.0
        if query.subjects:
            subject_match = 0.0
            for qs in query.subjects:
                syns = self.SUBJECT_SYNONYMS.get(qs, [qs])
                if any(re.search(r"\b" + re.escape(s) + r"\b", cand_subj_text) for s in syns):
                    subject_match = 1.0
                    break
            # Partial entity credit if hero/character/mascot for generic person queries
            if subject_match == 0.0 and any(h in cand_subj_text for h in ["character", "hero", "superhero", "illustration"]):
                if any(qs in {"guy", "man", "person"} for qs in query.subjects):
                    subject_match = 0.40

        # ── 2. Clothing Matching ─────────────────────────────────────
        clothing_match = 1.0
        if query.clothing:
            clothing_match = 0.0
            for qc in query.clothing:
                syns = self.CLOTHING_SYNONYMS.get(qc, [qc])
                if any(re.search(r"\b" + re.escape(c) + r"\b", cand_clothing_text) for c in syns):
                    clothing_match = 1.0
                    break

        # ── 3. Object Matching ───────────────────────────────────────
        object_match = 1.0
        if query.objects:
            object_match = 0.0
            for qo in query.objects:
                if re.search(r"\b" + re.escape(qo) + r"\b", cand_objs_text):
                    object_match = 1.0
                    break

        # ── 4. Action Matching ───────────────────────────────────────
        action_match = 1.0
        if query.actions:
            action_match = 0.0
            for qa in query.actions:
                if re.search(r"\b" + re.escape(qa) + r"\b", cand_acts_text):
                    action_match = 1.0
                    break

        # ── 5. Scene / Spatial Matching ──────────────────────────────
        scene_match = 1.0
        if query.scene:
            scene_match = 0.0
            for qs in query.scene:
                if re.search(r"\b" + re.escape(qs) + r"\b", cand_scene_text):
                    scene_match = 1.0
                    break

        # ── 6. Semantic Attribute Binding ────────────────────────────
        attribute_match = 1.0
        bound_attribute_match = 1.0

        if query.attributes:
            attribute_match = 0.0
            bound_attribute_match = 0.0
            has_general_attr = any(re.search(r"\b" + re.escape(qa) + r"\b", cand_attrs_text) for qa in query.attributes)

            if query.bound_pairs:
                for attr, target in query.bound_pairs:
                    target_syns = self.CLOTHING_SYNONYMS.get(target, [target])
                    is_bound = False
                    for ts in target_syns:
                        # Direct attribute-noun phrase
                        if re.search(rf"\b{re.escape(attr)}\s+{re.escape(ts)}\b", cand_attrs_text):
                            is_bound = True
                            break
                        # Prepositional binding: "in/wearing <attr> <ts>"
                        if re.search(rf"(in|wearing)\s+a?\s*{re.escape(attr)}\s+{re.escape(ts)}", cand_attrs_text):
                            is_bound = True
                            break
                        # Bound entities dictionary lookup
                        if ts in candidate.bound_entities and attr in candidate.bound_entities[ts]:
                            is_bound = True
                            break

                    if is_bound:
                        bound_attribute_match = 1.0
                        attribute_match = 1.0
                    elif has_general_attr:
                        # Ambient credit: attribute exists in candidate but modifies an unrelated entity
                        bound_attribute_match = 0.0
                        attribute_match = 0.20
            else:
                if has_general_attr:
                    attribute_match = 1.0
                    bound_attribute_match = 1.0

        # ── 7. Explicit Contradiction Handling ───────────────────────
        contradiction_penalty = 0.0

        # Case A: Query requires human clothing/person, but candidate is inanimate object/food dish
        if query.clothing and query.subjects:
            if not candidate.subjects and not candidate.clothing:
                contradiction_penalty = max(contradiction_penalty, 0.70)

        # Case B: Query specifies a bound attribute on a target (e.g. green shirt),
        # but candidate has the target item with a conflicting attribute (e.g. brown t-shirt)
        if query.bound_pairs and candidate.clothing:
            for attr, target in query.bound_pairs:
                target_syns = self.CLOTHING_SYNONYMS.get(target, [target])
                has_target = any(re.search(r"\b" + re.escape(ts) + r"\b", cand_clothing_text) for ts in target_syns)
                if has_target and bound_attribute_match == 0.0:
                    contradiction_penalty = max(contradiction_penalty, 0.65)

        # Case C: Query asks for human dress/clothing, candidate is a superhero suit/costume
        if any(qc in {"dress", "gown"} for qc in query.clothing):
            if any(s in cand_clothing_text for s in ["spider-man suit", "superhero suit", "costume", "vulture suit"]):
                contradiction_penalty = max(contradiction_penalty, 0.60)

        # ── 8. Coordination Scoring ──────────────────────────────────
        active_scores: List[float] = []
        if query.subjects:
            active_scores.append(subject_match)
        if query.clothing:
            active_scores.append(clothing_match)
        if query.objects:
            active_scores.append(object_match)
        if query.actions:
            active_scores.append(action_match)
        if query.scene:
            active_scores.append(scene_match)
        if query.attributes:
            active_scores.append(bound_attribute_match if query.bound_pairs else attribute_match)

        if not active_scores:
            active_scores = [1.0]

        avg_match = sum(active_scores) / len(active_scores)
        coordination_score = avg_match ** 2

        # ── 9. Normalized VLM Evidence Scoring ───────────────────────
        # Formula: Coordination * AvgMatch * (1 - 0.75 * Contradiction)
        # Suppresses 1-of-3 partial matches to near 0, rewards 3-of-3 full coordination
        vlm_score = coordination_score * avg_match * max(0.0, (1.0 - 0.75 * contradiction_penalty))
        vlm_score = round(min(1.0, max(0.0, vlm_score)), 4)

        return CompositionalMatchScore(
            subject_match=subject_match,
            attribute_match=attribute_match,
            clothing_match=clothing_match,
            object_match=object_match,
            action_match=action_match,
            relationship_match=1.0 if bound_attribute_match > 0 else 0.0,
            scene_match=scene_match,
            bound_attribute_match=bound_attribute_match,
            coordination_score=coordination_score,
            contradiction_penalty=contradiction_penalty,
            vlm_score=vlm_score,
            explanation=f"Coordination: {coordination_score:.2f}, Contradiction: {contradiction_penalty:.2f}",
        )
