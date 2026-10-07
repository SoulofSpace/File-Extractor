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
        self._privacy_engine: Optional[Any] = None
        self._person_service: Optional[Any] = None
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

                    # 8. V4 Metadata, Privacy, and Entity/Face Processing
                    if file_id:
                        try:
                            # 8a. Date extraction (EXIF capture date first, then file mtime)
                            capture_date = None
                            date_source = "filesystem"
                            if ext in IMAGE_EXTENSIONS:
                                try:
                                    from PIL import Image, ExifTags
                                    with Image.open(resolved) as img:
                                        exif = img.getexif()
                                        if exif:
                                            for tag_id, val in exif.items():
                                                tag_name = ExifTags.TAGS.get(tag_id, "")
                                                if tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                                                    raw_dt = str(val).strip()
                                                    if len(raw_dt) >= 10:
                                                        parts = raw_dt[:10].replace(":", "-").split("-")
                                                        if len(parts) == 3 and len(parts[0]) == 4:
                                                            capture_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                                                            date_source = "exif"
                                                            break
                                except Exception:
                                    pass

                            if not capture_date:
                                import datetime
                                mtime_dt = datetime.datetime.fromtimestamp(stat.st_mtime)
                                capture_date = mtime_dt.strftime("%Y-%m-%d")
                                date_source = "filesystem"

                            # 8b. Category & Document Type Classification & Sensitivity
                            if self._privacy_engine is None:
                                from .privacy_engine import PrivacyEngine
                                self._privacy_engine = PrivacyEngine(self.database)

                            extracted_n = native_text if ext in EXTRACTABLE_EXTENSIONS and 'native_text' in locals() else ""
                            extracted_o = ocr_text if ext in EXTRACTABLE_EXTENSIONS and 'ocr_text' in locals() else ""
                            comb_text = f"{resolved.name} {extracted_n or ''} {extracted_o or ''}".lower()
                            sensitivity_class, suggested_state, _ = self._privacy_engine.scan_sensitivity(
                                comb_text, filename=resolved.name
                            )

                            doc_type = None
                            cat_v4 = None
                            if sensitivity_class == "ID_DOCUMENT":
                                cat_v4 = "IDs & Documents"
                                if "aadhaar" in comb_text or "uidai" in comb_text:
                                    doc_type = "Aadhaar Card"
                                elif "pan" in comb_text or "income tax" in comb_text:
                                    doc_type = "PAN Card"
                                elif "passport" in comb_text:
                                    doc_type = "Passport"
                                elif "voter" in comb_text or "election" in comb_text:
                                    doc_type = "Voter ID"
                                elif "driving" in comb_text or "licence" in comb_text or "license" in comb_text:
                                    doc_type = "Driving License"
                                else:
                                    doc_type = "Identity Document"
                            elif sensitivity_class == "BANKING_FINANCE":
                                cat_v4 = "Banking & Finance"
                                if "statement" in comb_text:
                                    doc_type = "Bank Statement"
                                elif "salary" in comb_text or "payslip" in comb_text:
                                    doc_type = "Salary Slip"
                                elif "tax" in comb_text or "itr" in comb_text:
                                    doc_type = "Tax Return"
                                else:
                                    doc_type = "Financial Record"
                            elif ext in IMAGE_EXTENSIONS:
                                cat_v4 = "Personal Photos"
                                doc_type = "Photo"
                            elif any(k in comb_text for k in ["assignment", "syllabus", "lecture", "homework", "exam", "question paper", "da", "dsa", "dbms", "os", "cn"]):
                                cat_v4 = "Education"
                                doc_type = "Academic Document"
                            elif any(k in comb_text for k in ["resume", "cv", "project plan", "meeting notes", "contract", "offer letter", "agreement"]):
                                cat_v4 = "Work"
                                doc_type = "Work Document"
                            elif any(k in comb_text for k in ["ticket", "boarding pass", "flight", "hotel", "itinerary", "booking", "visa"]):
                                cat_v4 = "Travel"
                                doc_type = "Travel Document"
                            elif ext in (".pdf", ".docx", ".doc", ".txt", ".md"):
                                cat_v4 = "IDs & Documents"
                                doc_type = "Document"
                            else:
                                cat_v4 = "Other"
                                doc_type = ext.replace(".", "").upper()

                            # Update V4 metadata and privacy
                            current_priv = self.database.get_file_privacy(file_id)
                            privacy_to_set = current_priv["privacy_state"] if current_priv.get("manual_override") else suggested_state

                            self.database.update_file_v4_metadata(
                                file_id=file_id,
                                category_v4=cat_v4,
                                document_type=doc_type,
                                capture_date=capture_date,
                                date_source=date_source,
                                sensitivity_class=sensitivity_class,
                                privacy_state=privacy_to_set,
                            )
                            if not current_priv.get("manual_override"):
                                self.database.update_file_privacy(
                                    file_id=file_id,
                                    privacy_state=privacy_to_set,
                                    sensitivity_class=sensitivity_class,
                                    manual=False,
                                )

                            # 8c. Person & Face Indexing
                            if self._person_service is None:
                                from .person_service import PersonService
                                self._person_service = PersonService(self.database)
                            self._person_service.process_file_faces_and_entities(
                                file_id=file_id,
                                file_path=resolved,
                                ocr_text=extracted_o or "",
                                document_text=extracted_n or "",
                            )
                        except Exception as v4_err:
                            logger.debug("V4 enrichment skipped for %s: %s", resolved.name, v4_err)

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
