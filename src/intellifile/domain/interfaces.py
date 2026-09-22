"""
interfaces.py — Core architectural contracts for FILE XTRACTOR V2.
Defines interfaces for embedding models, vector storage, query planning, and match evidence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import numpy as np


@dataclass
class FileIdentity:
    """Cryptographic file identity and fast-path metadata."""
    path: Path
    size_bytes: int
    modified_at: float
    sha256_hash: Optional[str] = None
    phash: Optional[str] = None

    def is_fast_match(self, other_size: int, other_mtime: float) -> bool:
        """Fast-path pre-check to detect unmodified files without disk I/O."""
        return self.size_bytes == other_size and abs(self.modified_at - other_mtime) < 1e-4


@dataclass
class VectorMatch:
    """Represents a single nearest-neighbor vector match."""
    entity_type: str           # 'file', 'page', 'image'
    entity_id: int             # files.id or content_pages.id
    similarity: float          # Cosine similarity in range [-1.0, 1.0]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchEvidence:
    """
    Structured, explainable evidence explaining why a result matched.
    Note: `relevance_score` is a transformed multi-modal retrieval score in [0.0, 1.0],
    combining normalized BM25, dense vector cosine similarity, CLIP visual similarity,
    and exact filename matching. It is NOT a calibrated probability or confidence value.
    """
    relevance_score: float     # Transformed retrieval score in [0.0, 1.0]
    lexical_score: float = 0.0 # BM25 or FTS match score
    semantic_score: float = 0.0# Text embedding cosine similarity
    visual_score: float = 0.0  # CLIP multimodal cosine similarity
    vlm_score: float = 0.0     # Zero-shot VLM document/visual understanding score
    filename_score: float = 0.0# Exact or substring filename match
    ocr_score: float = 0.0     # OCR match score
    metadata_score: float = 0.0# Metadata match score
    subject_match: float = 0.0 # Compositional subject match
    attribute_match: float = 0.0 # Compositional attribute/color match
    clothing_match: float = 0.0# Compositional clothing match
    object_match: float = 0.0  # Compositional non-clothing object match
    action_match: float = 0.0  # Compositional action/verb match
    relationship_match: float = 0.0 # Compositional relationship match
    scene_match: float = 0.0   # Compositional scene/environment match
    coordination_score: float = 0.0 # Quadratic query coordination score
    contradiction_penalty: float = 0.0 # Contradiction penalty
    matched_terms: List[str] = field(default_factory=list)
    snippet: str = ""
    page_number: Optional[int] = None
    explanation: str = ""

    def formatted_badge(self) -> str:
        """Returns user-facing badge indicating multi-modal retrieval score."""
        return f"Relevance Score: {self.relevance_score:.2f}"

    def debug_dict(self) -> Dict[str, float]:
        """Exposes the required 15 diagnostic scoring fields."""
        return {
            "subject_match": round(self.subject_match, 4),
            "attribute_match": round(self.attribute_match, 4),
            "clothing_match": round(self.clothing_match, 4),
            "object_match": round(self.object_match, 4),
            "action_match": round(self.action_match, 4),
            "relationship_match": round(self.relationship_match, 4),
            "scene_match": round(self.scene_match, 4),
            "CLIP": round(self.visual_score, 4),
            "SBERT": round(self.semantic_score, 4),
            "BM25": round(self.lexical_score, 4),
            "OCR": round(self.ocr_score, 4),
            "metadata": round(self.metadata_score, 4),
            "coordination": round(self.coordination_score, 4),
            "contradiction": round(self.contradiction_penalty, 4),
            "final_score": round(self.relevance_score, 4),
        }


class TextEmbeddingProvider(ABC):
    """
    Contract for local dense text embedding providers.
    Allows substituting models (e.g. all-MiniLM-L6-v2, bge-small, nomic)
    without altering retrieval, storage, or UI code.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier (e.g. 'all-MiniLM-L6-v2')."""
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Model version or revision hash."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality (e.g. 384, 512, 768)."""
        ...

    @property
    @abstractmethod
    def normalization_method(self) -> str:
        """Vector normalization ('l2' or 'none')."""
        ...

    @property
    @abstractmethod
    def preprocessing_version(self) -> str:
        """Tokenizer and text truncation identifier."""
        ...

    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single query or text passage into a 1D float32 numpy array."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embed a sequence of texts into a 2D float32 numpy array [N, dimension]."""
        ...


class VectorStore(ABC):
    """
    Abstract interface for local vector storage and nearest-neighbor search.
    Decoupled from direct SQLite scans to allow plugging in FAISS/HNSW later.
    """

    @abstractmethod
    def add_vectors(
        self,
        entity_type: str,
        entity_ids: List[int],
        vectors: np.ndarray,
        model_name: str,
    ) -> None:
        """Add or update vectors in persistent storage and active memory index."""
        ...

    @abstractmethod
    def query_nearest(
        self,
        query_vector: np.ndarray,
        model_name: str,
        k: int = 50,
        threshold: float = 0.0,
        filter_fn: Optional[Callable[[int], bool]] = None,
    ) -> List[VectorMatch]:
        """Query top-k nearest neighbors sorted by cosine similarity descending."""
        ...

    @abstractmethod
    def delete_vectors(self, entity_type: str, entity_ids: List[int]) -> None:
        """Delete vectors by entity type and ID list."""
        ...

    @abstractmethod
    def rebuild_index(self, model_name: str) -> None:
        """Rebuild or sync the active memory-mapped index from persistent storage."""
        ...


class QueryPlanInterface(ABC):
    """Interface for query parsing, entity extraction, and routing."""

    @abstractmethod
    def parse_query(self, raw_query: str) -> Any:
        """Parse raw user query into a structured execution plan."""
        ...
