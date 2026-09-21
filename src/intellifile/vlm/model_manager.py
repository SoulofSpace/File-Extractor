"""
model_manager.py — Hardware inspection and local VLM lifecycle management for FILE XTRACTOR V3.
Detects GPU/VRAM, checks llama.cpp server health, and queries model capabilities.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..domain.vlm_provider import ModelInfo

logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = os.environ.get("INTELLIFILE_VLM_ENDPOINT", "http://127.0.0.1:8080")


@dataclass
class HardwareSpec:
    """Hardware capabilities detected on the host system."""
    gpu_available: bool
    gpu_name: str
    vram_total_mb: int
    vram_free_mb: int
    device_type: str  # 'cuda' or 'cpu'


class ModelManager:
    """
    Manages hardware inspection, server discovery, and model health
    for local Vision-Language Model execution.
    """

    def __init__(self, server_url: str = DEFAULT_SERVER_URL) -> None:
        self.server_url = server_url.rstrip("/")
        self._cached_hardware: Optional[HardwareSpec] = None
        self._last_health_check: float = 0.0
        self._is_server_healthy: bool = False
        self._cached_model_info: Optional[ModelInfo] = None
        self._health_ttl_seconds: float = 5.0

    def detect_hardware(self) -> HardwareSpec:
        """Inspect host GPU, VRAM, and acceleration status."""
        if self._cached_hardware is not None:
            return self._cached_hardware

        gpu_available = False
        gpu_name = "CPU"
        total_vram = 0
        free_vram = 0

        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_name = torch.cuda.get_device_name(0)
                total_vram = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
                free_vram = int(torch.cuda.mem_get_info()[0] / (1024 * 1024))
        except Exception as exc:
            logger.debug("Torch GPU detection unavailable or failed: %s", exc)

        device_type = "cuda" if gpu_available else "cpu"
        self._cached_hardware = HardwareSpec(
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            vram_total_mb=total_vram,
            vram_free_mb=free_vram,
            device_type=device_type,
        )
        return self._cached_hardware

    def check_health(self, force: bool = False) -> bool:
        """Check whether the local llama.cpp server is running and responding."""
        now = time.time()
        if not force and (now - self._last_health_check < self._health_ttl_seconds):
            return self._is_server_healthy

        self._last_health_check = now
        health_url = f"{self.server_url}/health"

        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "IntelliFile/3.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    self._is_server_healthy = True
                    return True
        except Exception as exc:
            logger.debug("Health check failed for %s: %s", health_url, exc)

        # Fallback check on /v1/models if /health is not implemented
        try:
            models_url = f"{self.server_url}/v1/models"
            req = urllib.request.Request(models_url, headers={"User-Agent": "IntelliFile/3.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    self._is_server_healthy = True
                    return True
        except Exception as exc:
            logger.debug("Models endpoint check failed for %s: %s", self.server_url, exc)

        self._is_server_healthy = False
        return False

    def query_model_info(self) -> ModelInfo:
        """Query active model properties from the llama.cpp server."""
        if self._cached_model_info is not None and self._is_server_healthy:
            return self._cached_model_info

        hw = self.detect_hardware()
        default_info = ModelInfo(
            model_name="Qwen3.5-4B-Q4_K_M",
            model_version="1.0",
            backend="llama.cpp",
            endpoint=self.server_url,
            context_length=96768,
            vision_enabled=True,
            quantization="Q4_K_M",
            device=hw.device_type,
        )

        try:
            models_url = f"{self.server_url}/v1/models"
            req = urllib.request.Request(models_url, headers={"User-Agent": "IntelliFile/3.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("data") or data.get("models") or []
                if models:
                    first = models[0]
                    model_id = first.get("id") or first.get("name", "Qwen3.5-4B-Q4_K_M")
                    meta = first.get("meta", {})
                    ctx = meta.get("n_ctx", 96768)
                    ftype = meta.get("ftype", "Q4_K - Medium")
                    capabilities = first.get("capabilities", ["completion", "multimodal"])
                    is_multimodal = "multimodal" in capabilities or "vision" in model_id.lower()

                    default_info = ModelInfo(
                        model_name=model_id,
                        model_version="Qwen3.5-4B",
                        backend="llama.cpp",
                        endpoint=self.server_url,
                        context_length=ctx,
                        vision_enabled=is_multimodal,
                        quantization=ftype,
                        device=hw.device_type,
                    )
        except Exception as exc:
            logger.debug("Could not query model info from server: %s", exc)

        self._cached_model_info = default_info
        return default_info


_global_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Return the global singleton ModelManager."""
    global _global_model_manager
    if _global_model_manager is None:
        _global_model_manager = ModelManager()
    return _global_model_manager
