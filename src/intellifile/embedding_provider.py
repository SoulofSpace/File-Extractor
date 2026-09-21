"""
embedding_provider.py — Dense Text Embedding Provider for FILE XTRACTOR V2.
Implements TextEmbeddingProvider interface wrapping local SentenceTransformers (all-MiniLM-L6-v2)
with GPU acceleration (NVIDIA RTX 4060 CUDA) and offline fallback.
"""

from __future__ import annotations

import os
import threading
from typing import List, Optional
import numpy as np

from .domain.interfaces import TextEmbeddingProvider

try:
    import torch
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except Exception:
    SBERT_AVAILABLE = False


class SentenceTransformerProvider(TextEmbeddingProvider):
    """
    Local dense text embedding provider backed by SentenceTransformers.
    Decoupled from retrieval engine and vector storage; can be hot-swapped for
    any local model (e.g. all-MiniLM-L6-v2, bge-small-en-v1.5, nomic-embed-text).
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        model_version: str = "2.0.0",
        device: Optional[str] = None,
    ):
        self._model_name = model_name
        self._model_version = model_version
        self._dimension = 384  # Default for all-MiniLM-L6-v2; auto-updated on load
        self._model: Optional[SentenceTransformer] = None
        self._lock = threading.Lock()

        # Determine target device (prefer CUDA on RTX 4060 if available)
        if device is not None:
            self._device = device
        elif SBERT_AVAILABLE and torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalization_method(self) -> str:
        return "l2"

    @property
    def preprocessing_version(self) -> str:
        return "sbert-standard-v1"

    def _ensure_model(self) -> SentenceTransformer:
        """Lazily loads the model into device memory only when first queried."""
        if not SBERT_AVAILABLE:
            raise RuntimeError("sentence-transformers is not installed in the environment.")

        if self._model is None:
            with self._lock:
                if self._model is None:
                    # Suppress huggingface hub noise and enforce offline local loading
                    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
                    try:
                        model = SentenceTransformer(self._model_name, device=self._device, local_files_only=True)
                    except Exception:
                        model = SentenceTransformer(self._model_name, device=self._device)
                    # Update dimension from model's actual embedding dimension
                    try:
                        self._dimension = model.get_embedding_dimension()
                    except AttributeError:
                        self._dimension = model.get_sentence_embedding_dimension()
                    self._model = model
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        """
        Embeds a single string into a 1D L2-normalized float32 numpy vector.
        """
        cleaned = text.strip()
        if not cleaned:
            return np.zeros(self._dimension, dtype=np.float32)

        model = self._ensure_model()
        vec = model.encode(
            cleaned,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec.astype(np.float32)

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Embeds a list of strings into a 2D L2-normalized float32 numpy array [N, dimension].
        """
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        model = self._ensure_model()
        cleaned_texts = [t.strip() or " " for t in texts]
        vecs = model.encode(
            cleaned_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)
