"""
vlm_provider.py — Abstract contracts for Local Vision-Language Models (VLM) in FILE XTRACTOR V3.
Defines interfaces for multimodal document understanding, model info, and generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from PIL import Image


@dataclass
class ModelInfo:
    """Metadata describing a Vision-Language Model."""
    model_name: str
    model_version: str
    backend: str              # e.g., 'llama.cpp', 'transformers', 'vllm'
    endpoint: Optional[str] = None
    context_length: int = 4096
    vision_enabled: bool = True
    quantization: Optional[str] = None  # e.g., 'Q4_K_M'
    device: str = "cuda"                # 'cuda', 'cpu'


@dataclass
class VLMResponse:
    """Raw and processed response from a Vision-Language Model invocation."""
    content: str
    reasoning_content: Optional[str] = None
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    latency_seconds: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class DocumentUnderstandingResult:
    """
    Standardized, structured extraction of a document or visual artifact.
    Used for multi-representation indexing and database persistence.
    """
    document_type: str                   # e.g., 'poster', 'photo', 'id_card', 'receipt', 'document', 'diagram'
    title: Optional[str] = None          # Main title/heading
    description: str = ""                # High-level summary/description
    event_name: Optional[str] = None     # Extracted event name if applicable
    dates: List[str] = field(default_factory=list)
    times: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    organizations: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)          # Physical objects detected (e.g. 'dog', 'laptop')
    entities: List[str] = field(default_factory=list)         # Named entities
    semantic_tags: List[str] = field(default_factory=list)    # Topical categories ('hackathon', 'ai')
    visual_concepts: List[str] = field(default_factory=list)  # Visual descriptors
    activities: List[str] = field(default_factory=list)       # Actions/activities
    colors: List[str] = field(default_factory=list)           # Prominent colors
    attributes: Dict[str, Any] = field(default_factory=dict)  # Key-value pairs (fees, prizes, etc.)
    relationships: List[str] = field(default_factory=list)    # Entity relationships
    important_text: List[str] = field(default_factory=list)   # Salient text blocks visually identified
    layout_regions: List[Dict[str, Any]] = field(default_factory=list) # Visual layout regions
    confidence: float = 1.0
    raw_json: Optional[Dict[str, Any]] = None

    def all_searchable_terms(self) -> List[str]:
        """Aggregate all extracted tokens and concepts into a deduplicated searchable list."""
        terms = set()
        if self.document_type:
            terms.add(self.document_type.lower())
        if self.title:
            for w in self.title.lower().split():
                clean = w.strip(".,;:!?()[]\"'")
                if clean:
                    terms.add(clean)
        if self.event_name:
            for w in self.event_name.lower().split():
                clean = w.strip(".,;:!?()[]\"'")
                if clean:
                    terms.add(clean)
        for collection in (self.dates, self.times, self.locations, self.organizations,
                           self.people, self.objects, self.entities, self.semantic_tags,
                           self.visual_concepts, self.activities, self.colors, self.important_text):
            for item in collection:
                if isinstance(item, str) and item.strip():
                    terms.add(item.strip().lower())
        return sorted(terms)


class VLMProvider(ABC):
    """
    Contract for Vision-Language Models.
    Allows substituting local llama.cpp servers, local GGUF runtimes,
    or other backends without modifying business logic.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the VLM provider is currently accessible and ready for inference."""
        ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return metadata about the underlying model."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        images: Optional[List[Image.Image]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1536,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> VLMResponse:
        """Generate a multimodal response from text prompt and optional images."""
        ...

    @abstractmethod
    def analyze_document(
        self,
        image: Image.Image,
        prompt: Optional[str] = None,
    ) -> DocumentUnderstandingResult:
        """Perform zero-shot structured document/visual understanding on an image."""
        ...
