"""
reranker.py — Optional second-stage candidate verification and reranking for FILE XTRACTOR V3.
Performs fine-grained visual-semantic verification on top retrieval candidates using local VLM.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .domain.vlm_provider import VLMProvider
from .vlm.format_normalizer import FormatNormalizer
from .vlm.local_qwen import LocalQwen35Provider

logger = logging.getLogger(__name__)

RERANK_PROMPT_TEMPLATE = """Evaluate how accurately this image matches the search query: "{query}".
Return ONLY a valid JSON object matching this schema:
{{
  "score": 0.0 to 1.0,
  "match": true or false,
  "reason": "One concise sentence explaining why it matches or fails to match"
}}
"""


class CandidateReranker:
    """
    Second-stage candidate verifier for top-N search results.
    Refines ranking when visual attributes or fine-grained details are ambiguous.
    """

    def __init__(self, vlm_provider: Optional[VLMProvider] = None) -> None:
        self.vlm_provider = vlm_provider or LocalQwen35Provider()

    def is_available(self) -> bool:
        """Check if local VLM server is ready for reranking."""
        try:
            return self.vlm_provider.is_available()
        except Exception:
            return False

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank top_k candidates by verifying visual contents with VLM.
        Returns the candidates list with updated scores.
        """
        if not candidates or not self.is_available():
            return candidates

        reranked_pool = candidates[:top_k]
        remaining = candidates[top_k:]

        for cand in reranked_pool:
            path_str = cand.get("path")
            if not path_str or not FormatNormalizer.is_visual_candidate(path_str):
                continue

            img = FormatNormalizer.load_as_image(path_str)
            if img is None:
                continue

            try:
                prompt = RERANK_PROMPT_TEMPLATE.format(query=query)
                resp = self.vlm_provider.generate(
                    prompt=prompt,
                    images=[img],
                    max_tokens=256,
                    temperature=0.0,
                )
                text = resp.content or resp.reasoning_content or ""
                # Parse JSON
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    data = json.loads(text[start : end + 1])
                    vlm_score = float(data.get("score", 0.5))
                    reason = data.get("reason", "VLM verified match")

                    # Blend rerank score into relevance score (30% weight)
                    orig_score = float(cand.get("relevance_score", 0.5))
                    new_score = 0.70 * orig_score + 0.30 * vlm_score
                    cand["relevance_score"] = round(new_score, 3)
                    cand["rank"] = -new_score
                    cand["vlm_rerank_reason"] = reason

                    match_ev = cand.get("match_evidence", {})
                    match_ev["vlm_rerank"] = vlm_score
                    cand["match_evidence"] = match_ev

            except Exception as exc:
                logger.debug("Reranking failed for %s: %s", path_str, exc)

        # Re-sort top pool
        reranked_pool.sort(key=lambda x: (float(x.get("rank", 0.0)), str(x.get("path", ""))))
        return reranked_pool + remaining
