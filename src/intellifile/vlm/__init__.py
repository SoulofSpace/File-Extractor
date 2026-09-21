"""
vlm — Local Vision-Language Model subsystem for FILE XTRACTOR V3.
"""

from .model_manager import ModelManager, get_model_manager
from .local_qwen import LocalQwen35Provider
from .normalizer import ConceptNormalizer
from .format_normalizer import FormatNormalizer
from .document_understanding import DocumentUnderstandingService

__all__ = [
    "ModelManager",
    "get_model_manager",
    "LocalQwen35Provider",
    "ConceptNormalizer",
    "FormatNormalizer",
    "DocumentUnderstandingService",
]

