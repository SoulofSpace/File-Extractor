from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .models import DiscoveredFile

CATEGORY_EXTS = {
    "Document": (
        ".pdf", ".docx", ".doc", ".txt", ".md", ".rtf",
        ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".tsv",
        ".odt", ".ods", ".epub"
    ),
    "Image": (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif", ".svg", ".ico"),
    "Video": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"),
    "Audio": (".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"),
    "Spreadsheet": (".xlsx", ".xls", ".csv", ".tsv"),
    "Presentation": (".pptx", ".ppt"),
    "Code": (
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
        ".cs", ".go", ".rs", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".bat"
    ),
    "Archive": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"),
    "Media": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mp3", ".wav", ".flac", ".aac", ".m4a"),
}


class Database:
    """SQLite persistence for application metadata, FTS full-text search, and OCR text."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS indexed_folders (
                    id INTEGER PRIMARY KEY,
                    path TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL,
                    last_scanned_at TEXT
                );

                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    folder_id INTEGER NOT NULL REFERENCES indexed_folders(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    extension TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    modified_at REAL NOT NULL,
                    indexed_at TEXT NOT NULL,
                    content_hash TEXT,
                    extracted_text TEXT,
                    ocr_text TEXT,
                    indexing_status TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_files_folder_id ON files(folder_id);
                CREATE INDEX IF NOT EXISTS idx_files_status ON files(indexing_status);
                CREATE INDEX IF NOT EXISTS idx_files_ext ON files(extension);

                CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(
                    file_id UNINDEXED,
                    filename,
                    content
                );
                """
            )
            self._migrate_v2(conn)
            self._migrate_v3(conn)
            self._migrate_v4(conn)

    def _migrate_v2(self, conn: sqlite3.Connection) -> None:
        """Applies non-destructive V2 migrations for vector embeddings, pages, jobs, and history."""
        # Safely add columns to indexed_folders if not present
        folder_cols = {r["name"] for r in conn.execute("PRAGMA table_info(indexed_folders)").fetchall()}
        if "watch_enabled" not in folder_cols:
            conn.execute("ALTER TABLE indexed_folders ADD COLUMN watch_enabled INTEGER NOT NULL DEFAULT 1")
        if "scan_duration_ms" not in folder_cols:
            conn.execute("ALTER TABLE indexed_folders ADD COLUMN scan_duration_ms INTEGER DEFAULT 0")
        if "file_count" not in folder_cols:
            conn.execute("ALTER TABLE indexed_folders ADD COLUMN file_count INTEGER DEFAULT 0")
        if "error_count" not in folder_cols:
            conn.execute("ALTER TABLE indexed_folders ADD COLUMN error_count INTEGER DEFAULT 0")

        # Safely add columns to files if not present
        file_cols = {r["name"] for r in conn.execute("PRAGMA table_info(files)").fetchall()}
        if "sha256_hash" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN sha256_hash TEXT")
        if "phash" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN phash TEXT")
        if "duplicate_of_id" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN duplicate_of_id INTEGER REFERENCES files(id) ON DELETE SET NULL")
        if "page_count" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN page_count INTEGER DEFAULT 1")

        # Create new tables and indexes
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256_hash);
            CREATE INDEX IF NOT EXISTS idx_files_phash ON files(phash);
            CREATE INDEX IF NOT EXISTS idx_files_duplicate ON files(duplicate_of_id);
            CREATE INDEX IF NOT EXISTS idx_files_mtime_size ON files(modified_at, size_bytes);

            CREATE TABLE IF NOT EXISTS content_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                text TEXT NOT NULL,
                ocr_text TEXT DEFAULT '',
                word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(file_id, page_number, chunk_index)
            );
            CREATE INDEX IF NOT EXISTS idx_content_pages_file ON content_pages(file_id);

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
            CREATE INDEX IF NOT EXISTS idx_embeddings_lookup ON embeddings(entity_type, entity_id, model_name);

            CREATE TABLE IF NOT EXISTS index_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL REFERENCES indexed_folders(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL UNIQUE,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status_stage ON index_jobs(status, stage);

            CREATE TABLE IF NOT EXISTS media_metadata (
                file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
                duration_seconds REAL,
                resolution TEXT,
                codec TEXT,
                fps REAL,
                is_movie INTEGER NOT NULL DEFAULT 0,
                extracted_tags TEXT
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                query_plan_summary TEXT,
                result_count INTEGER NOT NULL,
                execution_time_ms INTEGER NOT NULL,
                searched_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_history_time ON search_history(searched_at DESC);

            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                query_string TEXT NOT NULL,
                query_plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_run_at TEXT
            );

            PRAGMA user_version = 2;
            """
        )

    def _migrate_v3(self, conn: sqlite3.Connection) -> None:
        """Applies non-destructive V3 migrations for document understanding and multi-representation storage."""
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_understanding (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                page_id INTEGER,
                document_type TEXT NOT NULL,
                title TEXT,
                description TEXT,
                event_name TEXT,
                dates TEXT,
                times TEXT,
                locations TEXT,
                organizations TEXT,
                people TEXT,
                objects TEXT,
                entities TEXT,
                semantic_tags TEXT,
                visual_concepts TEXT,
                activities TEXT,
                colors TEXT,
                attributes TEXT,
                relationships TEXT,
                important_text TEXT,
                layout_regions TEXT,
                raw_response TEXT,
                content_hash TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                model_version TEXT NOT NULL,
                prompt_schema_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(file_id, model, prompt_schema_version)
            );
            CREATE INDEX IF NOT EXISTS idx_doc_und_file ON document_understanding(file_id);
            CREATE INDEX IF NOT EXISTS idx_doc_und_type ON document_understanding(document_type);
            CREATE INDEX IF NOT EXISTS idx_doc_und_hash ON document_understanding(content_hash);

            PRAGMA user_version = 3;
            """
        )

    def _migrate_v4(self, conn: sqlite3.Connection) -> None:
        """Applies non-destructive V4 migrations for Persons, Face Recognition, Privacy Engine, and Translation Cache."""
        file_cols = {r["name"] for r in conn.execute("PRAGMA table_info(files)").fetchall()}
        if "category_v4" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN category_v4 TEXT")
        if "document_type" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN document_type TEXT")
        if "capture_date" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN capture_date TEXT")
        if "date_source" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN date_source TEXT")
        if "privacy_state" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN privacy_state TEXT NOT NULL DEFAULT 'NORMAL'")
        if "sensitivity_class" not in file_cols:
            conn.execute("ALTER TABLE files ADD COLUMN sensitivity_class TEXT")

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_files_privacy ON files(privacy_state);
            CREATE INDEX IF NOT EXISTS idx_files_capture_date ON files(capture_date);
            CREATE INDEX IF NOT EXISTS idx_files_cat_v4 ON files(category_v4);
            CREATE INDEX IF NOT EXISTS idx_files_doc_type ON files(document_type);

            CREATE TABLE IF NOT EXISTS persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                is_cluster INTEGER NOT NULL DEFAULT 0,
                cluster_label TEXT,
                notes TEXT,
                avatar_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_persons_name ON persons(name);
            CREATE INDEX IF NOT EXISTS idx_persons_cluster ON persons(is_cluster);

            CREATE TABLE IF NOT EXISTS person_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                alias TEXT NOT NULL,
                UNIQUE(person_id, alias)
            );
            CREATE INDEX IF NOT EXISTS idx_aliases_alias ON person_aliases(alias);

            CREATE TABLE IF NOT EXISTS face_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                box_x REAL NOT NULL,
                box_y REAL NOT NULL,
                box_w REAL NOT NULL,
                box_h REAL NOT NULL,
                confidence REAL NOT NULL,
                embedding BLOB NOT NULL,
                person_id INTEGER REFERENCES persons(id) ON DELETE SET NULL,
                match_confidence REAL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_face_file ON face_detections(file_id);
            CREATE INDEX IF NOT EXISTS idx_face_person ON face_detections(person_id);

            CREATE TABLE IF NOT EXISTS person_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                source_file_id INTEGER REFERENCES files(id) ON DELETE SET NULL,
                embedding BLOB NOT NULL,
                is_reference INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_person_emb_pid ON person_embeddings(person_id);

            CREATE TABLE IF NOT EXISTS person_file_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                link_type TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                is_confirmed INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(person_id, file_id, link_type)
            );
            CREATE INDEX IF NOT EXISTS idx_pfl_person ON person_file_links(person_id);
            CREATE INDEX IF NOT EXISTS idx_pfl_file ON person_file_links(file_id);

            CREATE TABLE IF NOT EXISTS privacy_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS file_privacy (
                file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
                privacy_state TEXT NOT NULL DEFAULT 'NORMAL',
                sensitivity_class TEXT,
                manual_override INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_fp_state ON file_privacy(privacy_state);

            CREATE TABLE IF NOT EXISTS translation_cache (
                cache_key TEXT PRIMARY KEY,
                original_query_hash TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                model TEXT NOT NULL,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tc_hash ON translation_cache(original_query_hash);

            PRAGMA user_version = 4;
            """
        )


    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_folder(self, path: Path | str) -> int:
        resolved = str(Path(path).resolve())
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO indexed_folders(path, added_at) VALUES (?, ?)",
                (resolved, self.now()),
            )
            row = conn.execute(
                "SELECT id FROM indexed_folders WHERE path = ?", (resolved,)
            ).fetchone()
            return int(row["id"]) if row else 1

    def folders(self) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM indexed_folders ORDER BY added_at DESC"
            ).fetchall()

    def folders_with_counts(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.path, f.added_at, f.last_scanned_at,
                       COUNT(fi.id) AS file_count
                FROM indexed_folders f
                LEFT JOIN files fi ON fi.folder_id = f.id
                GROUP BY f.id
                ORDER BY f.added_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def remove_folder(self, folder_id: int) -> None:
        with self.connection() as conn:
            file_ids = conn.execute(
                "SELECT id FROM files WHERE folder_id = ?", (folder_id,)
            ).fetchall()
            for r in file_ids:
                conn.execute("DELETE FROM file_search WHERE file_id = ?", (str(r["id"]),))
            conn.execute("DELETE FROM indexed_folders WHERE id = ?", (folder_id,))

    def mark_folder_scanned(self, folder_id: int) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE indexed_folders SET last_scanned_at = ? WHERE id = ?",
                (self.now(), folder_id),
            )

    def upsert_file(self, folder_id: int, item: DiscoveredFile) -> int:
        now = self.now()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT id, modified_at, size_bytes FROM files WHERE path = ?", (str(item.path),)
            ).fetchone()
            unchanged = (
                existing is not None
                and existing["modified_at"] == item.modified_at
                and existing["size_bytes"] == item.size
            )
            status = "indexed" if unchanged else "pending_extraction"
            conn.execute(
                """
                INSERT INTO files (
                    folder_id, filename, path, extension, file_type, size_bytes,
                    created_at, modified_at, indexed_at, indexing_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(path) DO UPDATE SET
                    folder_id = excluded.folder_id,
                    filename = excluded.filename,
                    extension = excluded.extension,
                    file_type = excluded.file_type,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at,
                    modified_at = excluded.modified_at,
                    indexed_at = excluded.indexed_at,
                    indexing_status = excluded.indexing_status,
                    error_message = NULL
                """,
                (
                    folder_id,
                    item.path.name,
                    str(item.path),
                    item.extension,
                    item.file_type,
                    item.size,
                    item.created_at,
                    item.modified_at,
                    now,
                    status,
                ),
            )
            row = conn.execute("SELECT id FROM files WHERE path = ?", (str(item.path),)).fetchone()
            file_id = int(row["id"]) if row else 0

            # Ensure FTS always has this file by filename even if it has no extractable text
            if file_id:
                has_fts = conn.execute(
                    "SELECT 1 FROM file_search WHERE file_id = ?", (str(file_id),)
                ).fetchone()
                if not has_fts:
                    conn.execute(
                        "INSERT INTO file_search(file_id, filename, content) VALUES (?, ?, '')",
                        (str(file_id), item.path.name),
                    )
            return file_id

    def mark_file_indexed(self, path: Path | str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE files SET indexing_status = 'indexed', error_message = NULL WHERE path = ?",
                (str(path),),
            )

    def record_error(self, folder_id: int, path: Path, message: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE files SET indexing_status = 'failed', error_message = ? WHERE folder_id = ? AND path = ?",
                (message[:500], folder_id, str(path)),
            )

    def store_file_text(self, path: Path, extracted_text: str = "", ocr_text: str = "") -> None:
        with self.connection() as conn:
            row = conn.execute("SELECT id, filename FROM files WHERE path = ?", (str(path),)).fetchone()
            if row is None:
                return
            conn.execute(
                """
                UPDATE files
                SET extracted_text = ?, ocr_text = ?, indexing_status = 'indexed', error_message = NULL
                WHERE id = ?
                """,
                (extracted_text, ocr_text, row["id"]),
            )
            # Combine both digital text and OCR text for full-text search
            combined_content = (extracted_text + "\n" + ocr_text).strip()
            conn.execute("DELETE FROM file_search WHERE file_id = ?", (str(row["id"]),))
            conn.execute(
                "INSERT INTO file_search(file_id, filename, content) VALUES (?, ?, ?)",
                (str(row["id"]), row["filename"], combined_content),
            )

    def store_extracted_text(self, path: Path, text: str) -> None:
        self.store_file_text(path, extracted_text=text, ocr_text="")

    def keyword_search(
        self,
        query: str,
        category: str | None = None,
        sort_by: str = "rank",
        limit: int = 60,
    ) -> list[dict]:
        # Sanitize query terms for SQLite FTS5: strip punctuation and underscores, preserving Unicode words
        clean_query = re.sub(r"[^\w\s]|_", " ", query).strip()
        parts = [p for p in clean_query.split() if p]
        if not parts:
            return self.get_recent_files(category=category, limit=limit)
        # Short token guard: Only append prefix wildcard * for tokens of length >= 3
        # Tokens of length <= 2 (e.g. 'id', 'os', 'ai') match as exact terms to prevent false-positive overmatching
        terms = " ".join(f"{p}*" if len(p) >= 3 else f'"{p}"' for p in parts)

        with self.connection() as conn:
            sql = """
                SELECT files.*, snippet(file_search, 2, '<b>', '</b>', '…', 18) AS snippet,
                       bm25(file_search) AS rank
                FROM file_search JOIN files ON CAST(file_search.file_id AS INTEGER) = files.id
                WHERE file_search MATCH ?
            """
            params: list[object] = [terms]

            # Normalize category
            norm_cat = (category or "").capitalize()
            if norm_cat in CATEGORY_EXTS:
                placeholders = ",".join("?" for _ in CATEGORY_EXTS[norm_cat])
                sql += f" AND LOWER(files.extension) IN ({placeholders})"
                params.extend(CATEGORY_EXTS[norm_cat])

            # Sorting
            if sort_by == "size":
                sql += " ORDER BY files.size_bytes DESC LIMIT ?"
            elif sort_by == "date":
                sql += " ORDER BY files.modified_at DESC LIMIT ?"
            else:
                sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_recent_files(self, category: str | None = None, limit: int = 30) -> list[dict]:
        with self.connection() as conn:
            sql = "SELECT *, '' AS snippet, 0 AS rank FROM files WHERE indexing_status = 'indexed'"
            params: list[object] = []
            norm_cat = (category or "").capitalize()
            if norm_cat in CATEGORY_EXTS:
                placeholders = ",".join("?" for _ in CATEGORY_EXTS[norm_cat])
                sql += f" AND LOWER(extension) IN ({placeholders})"
                params.extend(CATEGORY_EXTS[norm_cat])
            sql += " ORDER BY indexed_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_videos(self, sort_by: str = "size", limit: int = 50) -> list[dict]:
        """Convenience method to retrieve video and movie files sorted by size or recency."""
        video_exts = CATEGORY_EXTS["Video"]
        placeholders = ",".join("?" for _ in video_exts)
        order_col = "size_bytes DESC" if sort_by == "size" else "modified_at DESC"
        with self.connection() as conn:
            sql = f"""
                SELECT *, '' AS snippet, 0 AS rank FROM files
                WHERE LOWER(extension) IN ({placeholders})
                ORDER BY {order_col} LIMIT ?
            """
            rows = conn.execute(sql, list(video_exts) + [limit]).fetchall()
            return [dict(r) for r in rows]

    def get_failed_files(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE indexing_status = 'failed' ORDER BY indexed_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_file_by_path(self, file_path: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM files WHERE path = ?", (file_path,)).fetchone()
            return dict(row) if row else None

    def get_file_by_id(self, file_id: int) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            return dict(row) if row else None

    def total_file_count(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    def total_folder_count(self) -> int:
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM indexed_folders").fetchone()[0]

    def statistics(self) -> dict[str, int]:
        with self.connection() as conn:
            total_folders = conn.execute("SELECT COUNT(*) FROM indexed_folders").fetchone()[0]
            total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            indexed_count = conn.execute("SELECT COUNT(*) FROM files WHERE indexing_status = 'indexed'").fetchone()[0]
            processing_count = conn.execute("SELECT COUNT(*) FROM files WHERE indexing_status = 'pending_extraction'").fetchone()[0]
            failed_count = conn.execute("SELECT COUNT(*) FROM files WHERE indexing_status = 'failed'").fetchone()[0]

        return {
            "folders": total_folders,
            "indexed": indexed_count,
            "total": total_files,
            "processing": processing_count,
            "failed": failed_count,
        }

    # ── Search History & Saved Searches ──────────────────────────────
    def add_search_history(
        self,
        query_text: str,
        result_count: int,
        execution_time_ms: int,
        query_plan_summary: str = "",
    ) -> None:
        """Records a search query for history dropdown without logging document text."""
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO search_history (query_text, query_plan_summary, result_count, execution_time_ms, searched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (query_text.strip(), query_plan_summary, result_count, execution_time_ms, self.now()),
            )

    def get_search_history(self, limit: int = 15) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM search_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_search_history(self) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM search_history")

    def add_saved_search(self, name: str, query_string: str, query_plan_json: str = "{}") -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO saved_searches (name, query_string, query_plan_json, created_at, last_run_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), query_string.strip(), query_plan_json, self.now(), self.now()),
            )
            return int(cursor.lastrowid)

    def get_saved_searches(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_searches ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_saved_search(self, search_id: int) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM saved_searches WHERE id = ?", (search_id,))

    # ── Cryptographic Hashing & Duplicate Detection ──────────────────
    def update_file_hash(
        self,
        file_id: int,
        sha256_hash: str,
        phash: str | None = None,
        duplicate_of_id: int | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE files
                SET sha256_hash = ?, phash = ?, duplicate_of_id = ?
                WHERE id = ?
                """,
                (sha256_hash, phash, duplicate_of_id, file_id),
            )

    def find_exact_duplicates(self) -> list[dict]:
        """Returns groups of files that share identical SHA-256 hashes."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT sha256_hash, COUNT(*) as copy_count, GROUP_CONCAT(path, '|||') as paths
                FROM files
                WHERE sha256_hash IS NOT NULL AND sha256_hash != ''
                GROUP BY sha256_hash
                HAVING COUNT(*) > 1
                ORDER BY copy_count DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Page-Level Content Storage ───────────────────────────────────
    def store_page_content(
        self,
        file_id: int,
        page_number: int,
        chunk_index: int,
        text: str,
        ocr_text: str = "",
    ) -> None:
        word_count = len((text + " " + ocr_text).split())
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO content_pages (file_id, page_number, chunk_index, text, ocr_text, word_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, page_number, chunk_index) DO UPDATE SET
                    text = excluded.text,
                    ocr_text = excluded.ocr_text,
                    word_count = excluded.word_count,
                    created_at = excluded.created_at
                """,
                (file_id, page_number, chunk_index, text, ocr_text, word_count, self.now()),
            )

    def get_pages_for_file(self, file_id: int) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM content_pages WHERE file_id = ? ORDER BY page_number ASC, chunk_index ASC",
                (file_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Crash-Resumable Indexing Checkpoints ─────────────────────────
    def upsert_index_job(
        self,
        folder_id: int,
        file_path: str,
        stage: str,
        status: str,
        error: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO index_jobs (folder_id, file_path, stage, status, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    stage = excluded.stage,
                    status = excluded.status,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (folder_id, file_path, stage, status, error, self.now()),
            )

    def get_pending_index_jobs(self) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM index_jobs WHERE status IN ('pending', 'in_progress') ORDER BY id ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Media & Video Metadata ───────────────────────────────────────
    def store_media_metadata(
        self,
        file_id: int,
        duration_seconds: float | None = None,
        resolution: str | None = None,
        codec: str | None = None,
        fps: float | None = None,
        is_movie: bool = False,
        extracted_tags: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO media_metadata (file_id, duration_seconds, resolution, codec, fps, is_movie, extracted_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    duration_seconds = excluded.duration_seconds,
                    resolution = excluded.resolution,
                    codec = excluded.codec,
                    fps = excluded.fps,
                    is_movie = excluded.is_movie,
                    extracted_tags = excluded.extracted_tags
                """,
                (file_id, duration_seconds, resolution, codec, fps, 1 if is_movie else 0, extracted_tags),
            )

    # ── Universal Document & Visual Understanding (V3) ───────────────
    def upsert_document_understanding(
        self,
        file_id: int,
        result: Any,  # DocumentUnderstandingResult
        content_hash: str,
        provider: str = "local_qwen",
        model: str = "Qwen3.5-4B-Q4_K_M",
        model_version: str = "1.0",
        prompt_schema_version: str = "v1",
    ) -> int:
        """Store or update structured document understanding and enrich FTS5 full-text index."""
        now = self.now()
        dates_json = json.dumps(getattr(result, "dates", []), ensure_ascii=False)
        times_json = json.dumps(getattr(result, "times", []), ensure_ascii=False)
        locations_json = json.dumps(getattr(result, "locations", []), ensure_ascii=False)
        orgs_json = json.dumps(getattr(result, "organizations", []), ensure_ascii=False)
        people_json = json.dumps(getattr(result, "people", []), ensure_ascii=False)
        objects_json = json.dumps(getattr(result, "objects", []), ensure_ascii=False)
        entities_json = json.dumps(getattr(result, "entities", []), ensure_ascii=False)
        tags_json = json.dumps(getattr(result, "semantic_tags", []), ensure_ascii=False)
        concepts_json = json.dumps(getattr(result, "visual_concepts", []), ensure_ascii=False)
        activities_json = json.dumps(getattr(result, "activities", []), ensure_ascii=False)
        colors_json = json.dumps(getattr(result, "colors", []), ensure_ascii=False)
        attrs_json = json.dumps(getattr(result, "attributes", {}), ensure_ascii=False)
        relationships_json = json.dumps(getattr(result, "relationships", []), ensure_ascii=False)
        important_text_json = json.dumps(getattr(result, "important_text", []), ensure_ascii=False)
        layout_json = json.dumps(getattr(result, "layout_regions", []), ensure_ascii=False)
        raw_resp = json.dumps(getattr(result, "raw_json", {}) or {}, ensure_ascii=False)

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO document_understanding (
                    file_id, page_id, document_type, title, description, event_name,
                    dates, times, locations, organizations, people, objects, entities,
                    semantic_tags, visual_concepts, activities, colors, attributes,
                    relationships, important_text, layout_regions, raw_response,
                    content_hash, provider, model, model_version, prompt_schema_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, model, prompt_schema_version) DO UPDATE SET
                    document_type = excluded.document_type,
                    title = excluded.title,
                    description = excluded.description,
                    event_name = excluded.event_name,
                    dates = excluded.dates,
                    times = excluded.times,
                    locations = excluded.locations,
                    organizations = excluded.organizations,
                    people = excluded.people,
                    objects = excluded.objects,
                    entities = excluded.entities,
                    semantic_tags = excluded.semantic_tags,
                    visual_concepts = excluded.visual_concepts,
                    activities = excluded.activities,
                    colors = excluded.colors,
                    attributes = excluded.attributes,
                    relationships = excluded.relationships,
                    important_text = excluded.important_text,
                    layout_regions = excluded.layout_regions,
                    raw_response = excluded.raw_response,
                    content_hash = excluded.content_hash,
                    provider = excluded.provider,
                    model_version = excluded.model_version,
                    updated_at = excluded.updated_at
                """,
                (
                    file_id,
                    None,
                    getattr(result, "document_type", "document"),
                    getattr(result, "title", None),
                    getattr(result, "description", ""),
                    getattr(result, "event_name", None),
                    dates_json,
                    times_json,
                    locations_json,
                    orgs_json,
                    people_json,
                    objects_json,
                    entities_json,
                    tags_json,
                    concepts_json,
                    activities_json,
                    colors_json,
                    attrs_json,
                    relationships_json,
                    important_text_json,
                    layout_json,
                    raw_resp,
                    content_hash,
                    provider,
                    model,
                    model_version,
                    prompt_schema_version,
                    now,
                    now,
                ),
            )
            row_id = cursor.lastrowid or 0

            # Enrich FTS5 file_search with extracted understanding so natural lexical queries find it
            f_row = conn.execute(
                "SELECT filename, extracted_text, ocr_text FROM files WHERE id = ?",
                (file_id,),
            ).fetchone()
            if f_row:
                searchable_terms = ""
                if hasattr(result, "all_searchable_terms"):
                    searchable_terms = " ".join(result.all_searchable_terms())
                else:
                    searchable_terms = f"{getattr(result, 'title', '') or ''} {getattr(result, 'event_name', '') or ''}"

                desc = getattr(result, "description", "") or ""
                combined_content = f"{(f_row['extracted_text'] or '')}\n{(f_row['ocr_text'] or '')}\n{searchable_terms}\n{desc}".strip()
                conn.execute("DELETE FROM file_search WHERE file_id = ?", (str(file_id),))
                conn.execute(
                    "INSERT INTO file_search(file_id, filename, content) VALUES (?, ?, ?)",
                    (str(file_id), f_row["filename"], combined_content),
                )

            return row_id

    def get_document_understanding(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve stored document understanding record by file ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM document_understanding WHERE file_id = ? ORDER BY id DESC LIMIT 1",
                (file_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_document_understanding_by_hash(
        self,
        content_hash: str,
        model: Optional[str] = None,
        prompt_schema_version: str = "v1",
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached understanding by content hash for fast-path indexing avoidance."""
        with self.connection() as conn:
            if model:
                row = conn.execute(
                    """
                    SELECT * FROM document_understanding
                    WHERE content_hash = ? AND model = ? AND prompt_schema_version = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (content_hash, model, prompt_schema_version),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM document_understanding
                    WHERE content_hash = ? AND prompt_schema_version = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (content_hash, prompt_schema_version),
                ).fetchone()
            return dict(row) if row else None

    def search_document_understanding(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search document understanding records by concept, object, tag, title, or description."""
        COMMON_STOPWORDS = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "by", "with",
            "and", "or", "is", "it", "as", "from", "into", "onto", "my", "me",
            "this", "that", "these", "those",
        }
        ALLOWED_SHORT_TOKENS = {
            "ai", "ml", "ui", "ux", "os", "id", "qa", "db", "vr", "ar", "cv", "ip",
        }

        raw_tokens = [t.strip().lower() for t in re.sub(r"[^\w\s]|_", " ", query).split() if t.strip()]
        significant_tokens = [
            t for t in raw_tokens
            if (len(t) > 2 and t not in COMMON_STOPWORDS) or (t in ALLOWED_SHORT_TOKENS)
        ]
        tokens = significant_tokens if significant_tokens else [t for t in raw_tokens if t not in {"a", "an", "the"}]
        if not tokens:
            return []

        token_clauses = []
        clause_params: List[Any] = []
        for t in tokens:
            pattern = f"%{t}%"
            clause = (
                "(LOWER(du.title) LIKE ? OR LOWER(du.event_name) LIKE ? OR LOWER(du.document_type) LIKE ? "
                "OR LOWER(du.objects) LIKE ? OR LOWER(du.semantic_tags) LIKE ? OR LOWER(du.visual_concepts) LIKE ? "
                "OR LOWER(du.description) LIKE ? OR LOWER(du.important_text) LIKE ?)"
            )
            token_clauses.append(clause)
            clause_params.extend([pattern] * 8)

        match_score_sql = " + ".join(f"(CASE WHEN {c} THEN 1 ELSE 0 END)" for c in token_clauses)
        where_sql = " OR ".join(token_clauses)

        sql = f"""
            SELECT du.*, f.path, f.filename, f.file_type, f.size_bytes,
                   ({match_score_sql}) AS match_count
            FROM document_understanding du
            JOIN files f ON du.file_id = f.id
            WHERE ({where_sql})
            ORDER BY match_count DESC, du.id DESC
            LIMIT ?
        """
        all_params = clause_params + clause_params + [limit * 2]
        with self.connection() as conn:
            rows = conn.execute(sql, all_params).fetchall()
            scored_rows = []
            for r in rows:
                du_dict = dict(r)
                combined_text = " ".join([
                    str(du_dict.get("title") or ""),
                    str(du_dict.get("event_name") or ""),
                    str(du_dict.get("document_type") or ""),
                    str(du_dict.get("objects") or ""),
                    str(du_dict.get("semantic_tags") or ""),
                    str(du_dict.get("visual_concepts") or ""),
                    str(du_dict.get("description") or ""),
                    str(du_dict.get("important_text") or ""),
                ]).lower()
                word_set = set(re.findall(r"\b\w+\b", combined_text))
                matched_tokens = [t for t in tokens if t in word_set]
                exact_matches = len(matched_tokens)

                if exact_matches > 0:
                    du_dict["match_count"] = exact_matches
                    scored_rows.append(du_dict)

            scored_rows.sort(key=lambda x: (x["match_count"], x.get("id", 0)), reverse=True)
            return scored_rows[:limit]

    # ── V4 Persons Management ──────────────────────────────────────────────────

    def create_person(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        avatar_file_id: Optional[int] = None,
        notes: str = "",
        is_cluster: bool = False,
        cluster_label: Optional[str] = None,
    ) -> int:
        now = self.now()
        name_clean = name.strip()
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO persons (name, is_cluster, cluster_label, notes, avatar_file_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name_clean, 1 if is_cluster else 0, cluster_label, notes, avatar_file_id, now, now),
            )
            person_id = cur.lastrowid
            if aliases:
                for a in aliases:
                    alias_str = a.strip()
                    if alias_str and alias_str.lower() != name_clean.lower():
                        conn.execute(
                            "INSERT OR IGNORE INTO person_aliases (person_id, alias) VALUES (?, ?)",
                            (person_id, alias_str),
                        )
            return person_id

    def get_person(self, person_id: int) -> Optional[dict]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM persons WHERE id = ?", (person_id,)).fetchone()
            if not row:
                return None
            p = dict(row)
            alias_rows = conn.execute(
                "SELECT alias FROM person_aliases WHERE person_id = ? ORDER BY alias", (person_id,)
            ).fetchall()
            p["aliases"] = [r["alias"] for r in alias_rows]
            return p

    def list_persons(self, include_clusters: bool = True, privacy_scope: str = "NORMAL") -> List[dict]:
        where_clause = "" if include_clusters else "WHERE p.is_cluster = 0"
        hidden_filter = "AND f.privacy_state != 'HIDDEN'" if privacy_scope != "PRIVATE" else ""
        sql = f"""
            SELECT p.*,
                   COUNT(DISTINCT CASE WHEN pfl.link_type = 'face' {hidden_filter} THEN pfl.file_id END) AS photo_count,
                   COUNT(DISTINCT CASE WHEN pfl.link_type IN ('ocr', 'filename', 'entity') {hidden_filter} THEN pfl.file_id END) AS doc_count,
                   COUNT(DISTINCT CASE WHEN 1=1 {hidden_filter} THEN pfl.file_id END) AS total_files_count
            FROM persons p
            LEFT JOIN person_file_links pfl ON pfl.person_id = p.id
            LEFT JOIN files f ON pfl.file_id = f.id
            {where_clause}
            GROUP BY p.id
            ORDER BY p.is_cluster ASC, p.name COLLATE NOCASE ASC
        """
        with self.connection() as conn:
            rows = conn.execute(sql).fetchall()
            results = []
            for r in rows:
                p = dict(r)
                aliases = conn.execute(
                    "SELECT alias FROM person_aliases WHERE person_id = ? ORDER BY alias", (p["id"],)
                ).fetchall()
                p["aliases"] = [a["alias"] for a in aliases]
                results.append(p)
            return results

    def update_person(
        self,
        person_id: int,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        avatar_file_id: Optional[int] = None,
        is_cluster: Optional[bool] = None,
    ) -> None:
        now = self.now()
        updates = ["updated_at = ?"]
        params: List[Any] = [now]
        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if avatar_file_id is not None:
            updates.append("avatar_file_id = ?")
            params.append(avatar_file_id)
        if is_cluster is not None:
            updates.append("is_cluster = ?")
            params.append(1 if is_cluster else 0)
        params.append(person_id)

        with self.connection() as conn:
            conn.execute(f"UPDATE persons SET {', '.join(updates)} WHERE id = ?", params)

    def delete_person(self, person_id: int) -> None:
        """Deletes person identity, aliases, embeddings and file links. Does NOT delete original files."""
        with self.connection() as conn:
            conn.execute("UPDATE face_detections SET person_id = NULL WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM person_embeddings WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM person_file_links WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM person_aliases WHERE person_id = ?", (person_id,))
            conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))

    def add_person_alias(self, person_id: int, alias: str) -> None:
        alias_clean = alias.strip()
        if not alias_clean:
            return
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO person_aliases (person_id, alias) VALUES (?, ?)",
                (person_id, alias_clean),
            )

    def remove_person_alias(self, person_id: int, alias: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "DELETE FROM person_aliases WHERE person_id = ? AND alias = ?",
                (person_id, alias.strip()),
            )

    def find_person_by_name_or_alias(self, name_or_alias: str) -> Optional[dict]:
        target = name_or_alias.strip().lower()
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT p.* FROM persons p
                LEFT JOIN person_aliases pa ON pa.person_id = p.id
                WHERE LOWER(p.name) = ? OR LOWER(pa.alias) = ?
                LIMIT 1
                """,
                (target, target),
            ).fetchone()
            if not row:
                return None
            return self.get_person(row["id"])

    def merge_persons(self, source_person_id: int, target_person_id: int) -> None:
        """Merges source person into target person (moves aliases, embeddings, links, face detections)."""
        if source_person_id == target_person_id:
            return
        now = self.now()
        with self.connection() as conn:
            # Move aliases
            conn.execute(
                "UPDATE OR IGNORE person_aliases SET person_id = ? WHERE person_id = ?",
                (target_person_id, source_person_id),
            )
            # Add source person's name as an alias for target person if not present
            source_row = conn.execute("SELECT name FROM persons WHERE id = ?", (source_person_id,)).fetchone()
            if source_row:
                conn.execute(
                    "INSERT OR IGNORE INTO person_aliases (person_id, alias) VALUES (?, ?)",
                    (target_person_id, source_row["name"]),
                )
            # Move embeddings
            conn.execute(
                "UPDATE person_embeddings SET person_id = ? WHERE person_id = ?",
                (target_person_id, source_person_id),
            )
            # Move face detections
            conn.execute(
                "UPDATE face_detections SET person_id = ? WHERE person_id = ?",
                (target_person_id, source_person_id),
            )
            # Move file links
            conn.execute(
                "UPDATE OR IGNORE person_file_links SET person_id = ? WHERE person_id = ?",
                (target_person_id, source_person_id),
            )
            conn.execute("DELETE FROM person_file_links WHERE person_id = ?", (source_person_id,))
            conn.execute("DELETE FROM persons WHERE id = ?", (source_person_id,))
            conn.execute("UPDATE persons SET updated_at = ? WHERE id = ?", (now, target_person_id))

    def split_person(
        self,
        person_id: int,
        new_person_name: str,
        detection_ids: Optional[List[int]] = None,
        file_ids: Optional[List[int]] = None,
    ) -> int:
        """Splits selected face detections or file links into a new person identity."""
        new_pid = self.create_person(new_person_name)
        with self.connection() as conn:
            if detection_ids:
                pl = ",".join("?" for _ in detection_ids)
                conn.execute(
                    f"UPDATE face_detections SET person_id = ? WHERE id IN ({pl}) AND person_id = ?",
                    [new_pid] + list(detection_ids) + [person_id],
                )
            if file_ids:
                pl = ",".join("?" for _ in file_ids)
                conn.execute(
                    f"UPDATE person_file_links SET person_id = ? WHERE file_id IN ({pl}) AND person_id = ?",
                    [new_pid] + list(file_ids) + [person_id],
                )
        return new_pid

    def name_cluster(self, cluster_id: int, person_name: str) -> int:
        """Names an unknown cluster as an approved person identity."""
        now = self.now()
        with self.connection() as conn:
            conn.execute(
                "UPDATE persons SET name = ?, is_cluster = 0, updated_at = ? WHERE id = ?",
                (person_name.strip(), now, cluster_id),
            )
        return cluster_id

    # ── V4 Face Detections & Embeddings ───────────────────────────────────────

    def add_face_detection(
        self,
        file_id: int,
        box_x: float,
        box_y: float,
        box_w: float,
        box_h: float,
        confidence: float,
        embedding: bytes,
        person_id: Optional[int] = None,
        match_confidence: Optional[float] = None,
    ) -> int:
        now = self.now()
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO face_detections (file_id, box_x, box_y, box_w, box_h, confidence, embedding, person_id, match_confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, box_x, box_y, box_w, box_h, confidence, embedding, person_id, match_confidence, now),
            )
            return cur.lastrowid

    def get_face_detections(
        self, file_id: Optional[int] = None, person_id: Optional[int] = None
    ) -> List[dict]:
        with self.connection() as conn:
            if file_id is not None:
                rows = conn.execute(
                    "SELECT * FROM face_detections WHERE file_id = ? ORDER BY id", (file_id,)
                ).fetchall()
            elif person_id is not None:
                rows = conn.execute(
                    "SELECT * FROM face_detections WHERE person_id = ? ORDER BY id", (person_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM face_detections ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    def add_person_embedding(
        self,
        person_id: int,
        embedding: bytes,
        source_file_id: Optional[int] = None,
        is_reference: bool = True,
    ) -> int:
        now = self.now()
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO person_embeddings (person_id, source_file_id, embedding, is_reference, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (person_id, source_file_id, embedding, 1 if is_reference else 0, now),
            )
            return cur.lastrowid

    def get_all_person_embeddings(self) -> List[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT pe.*, p.name, p.is_cluster
                FROM person_embeddings pe
                JOIN persons p ON pe.person_id = p.id
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def link_person_to_file(
        self,
        person_id: int,
        file_id: int,
        link_type: str = "face",
        confidence: float = 1.0,
        is_confirmed: bool = False,
        notes: str = "",
    ) -> None:
        now = self.now()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO person_file_links (person_id, file_id, link_type, confidence, is_confirmed, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id, file_id, link_type) DO UPDATE SET
                    confidence = MAX(confidence, excluded.confidence),
                    is_confirmed = MAX(is_confirmed, excluded.is_confirmed),
                    notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE notes END
                """,
                (person_id, file_id, link_type, confidence, 1 if is_confirmed else 0, notes, now),
            )

    def get_person_files(self, person_id: int, privacy_scope: str = "NORMAL") -> List[dict]:
        hidden_filter = "AND f.privacy_state != 'HIDDEN'" if privacy_scope != "PRIVATE" else ""
        sql = f"""
            SELECT f.*, pfl.link_type, pfl.confidence AS link_confidence, pfl.is_confirmed AS link_confirmed
            FROM person_file_links pfl
            JOIN files f ON pfl.file_id = f.id
            WHERE pfl.person_id = ? {hidden_filter}
            ORDER BY pfl.is_confirmed DESC, pfl.confidence DESC, f.id DESC
        """
        with self.connection() as conn:
            rows = conn.execute(sql, (person_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_file_persons(self, file_id: int) -> List[dict]:
        sql = """
            SELECT p.*, pfl.link_type, pfl.confidence, pfl.is_confirmed
            FROM person_file_links pfl
            JOIN persons p ON pfl.person_id = p.id
            WHERE pfl.file_id = ?
            ORDER BY pfl.confidence DESC
        """
        with self.connection() as conn:
            rows = conn.execute(sql, (file_id,)).fetchall()
            return [dict(r) for r in rows]

    # ── V4 Privacy Engine & Settings ───────────────────────────────────────────

    def get_privacy_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute("SELECT value FROM privacy_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_privacy_setting(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO privacy_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def get_all_privacy_settings(self) -> Dict[str, str]:
        with self.connection() as conn:
            rows = conn.execute("SELECT key, value FROM privacy_settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

    def update_file_privacy(
        self,
        file_id: int,
        privacy_state: str,
        sensitivity_class: Optional[str] = None,
        manual: bool = False,
    ) -> None:
        now = self.now()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO file_privacy (file_id, privacy_state, sensitivity_class, manual_override, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    privacy_state = excluded.privacy_state,
                    sensitivity_class = COALESCE(excluded.sensitivity_class, sensitivity_class),
                    manual_override = excluded.manual_override,
                    updated_at = excluded.updated_at
                """,
                (file_id, privacy_state.upper(), sensitivity_class, 1 if manual else 0, now),
            )
            # Synchronize to files table
            conn.execute(
                "UPDATE files SET privacy_state = ?, sensitivity_class = COALESCE(?, sensitivity_class) WHERE id = ?",
                (privacy_state.upper(), sensitivity_class, file_id),
            )

    def get_file_privacy(self, file_id: int) -> dict:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM file_privacy WHERE file_id = ?", (file_id,)).fetchone()
            if row:
                return dict(row)
            f_row = conn.execute("SELECT privacy_state, sensitivity_class FROM files WHERE id = ?", (file_id,)).fetchone()
            if f_row:
                return {
                    "file_id": file_id,
                    "privacy_state": f_row["privacy_state"] or "NORMAL",
                    "sensitivity_class": f_row["sensitivity_class"] or "None",
                    "manual_override": 0,
                }
            return {"file_id": file_id, "privacy_state": "NORMAL", "sensitivity_class": "None", "manual_override": 0}

    def update_file_v4_metadata(
        self,
        file_id: int,
        category_v4: Optional[str] = None,
        document_type: Optional[str] = None,
        capture_date: Optional[str] = None,
        date_source: Optional[str] = None,
        sensitivity_class: Optional[str] = None,
        privacy_state: Optional[str] = None,
    ) -> None:
        updates = []
        params = []
        if category_v4 is not None:
            updates.append("category_v4 = ?")
            params.append(category_v4)
        if document_type is not None:
            updates.append("document_type = ?")
            params.append(document_type)
        if capture_date is not None:
            updates.append("capture_date = ?")
            params.append(capture_date)
        if date_source is not None:
            updates.append("date_source = ?")
            params.append(date_source)
        if sensitivity_class is not None:
            updates.append("sensitivity_class = ?")
            params.append(sensitivity_class)
        if privacy_state is not None:
            updates.append("privacy_state = ?")
            params.append(privacy_state.upper())
        if not updates:
            return
        params.append(file_id)
        with self.connection() as conn:
            conn.execute(f"UPDATE files SET {', '.join(updates)} WHERE id = ?", params)

    # ── V4 Sarvam Translation Cache ───────────────────────────────────────────

    def get_translation_cache(self, cache_key: str) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT translated_text FROM translation_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            return row["translated_text"] if row else None

    def set_translation_cache(
        self,
        cache_key: str,
        original_query_hash: str,
        translated_text: str,
        model: str,
        source_lang: str,
        target_lang: str,
    ) -> None:
        now = self.now()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO translation_cache
                (cache_key, original_query_hash, translated_text, model, source_lang, target_lang, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (cache_key, original_query_hash, translated_text, model, source_lang, target_lang, now),
            )

    def clear_translation_cache(self) -> int:
        with self.connection() as conn:
            cur = conn.execute("DELETE FROM translation_cache")
            return cur.rowcount


