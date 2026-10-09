"""
sarvam_service.py — V4 Multilingual & Voice Search Bridge with Sarvam AI.
Implements:
  • Dedicated translation provider using official sarvamai SDK with Mayura v1 (auto -> en-IN)
  • Sarvam Saaras v4 for speech-to-text with direct English translation (mode="translate")
  • Local script and romanized Indian language detection to prevent cloud calls for English
  • SHA-256 translation caching in SQLite and in-memory
  • Zero file/image/OCR leakage to Sarvam (query text and short voice audio only)
  • Robust error handling and 100% graceful offline fallback (never crashes on API failure)
  • Never exposes SARVAM_API_KEY to frontend or logs
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Indic Unicode Blocks: Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam
INDIC_UNICODE_REGEX = re.compile(
    r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F]"
)

# Common Romanized Indian Language Tokens
ROMANIZED_INDIC_TOKENS = {
    # Tamil
    "oda", "kaatu", "kaattu", "kooda", "potta", "irukku", "paaru", "vechu", "padam", "padangal", "eduthu",
    "enaku", "enakku", "nethu", "venum", "kudunga", "irukka", "illai", "enga", "enna",
    "iruntha", "pannu", "kodu", "thanga", "eppadi", "yaar", "yaaru", "neram", "vanthu", "panna", "edutha", "paatha",
    # Hindi
    "ke", "ki", "ka", "ko", "dikhao", "karo", "hai", "kahan", "mera", "meri", "chahiye", "wali", "wale",
    "tasveerein", "tasveer", "mujhe", "dhundo", "bhejo", "lao", "kal", "aaj", "wala", "bhi", "tha", "thi",
    "raha", "rahe", "dedo", "karna", "aur", "sab", "sabhi",
    # Telugu
    "chupinchu", "yokka", "ekkada", "unnayi", "naaku",
    # Malayalam
    "kaanikku", "ude", "evide", "enikku",
}


def _ensure_env_loaded() -> Optional[str]:
    """Ensures SARVAM_API_KEY is loaded into os.environ from .env if present."""
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if key:
        return key

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k == "SARVAM_API_KEY" and v:
                            os.environ["SARVAM_API_KEY"] = v
                            return v
            except Exception:
                pass
    return None


@dataclass
class TranslationResult:
    """Detailed result of a translation attempt."""
    translated_text: str
    was_translated: bool
    source_language: Optional[str] = None
    original_query: str = ""
    cached: bool = False
    error: Optional[str] = None

    def __getitem__(self, idx: int) -> Any:
        # Tuple-like indexing (translated_text, was_translated, source_language)
        if idx == 0:
            return self.translated_text
        elif idx == 1:
            return self.was_translated
        elif idx == 2:
            return self.source_language
        raise IndexError(f"Index {idx} out of range for TranslationResult")

    def __iter__(self):
        return iter((self.translated_text, self.was_translated))


class SarvamService:
    """
    Dedicated translation and voice bridge for FILE XTRACTOR V4.
    Integrates Mayura v1 (auto -> en-IN) for text and Saaras v4 for voice.
    """

    def __init__(self, database: Optional[Any] = None) -> None:
        self.database = database
        self.base_url = "https://api.sarvam.ai"
        self._client = None
        self._client_key: Optional[str] = None
        self._memory_cache: Dict[str, TranslationResult] = {}

    @property
    def api_key(self) -> Optional[str]:
        """Loads SARVAM_API_KEY strictly from the environment variable (or .env)."""
        key = os.environ.get("SARVAM_API_KEY", "").strip()
        if not key:
            key = _ensure_env_loaded()
        return key if key else None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def is_multilingual_enabled(self) -> bool:
        if not self.database:
            return True
        val = self.database.get_privacy_setting("multilingual_search_enabled", None)
        if val is None:
            val = self.database.get_privacy_setting("multilingual_enabled", "1")
        return str(val).strip().lower() not in ("0", "false", "off", "no")

    @property
    def is_voice_enabled(self) -> bool:
        if not self.database:
            return True
        val = self.database.get_privacy_setting("voice_enabled", "1")
        return str(val).strip().lower() not in ("0", "false", "off", "no")

    def _get_sdk_client(self) -> Optional[Any]:
        """Instantiates or returns cached official SarvamAI client."""
        key = self.api_key
        if not key:
            return None
        if self._client is None or self._client_key != key:
            try:
                from sarvamai import SarvamAI
                self._client = SarvamAI(api_subscription_key=key)
                self._client_key = key
            except Exception as e:
                logger.warning("Could not initialize official SarvamAI SDK client: %s", e)
                self._client = None
        return self._client

    def is_multilingual_or_codemixed(self, text: str) -> bool:
        """
        Determines locally if a query is non-English or code-mixed Indian language.
        If False, we skip calling Sarvam entirely to avoid latency, costs, and network calls.
        """
        s = text.strip()
        if not s:
            return False

        # 1. Native Indic script check (Tamil, Devanagari, Telugu, Kannada, etc.)
        if INDIC_UNICODE_REGEX.search(s):
            return True

        # 2. Romanized / Code-mixed Latin script heuristic check
        tokens = [w.lower() for w in re.findall(r"\b\w+\b", s)]
        for t in tokens:
            if t in ROMANIZED_INDIC_TOKENS:
                return True

        return False

    def translate_to_english(self, query: str) -> str:
        """
        Translates multilingual or code-mixed query into English.
        Returns the translated query if translation occurred, or original query if English/failed.
        """
        res = self.translate_query_details(query)
        return res.translated_text

    def translate_query_if_needed(self, query: str) -> Tuple[str, bool]:
        """
        Translates query into English if necessary.
        Returns (english_query, was_translated).
        """
        res = self.translate_query_details(query)
        return res.translated_text, res.was_translated

    def translate_query_details(self, query: str) -> TranslationResult:
        """
        Executes Mayura v1 translation pipeline with caching, local heuristics, and graceful fallback.
        """
        raw_query = query.strip() if query else ""
        if not raw_query:
            return TranslationResult(
                translated_text=query,
                was_translated=False,
                original_query=query,
            )

        # Check privacy / configuration toggle
        if not self.is_multilingual_enabled:
            return TranslationResult(
                translated_text=query,
                was_translated=False,
                original_query=query,
                error="Multilingual search is disabled in privacy settings",
            )

        # Fast local heuristic check: do not call Sarvam for normal English queries
        if not self.is_multilingual_or_codemixed(raw_query):
            return TranslationResult(
                translated_text=query,
                was_translated=False,
                original_query=query,
            )

        # Check in-memory cache
        cache_key = self._compute_cache_key(raw_query, "mayura:v1", "en-IN")
        if cache_key in self._memory_cache:
            hit = self._memory_cache[cache_key]
            return TranslationResult(
                translated_text=hit.translated_text,
                was_translated=True,
                source_language=hit.source_language,
                original_query=query,
                cached=True,
            )

        # Check SQLite persistent cache
        if self.database and hasattr(self.database, "get_translation_cache"):
            try:
                cached_text = self.database.get_translation_cache(cache_key)
                if cached_text:
                    res = TranslationResult(
                        translated_text=cached_text,
                        was_translated=True,
                        source_language=None,
                        original_query=query,
                        cached=True,
                    )
                    self._memory_cache[cache_key] = res
                    return res
            except Exception as e:
                logger.debug("Database translation cache check error: %s", e)

        key = self.api_key
        if not key:
            logger.info("SARVAM_API_KEY not configured. Falling back to local query.")
            return TranslationResult(
                translated_text=query,
                was_translated=False,
                original_query=query,
                error="SARVAM_API_KEY not configured",
            )

        # ── Call Sarvam Mayura v1 ──
        translated_text: Optional[str] = None
        detected_lang: Optional[str] = None
        error_msg: Optional[str] = None

        # Attempt 1: Official sarvamai SDK
        client = self._get_sdk_client()
        if client is not None:
            try:
                from sarvamai.core.api_error import ApiError
                from sarvamai import UnauthorizedError, ForbiddenError, BadRequestError
            except ImportError:
                UnauthorizedError = ForbiddenError = BadRequestError = ApiError = Exception

            try:
                response = client.text.translate(
                    input=raw_query[:500],
                    model="mayura:v1",
                    source_language_code="auto",
                    target_language_code="en-IN",
                )
                translated_text = getattr(response, "translated_text", None)
                detected_lang = getattr(response, "source_language_code", None)
            except UnauthorizedError:
                error_msg = "Authentication failed: invalid SARVAM_API_KEY"
                logger.warning("Sarvam API authentication failed (invalid key).")
            except ForbiddenError:
                error_msg = "Access forbidden for SARVAM_API_KEY"
                logger.warning("Sarvam API access forbidden.")
            except BadRequestError as be:
                error_msg = f"Bad request: {be}"
                logger.warning("Sarvam Mayura translation bad request: %s", be)
            except ApiError as ae:
                error_msg = f"Sarvam API error: {ae}"
                logger.warning("Sarvam API error: %s", ae)
            except Exception as e:
                error_msg = f"SDK call failed: {e}"
                logger.warning("Sarvam SDK call failed: %s. Attempting fallback.", e)

        # Attempt 2: Direct HTTP via httpx fallback (if SDK failed or not available)
        if not translated_text and not error_msg:
            try:
                import httpx

                url = f"{self.base_url}/translate"
                headers = {
                    "api-subscription-key": key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "input": raw_query[:500],
                    "source_language_code": "auto",
                    "target_language_code": "en-IN",
                    "model": "mayura:v1",
                }

                resp = httpx.post(url, headers=headers, json=payload, timeout=8.0)
                if resp.status_code == 200:
                    data = resp.json()
                    translated_text = data.get("translated_text", "").strip()
                    detected_lang = data.get("source_language_code")
                elif resp.status_code in (401, 403):
                    error_msg = "Authentication failed (HTTP 401/403)"
                    logger.warning("Sarvam API authentication failed.")
                elif resp.status_code == 429:
                    error_msg = "Rate limit exceeded (HTTP 429)"
                    logger.warning("Sarvam API rate limit exceeded.")
                else:
                    error_msg = f"HTTP {resp.status_code}"
                    logger.warning("Sarvam Mayura HTTP error: %s", resp.status_code)
            except Exception as e:
                error_msg = f"Network exception: {e}"
                logger.warning("Sarvam translation network exception: %s", e)

        # Handle successful translation
        if translated_text and translated_text.strip():
            clean_translated = translated_text.strip()
            result = TranslationResult(
                translated_text=clean_translated,
                was_translated=True,
                source_language=detected_lang,
                original_query=query,
            )

            # Store in-memory
            self._memory_cache[cache_key] = result

            # Store in SQLite persistent database
            if self.database and hasattr(self.database, "set_translation_cache"):
                try:
                    self.database.set_translation_cache(
                        cache_key=cache_key,
                        original_query_hash=hashlib.sha256(raw_query.encode("utf-8")).hexdigest(),
                        translated_text=clean_translated,
                        model="mayura:v1",
                        source_lang=detected_lang or "auto",
                        target_lang="en-IN",
                    )
                except Exception as e:
                    logger.debug("Failed to persist translation cache to SQLite: %s", e)

            return result

        # Graceful fallback: return original query untouched
        return TranslationResult(
            translated_text=query,
            was_translated=False,
            original_query=query,
            error=error_msg,
        )

    def voice_to_text(self, audio_bytes: bytes, filename: str = "voice_search.wav") -> Optional[str]:
        """
        Transcribes and translates speech to English using Sarvam Saaras v4 (mode="translate").
        Returns the translated English query text.
        """
        if not audio_bytes:
            return None

        if not self.is_voice_enabled:
            return None

        key = self.api_key
        if not key:
            logger.warning("Voice search requires SARVAM_API_KEY to be configured.")
            return None

        try:
            import httpx

            url = f"{self.base_url}/speech-to-text"
            headers = {
                "api-subscription-key": key,
            }
            files = {
                "file": (filename, audio_bytes, "audio/wav"),
            }
            data = {
                "model": "saaras:v4",
                "mode": "translate",
            }

            resp = httpx.post(url, headers=headers, files=files, data=data, timeout=12.0)

            if resp.status_code == 200:
                result = resp.json()
                text = result.get("transcript") or result.get("translated_text") or ""
                return text.strip() if text else None
            elif resp.status_code in (401, 403):
                logger.warning("Sarvam voice search authentication failed.")
            elif resp.status_code == 429:
                logger.warning("Sarvam voice search rate limited.")
            else:
                logger.warning("Sarvam Saaras voice search returned HTTP %s", resp.status_code)

        except Exception as err:
            logger.warning("Voice search network error: %s", err)

        return None

    def transcribe_speech(self, audio_bytes: bytes, mime_type: str = "audio/wav", mode: str = "translate") -> Optional[str]:
        return self.voice_to_text(audio_bytes, filename="voice_search.wav")

    @staticmethod
    def _compute_cache_key(query: str, model: str, target_lang: str) -> str:
        composite = f"{query.strip().lower()}|{model}|{target_lang}"
        return hashlib.sha256(composite.encode("utf-8")).hexdigest()
