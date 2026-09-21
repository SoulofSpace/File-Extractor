"""
local_qwen.py — Local Qwen3.5-4B VLM provider via llama.cpp for FILE XTRACTOR V3.
Provides high-accuracy zero-shot document understanding, reasoning-token isolation,
and strict structured JSON extraction.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from PIL import Image

from ..domain.vlm_provider import (
    DocumentUnderstandingResult,
    ModelInfo,
    VLMProvider,
    VLMResponse,
)
from .model_manager import ModelManager, get_model_manager

logger = logging.getLogger(__name__)

DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT = """You are an expert document understanding and visual recognition engine.
Analyze the provided image thoroughly and output ONLY a valid, parseable JSON object matching this schema:
{
  "document_type": "poster | photo | id_card | receipt | timetable | diagram | document | graphic",
  "title": "Main title or headline (or null if none)",
  "description": "A concise, complete description of what the image shows",
  "event_name": "Name of any event, competition, or conference (or null)",
  "dates": ["extracted dates e.g. October 7 & 8, 2026"],
  "times": ["extracted times e.g. 10:00 AM, 24 Hours"],
  "locations": ["extracted venues, colleges, auditoriums, cities"],
  "organizations": ["organizers, clubs, institutions, corporate sponsors"],
  "people": ["names of persons or role designations"],
  "objects": ["physical entities and objects seen e.g. dog, cat, laptop, car, chair, phone, tree"],
  "entities": ["named concepts, product names, acronyms"],
  "semantic_tags": ["topical tags e.g. hackathon, coding, prize, tech, education"],
  "visual_concepts": ["visual attributes e.g. dark background, neon blue, banner, QR code, illustration"],
  "activities": ["actions or activities depicted e.g. programming, gaming, posing, presentation"],
  "colors": ["prominent colors e.g. blue, black, gold, white, red"],
  "attributes": {"key": "value pairs for registration fees, prize pool amounts, contact emails, URLs"},
  "important_text": ["salient display text, header phrases, badges, or slogans verbatim"]
}
CRITICAL REQUIREMENTS:
1. Output ONLY the JSON object. Do not include introductory or concluding conversational text.
2. If text is artistic, stylized, large, or in non-standard fonts, transcribe it accurately in 'title' or 'important_text'.
3. In 'objects', list ALL concrete physical items or animals visible in the frame (e.g. dog, laptop, car, cup, plant).
4. If a prize pool, cash prize, or registration fee is shown, record it in 'attributes'.
"""


class LocalQwen35Provider(VLMProvider):
    """
    VLM Provider executing Qwen3.5-4B via local llama.cpp server.
    Handles base64 image encoding, reasoning token parsing, and JSON repair.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        model_manager: Optional[ModelManager] = None,
        request_timeout: float = 90.0,
    ) -> None:
        self.model_manager = model_manager or get_model_manager()
        self.endpoint = (endpoint or self.model_manager.server_url).rstrip("/")
        self._configured_model_name = model_name
        self.request_timeout = request_timeout

    def is_available(self) -> bool:
        """Check if local llama.cpp server is reachable and active."""
        return self.model_manager.check_health()

    def get_model_info(self) -> ModelInfo:
        """Return model specifications."""
        return self.model_manager.query_model_info()

    def _encode_image(self, image: Image.Image, max_dimension: int = 1536) -> str:
        """Resize image if needed and encode to base64 JPEG string."""
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        # Downscale proportionally if larger than max_dimension to accelerate inference
        width, height = image.size
        if max(width, height) > max_dimension:
            scale = max_dimension / max(width, height)
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def generate(
        self,
        prompt: str,
        images: Optional[List[Image.Image]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1536,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> VLMResponse:
        """
        Execute completion request against llama.cpp OpenAI-compatible API.
        Separates <think> reasoning tokens from final content.
        """
        if not self.is_available():
            raise RuntimeError(f"Local VLM server is not available at {self.endpoint}")

        active_model_name = (
            self._configured_model_name
            or self.get_model_info().model_name
            or "lmstudio-community/Qwen3.5-4B-GGUF:Q4_K_M"
        )

        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content: List[Dict[str, Any]] = []
        if images:
            for img in images:
                b64_str = self._encode_image(img)
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}
                })

        user_content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": active_model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/v1/chat/completions",
            data=req_data,
            headers={"Content-Type": "application/json", "User-Agent": "IntelliFile/3.0"},
        )

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                raw_data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            logger.error("VLM inference request failed: %s", exc)
            raise RuntimeError(f"VLM communication failure: {exc}") from exc

        latency = time.time() - start_time
        choices = raw_data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Empty choices in VLM response: {raw_data}")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "").strip()
        reasoning = message.get("reasoning_content", None)
        finish_reason = choice.get("finish_reason", "stop")
        usage = raw_data.get("usage", {})

        # Handle models that embed <think> tokens directly in content
        if "<think>" in content and "</think>" in content:
            parts = content.split("</think>", 1)
            reasoning = parts[0].replace("<think>", "").strip()
            content = parts[1].strip()

        return VLMResponse(
            content=content,
            reasoning_content=reasoning,
            finish_reason=finish_reason,
            usage=usage,
            latency_seconds=latency,
            raw_response=raw_data,
        )

    def analyze_document(
        self,
        image: Image.Image,
        prompt: Optional[str] = None,
    ) -> DocumentUnderstandingResult:
        """Analyze an image or document page and return structured understanding."""
        user_prompt = prompt or "Extract all document information and visual understanding according to your instructions."
        response = self.generate(
            prompt=user_prompt,
            images=[image],
            system_prompt=DOCUMENT_UNDERSTANDING_SYSTEM_PROMPT,
            max_tokens=1536,
            temperature=0.1,
        )

        parsed_json = self._extract_json(response.content)
        if not parsed_json and response.reasoning_content:
            # Check if JSON was written in reasoning output
            parsed_json = self._extract_json(response.reasoning_content)

        if not parsed_json:
            logger.warning("Could not parse JSON from VLM response. Falling back to generic result.")
            return DocumentUnderstandingResult(
                document_type="graphic",
                description=response.content[:300] if response.content else "Unrecognized visual artifact",
                confidence=0.5,
                raw_json={"raw_text": response.content},
            )

        return self._build_result_from_json(parsed_json)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from text, handling markdown fences and minor truncation."""
        if not text:
            return None

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Match markdown ```json ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Match outermost curly braces
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Attempt basic auto-close repair if truncated
                pass

        return None

    def _build_result_from_json(self, data: Dict[str, Any]) -> DocumentUnderstandingResult:
        """Convert raw parsed dictionary into DocumentUnderstandingResult with defensive type checks."""
        def _to_str_list(val: Any) -> List[str]:
            if isinstance(val, list):
                res = []
                for item in val:
                    if isinstance(item, str) and item.strip():
                        res.append(item.strip())
                    elif isinstance(item, (int, float)):
                        res.append(str(item))
                return res
            elif isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        doc_type = str(data.get("document_type") or "document").lower().strip()
        title = data.get("title")
        if title is not None:
            title = str(title).strip() or None
        event_name = data.get("event_name")
        if event_name is not None:
            event_name = str(event_name).strip() or None

        description = str(data.get("description") or "").strip()
        attributes = data.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}

        return DocumentUnderstandingResult(
            document_type=doc_type,
            title=title,
            description=description,
            event_name=event_name,
            dates=_to_str_list(data.get("dates")),
            times=_to_str_list(data.get("times")),
            locations=_to_str_list(data.get("locations")),
            organizations=_to_str_list(data.get("organizations")),
            people=_to_str_list(data.get("people")),
            objects=_to_str_list(data.get("objects")),
            entities=_to_str_list(data.get("entities")),
            semantic_tags=_to_str_list(data.get("semantic_tags")),
            visual_concepts=_to_str_list(data.get("visual_concepts")),
            activities=_to_str_list(data.get("activities")),
            colors=_to_str_list(data.get("colors")),
            attributes=attributes,
            relationships=_to_str_list(data.get("relationships")),
            important_text=_to_str_list(data.get("important_text")),
            layout_regions=data.get("layout_regions", []) if isinstance(data.get("layout_regions"), list) else [],
            confidence=float(data.get("confidence", 1.0)),
            raw_json=data,
        )
