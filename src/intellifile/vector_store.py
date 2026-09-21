"""
vector_store.py — SQLiteFlatVectorStore implementation for FILE XTRACTOR V2.
Decoupled vector storage and nearest-neighbor search backed by SQLite BLOB storage
and memory-mapped NumPy matrices for sub-millisecond retrieval.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple
import numpy as np

from .domain.interfaces import VectorMatch, VectorStore


class _ModelIndex:
    """In-memory cache for fast vector dot-product similarity."""

    def __init__(self, dimension: int):
        self.dimension = dimension
        self.entities: List[Tuple[str, int]] = []  # [(entity_type, entity_id), ...]
        self.matrix: Optional[np.ndarray] = None   # Shape: [N, dimension], float32

    def set_vectors(self, entities: List[Tuple[str, int]], matrix: np.ndarray) -> None:
        self.entities = entities
        if len(entities) > 0 and matrix.shape[0] == len(entities):
            # Ensure float32 and L2-normalized
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.matrix = (matrix / norms).astype(np.float32)
        else:
            self.matrix = None


class SQLiteFlatVectorStore(VectorStore):
    """
    Concrete VectorStore backed by SQLite's embeddings table.
    Maintains fast in-memory normalized matrices for zero-friction sub-millisecond
    cosine similarity searches, with zero C++ compilation dependencies.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._indices: Dict[str, _ModelIndex] = {}  # model_name -> _ModelIndex
        self._initialize_table()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize_table(self) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    normalization TEXT NOT NULL DEFAULT 'l2',
                    vector BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(entity_type, entity_id, model_name)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_embeddings_lookup ON embeddings(entity_type, entity_id, model_name);"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_vectors(
        self,
        entity_type: str,
        entity_ids: List[int],
        vectors: np.ndarray,
        model_name: str,
        model_version: str = "v1",
        normalization: str = "l2",
    ) -> None:
        if len(entity_ids) == 0 or len(vectors) == 0:
            return

        if len(entity_ids) != len(vectors):
            raise ValueError(f"Mismatch: {len(entity_ids)} ids vs {len(vectors)} vectors")

        vec_array = np.asarray(vectors, dtype=np.float32)
        dim = int(vec_array.shape[1])
        now = self._now()

        # Batch write to SQLite
        with self._lock, self._connection() as conn:
            params = []
            for eid, vec in zip(entity_ids, vec_array):
                blob = vec.tobytes()
                params.append((entity_type, eid, model_name, model_version, dim, normalization, blob, now))

            conn.executemany(
                """
                INSERT INTO embeddings (
                    entity_type, entity_id, model_name, model_version,
                    dimension, normalization, vector, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id, model_name) DO UPDATE SET
                    model_version = excluded.model_version,
                    dimension = excluded.dimension,
                    normalization = excluded.normalization,
                    vector = excluded.vector,
                    created_at = excluded.created_at
                """,
                params,
            )
            conn.commit()

        # Sync in-memory index
        self.rebuild_index(model_name)

    def query_nearest(
        self,
        query_vector: np.ndarray,
        model_name: str,
        k: int = 50,
        threshold: float = 0.0,
        filter_fn: Optional[Callable[[int], bool]] = None,
    ) -> List[VectorMatch]:
        with self._lock:
            if model_name not in self._indices:
                self.rebuild_index(model_name)

            index = self._indices.get(model_name)
            if index is None or index.matrix is None or len(index.entities) == 0:
                return []

            q = np.asarray(query_vector, dtype=np.float32).flatten()
            norm = np.linalg.norm(q)
            if norm == 0:
                return []
            q = q / norm

            # Cosine similarity via fast matrix-vector dot product
            scores = index.matrix @ q

            # Get indices sorted descending by score
            sorted_indices = np.argsort(-scores)

            matches: List[VectorMatch] = []
            for idx in sorted_indices:
                score = float(scores[idx])
                if score < threshold:
                    break

                entity_type, entity_id = index.entities[idx]
                if filter_fn is not None and not filter_fn(entity_id):
                    continue

                matches.append(
                    VectorMatch(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        similarity=score,
                        metadata={"model_name": model_name},
                    )
                )
                if len(matches) >= k:
                    break

            return matches

    def delete_vectors(self, entity_type: str, entity_ids: List[int]) -> None:
        if not entity_ids:
            return

        with self._lock, self._connection() as conn:
            placeholders = ",".join("?" for _ in entity_ids)
            conn.execute(
                f"DELETE FROM embeddings WHERE entity_type = ? AND entity_id IN ({placeholders})",
                [entity_type] + list(entity_ids),
            )
            conn.commit()

        # Invalidate active in-memory models
        with self._lock:
            for model_name in list(self._indices.keys()):
                self.rebuild_index(model_name)

    def rebuild_index(self, model_name: str) -> None:
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                """
                SELECT entity_type, entity_id, dimension, vector
                FROM embeddings
                WHERE model_name = ?
                ORDER BY id ASC
                """,
                (model_name,),
            ).fetchall()

            if not rows:
                self._indices[model_name] = _ModelIndex(dimension=0)
                return

            dim = int(rows[0]["dimension"])
            entities: List[Tuple[str, int]] = []
            vec_list: List[np.ndarray] = []

            for r in rows:
                entities.append((str(r["entity_type"]), int(r["entity_id"])))
                arr = np.frombuffer(r["vector"], dtype=np.float32)
                vec_list.append(arr)

            matrix = np.vstack(vec_list) if vec_list else np.empty((0, dim), dtype=np.float32)
            idx = _ModelIndex(dimension=dim)
            idx.set_vectors(entities, matrix)
            self._indices[model_name] = idx
