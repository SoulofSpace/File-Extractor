"""
domain — Core architectural contracts and domain primitives for FILE XTRACTOR V2.
"""

from .interfaces import (
    TextEmbeddingProvider,
    VectorStore,
    VectorMatch,
    FileIdentity,
    QueryPlanInterface,
    MatchEvidence,
)
from .vlm_provider import (
    VLMProvider,
    ModelInfo,
    VLMResponse,
    DocumentUnderstandingResult,
)

__all__ = [
    "TextEmbeddingProvider",
    "VectorStore",
    "VectorMatch",
    "FileIdentity",
    "QueryPlanInterface",
    "MatchEvidence",
    "VLMProvider",
    "ModelInfo",
    "VLMResponse",
    "DocumentUnderstandingResult",
]

