"""
search_worker.py — Asynchronous, Non-Blocking Search Worker for FILE XTRACTOR V2.
Executes multi-modal queries (lexical FTS5, dense text embeddings, and CLIP vision)
in background threads via PySide6 QRunnable / QThreadPool, guaranteeing 60fps UI smoothness.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class SearchWorkerSignals(QObject):
    """Qt Signals emitted by SearchWorker upon task completion or error."""
    started = Signal(str)                                    # query_text
    results_ready = Signal(list, float, str)                 # (results, elapsed_ms, query_plan_summary)
    error_occurred = Signal(str)                             # error_message
    finished = Signal()


class SearchWorker(QRunnable):
    """
    Background worker that runs hybrid search queries off the main GUI thread.
    Prevents UI frame drops and freezing during model inference and database queries.
    """

    def __init__(
        self,
        search_fn: Callable[..., List[Dict[str, Any]]],
        query: str,
        category: Optional[str] = None,
        limit: int = 45,
        save_history_fn: Optional[Callable[[str, int, int, str], None]] = None,
    ):
        super().__init__()
        self.search_fn = search_fn
        self.query = query
        self.category = category
        self.limit = limit
        self.save_history_fn = save_history_fn
        self.signals = SearchWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        t0 = time.perf_counter()
        try:
            self.signals.started.emit(self.query)
            results = self.search_fn(
                self.query,
                user_category=self.category,
                limit=self.limit,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            summary = f"Hybrid Search ({len(results)} matches in {elapsed_ms:.1f}ms)"

            # Optionally persist to privacy-preserving search history table
            if self.save_history_fn is not None:
                try:
                    self.save_history_fn(self.query, len(results), int(elapsed_ms), summary)
                except Exception:
                    pass

            self.signals.results_ready.emit(results, elapsed_ms, summary)
        except Exception as exc:
            self.signals.error_occurred.emit(str(exc))
        finally:
            self.signals.finished.emit()
