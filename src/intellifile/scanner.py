import logging
import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

from .database import Database
from .extractors import extract_file_content
from .models import DiscoveredFile, SUPPORTED_EXTENSIONS
from .domain.hashing import fast_mtime_size_check, compute_sha256
from .domain.phash import compute_phash

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

# Extensions eligible for text or OCR extraction
EXTRACTABLE_EXTENSIONS = {
    # Text documents & code
    ".pdf", ".docx", ".txt", ".md", ".json", ".csv", ".py", ".js",
    ".ts", ".html", ".css", ".xml", ".yaml", ".yml", ".sql", ".c", ".cpp",
    # Images (OCR)
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff",
}

IGNORED_SCAN_EXTS = {".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"}


class ScanWorker(QThread):
    """
    Background worker thread that scans directories, registers files,
    and extracts text + OCR text.

    Bulletproof design:
      • Never terminates early due to unsupported, locked, or corrupted files.
      • Catches all exceptions at the individual file boundary.
      • Gracefully skips unsupported formats and records errors for corrupted files.
    """
    progress = Signal(int, int, str)
    completed = Signal(int, int)
    failed = Signal(str)

    def __init__(
        self,
        arg1: Any,
        arg2: Any,
        paths: list[Path] | None = None,
        enable_vlm: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.enable_vlm = enable_vlm
        self._doc_service: Optional[Any] = None
        # Handle flexible argument ordering for backward compatibility:
        # ScanWorker(path, database) OR ScanWorker(database, path/folder_id, ...)
        if isinstance(arg1, Database):
            self.database: Database = arg1
            self.folder_path: Path = Path(arg2)
        else:
            self.folder_path: Path = Path(arg1)
            self.database: Database = arg2

        self.paths = paths
        # Ensure the folder is registered in the database
        try:
            self.folder_id = self.database.add_folder(self.folder_path)
        except Exception:
            self.folder_id = 1

    def supported_paths(self) -> list[Path]:
        """Collects all existing files in the directory tree."""
        if self.paths is not None:
            return [path for path in self.paths if path.is_file()]

        found: list[Path] = []
        try:
            for root, _directories, names in os.walk(self.folder_path, followlinks=False):
                for name in names:
                    try:
                        p = Path(root) / name
                        if p.suffix.lower() in IGNORED_SCAN_EXTS:
                            continue
                        found.append(p)
                    except Exception:
                        continue
        except Exception:
            pass
        return found

    def run(self) -> None:
        failures = 0
        try:
            paths = self.supported_paths()
            total = len(paths)
            if total == 0:
                self.database.mark_folder_scanned(self.folder_id)
                self.completed.emit(0, 0)
                return

            for number, path in enumerate(paths, start=1):
                try:
                    # 1. Skip if file was deleted or unreadable
                    if not path.is_file():
                        continue

                    # 2. Query file stat & check fast-path
                    stat = path.stat()
                    ext = path.suffix.lower()
                    resolved = path.resolve()
                    resolved_str = str(resolved)

                    existing = self.database.get_file_by_path(resolved_str)
                    is_unmodified = (
                        existing is not None
                        and existing.get("indexing_status") == "indexed"
                        and abs(existing.get("modified_at", 0) - stat.st_mtime) < 1e-4
                        and existing.get("size_bytes", 0) == stat.st_size
                        and existing.get("sha256_hash") is not None
                    )

                    if is_unmodified:
                        continue

                    # 3. Checkpoint job start
                    self.database.upsert_index_job(self.folder_id, resolved_str, stage="discovered", status="in_progress")

                    # 4. Upsert discovered file record
                    item = DiscoveredFile(
                        path=resolved,
                        extension=ext,
                        size=stat.st_size,
                        created_at=stat.st_ctime,
                        modified_at=stat.st_mtime,
                    )
                    file_id = self.database.upsert_file(self.folder_id, item)

                    # 5. Compute full streamed cryptographic SHA-256 and optional image pHash
                    sha_hash = compute_sha256(resolved)
                    img_phash = compute_phash(resolved) if ext in IMAGE_EXTENSIONS else None
                    if file_id and sha_hash:
                        self.database.update_file_hash(file_id, sha_hash, img_phash)

                    # 6. Extract Text & OCR if applicable
                    if ext in EXTRACTABLE_EXTENSIONS:
                        self.database.upsert_index_job(self.folder_id, resolved_str, stage="extracting", status="in_progress")
                        native_text, ocr_text = extract_file_content(resolved)
                        self.database.store_file_text(resolved, native_text or "", ocr_text or "")
                    else:
                        self.database.mark_file_indexed(resolved)

                    # 7. Document & Visual Understanding (V3)
                    if self.enable_vlm and sha_hash and file_id and (ext in IMAGE_EXTENSIONS or ext == ".pdf"):
                        try:
                            if self._doc_service is None:
                                from .vlm.document_understanding import DocumentUnderstandingService
                                self._doc_service = DocumentUnderstandingService(self.database)
                            self.database.upsert_index_job(self.folder_id, resolved_str, stage="understanding", status="in_progress")
                            self._doc_service.process_file(resolved, file_id, sha_hash)
                        except Exception as vlm_err:
                            logger.debug("VLM understanding skipped for %s: %s", resolved.name, vlm_err)

                    self.database.upsert_index_job(self.folder_id, resolved_str, stage="complete", status="completed")


                except (OSError, PermissionError) as perm_err:
                    # File locked by Windows or access denied: skip gracefully
                    failures += 1
                    try:
                        self.database.record_error(self.folder_id, path, f"Access denied / locked: {perm_err}")
                    except Exception:
                        pass
                except Exception as file_err:
                    # Corrupted file, unexpected encoding, or library parser exception:
                    # Log error and continue to next file without stopping the scan
                    failures += 1
                    try:
                        self.database.record_error(self.folder_id, path, str(file_err))
                    except Exception:
                        pass
                finally:
                    # Emit progress update for every file
                    try:
                        self.progress.emit(number, total, path.name)
                    except Exception:
                        pass

            # Mark folder scan complete
            try:
                self.database.mark_folder_scanned(self.folder_id)
            except Exception:
                pass
            self.completed.emit(total, failures)

        except Exception as scan_err:
            # Top-level guard in case directory itself became unreachable
            self.failed.emit(str(scan_err))
