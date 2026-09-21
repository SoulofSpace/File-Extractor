"""
document_understanding.py — High-level document and visual understanding orchestrator.
Manages caching, format normalization, VLM inference, and database persistence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from PIL import Image

from ..database import Database
from ..domain.vlm_provider import DocumentUnderstandingResult, VLMProvider
from .format_normalizer import FormatNormalizer
from .local_qwen import LocalQwen35Provider
from .normalizer import ConceptNormalizer

logger = logging.getLogger(__name__)


class DocumentUnderstandingService:
    """
    High-level orchestrator for multimodal file understanding.
    Checks SHA-256 hash cache first, executes VLM inference only on new/changed files,
    canonicalizes concepts, and persists structured records to SQLite.
    """

    def __init__(
        self,
        database: Database,
        vlm_provider: Optional[VLMProvider] = None,
        prompt_schema_version: str = "v1",
    ) -> None:
        self.database = database
        self.vlm_provider = vlm_provider or LocalQwen35Provider()
        self.prompt_schema_version = prompt_schema_version

    def is_available(self) -> bool:
        """Check if underlying VLM provider is active."""
        try:
            return self.vlm_provider.is_available()
        except Exception:
            return False

    def process_file(
        self,
        file_path: Path | str,
        file_id: int,
        content_hash: str,
        force: bool = False,
    ) -> Optional[DocumentUnderstandingResult]:
        """
        Analyze a file visually if supported, returning structured understanding.
        Utilizes hash-based caching to avoid redundant inferences.
        """
        path = Path(file_path)
        if not FormatNormalizer.is_visual_candidate(path):
            return None

        model_info = self.vlm_provider.get_model_info()

        # 1. Fast-path: Check database cache by content hash
        if not force:
            cached = self.database.get_document_understanding_by_hash(
                content_hash=content_hash,
                model=model_info.model_name,
                prompt_schema_version=self.prompt_schema_version,
            )
            if cached:
                logger.debug("Cache hit for document understanding: %s", path.name)
                return self._row_to_result(cached)

        # 2. Check VLM provider availability
        if not self.is_available():
            logger.debug("VLM provider unavailable. Skipping visual document analysis for %s", path.name)
            return None

        # 3. Load standardized image
        image = FormatNormalizer.load_as_image(path)
        if image is None:
            return None

        # 4. Perform visual inference
        try:
            logger.info("Performing VLM document understanding on %s...", path.name)
            result = self.vlm_provider.analyze_document(image)
        except Exception as exc:
            logger.warning("VLM analysis failed for %s: %s", path.name, exc)
            return None

        # 5. Canonicalize concepts
        normalized = ConceptNormalizer.categorize_concepts(
            objects=result.objects,
            visual_concepts=result.visual_concepts,
            semantic_tags=result.semantic_tags,
        )
        result.objects = normalized.core_concepts
        result.visual_concepts = normalized.secondary_concepts

        # 6. Persist to database
        try:
            self.database.upsert_document_understanding(
                file_id=file_id,
                result=result,
                content_hash=content_hash,
                provider="local_qwen",
                model=model_info.model_name,
                model_version=model_info.model_version,
                prompt_schema_version=self.prompt_schema_version,
            )
        except Exception as exc:
            logger.error("Failed to persist document understanding for %s: %s", path.name, exc)

        return result

    def _row_to_result(self, row: dict) -> DocumentUnderstandingResult:
        """Convert a database row into a DocumentUnderstandingResult object."""
        import json

        def _parse_list(val: Any) -> list:
            if isinstance(val, str) and val.strip():
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            return []

        def _parse_dict(val: Any) -> dict:
            if isinstance(val, str) and val.strip():
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
            return {}

        return DocumentUnderstandingResult(
            document_type=row.get("document_type", "document"),
            title=row.get("title"),
            description=row.get("description", ""),
            event_name=row.get("event_name"),
            dates=_parse_list(row.get("dates")),
            times=_parse_list(row.get("times")),
            locations=_parse_list(row.get("locations")),
            organizations=_parse_list(row.get("organizations")),
            people=_parse_list(row.get("people")),
            objects=_parse_list(row.get("objects")),
            entities=_parse_list(row.get("entities")),
            semantic_tags=_parse_list(row.get("semantic_tags")),
            visual_concepts=_parse_list(row.get("visual_concepts")),
            activities=_parse_list(row.get("activities")),
            colors=_parse_list(row.get("colors")),
            attributes=_parse_dict(row.get("attributes")),
            relationships=_parse_list(row.get("relationships")),
            important_text=_parse_list(row.get("important_text")),
            layout_regions=_parse_list(row.get("layout_regions")),
            raw_json=_parse_dict(row.get("raw_response")),
        )
