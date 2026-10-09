"""
server.py — High-Performance Local API Bridge for FILE XTRACTOR.
Binds strictly to 127.0.0.1. Exposes typed endpoints for:
  • Hybrid AI Search & Compositional Retrieval with 15-field MatchEvidence
  • Format and category filtering (PDF, DOCX, PPTX, JPG, PNG, etc.)
  • Result sorting (Relevance, Date, Size, Name)
  • Image thumbnail streaming and local file preview
  • Folder management, live indexing status, and background scanning
  • Search history, saved searches, and AI model health
"""

from __future__ import annotations

import io
import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Body, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

# Ensure src in sys.path
_src = Path(__file__).resolve().parent.parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from intellifile.paths import database_path
from intellifile.database import Database
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.ai_agent import AIAgent
from intellifile.scanner import ScanWorker
from intellifile.models import SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS, classify_video
from intellifile.person_service import PersonService
from intellifile.sarvam_service import SarvamService
from intellifile.privacy_engine import PrivacyEngine
from intellifile.universal_query_planner import UniversalQueryPlanner
from fastapi import UploadFile, File
from PIL import Image, ImageFilter

# Initialize core services
app = FastAPI(title="FILE XTRACTOR Core API", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global singletons
_db: Optional[Database] = None
_vector_store: Optional[SQLiteFlatVectorStore] = None
_embed_provider: Optional[SentenceTransformerProvider] = None
_agent: Optional[AIAgent] = None
_person_service: Optional[PersonService] = None
_sarvam_service: Optional[SarvamService] = None
_privacy_engine: Optional[PrivacyEngine] = None
_universal_planner: Optional[UniversalQueryPlanner] = None

# Indexing status tracking
_indexing_lock = threading.Lock()
_indexing_status = {
    "is_scanning": False,
    "current_folder": "",
    "current_file": "",
    "current_count": 0,
    "total_count": 0,
    "failures": 0,
    "last_error": "",
}


def get_services():
    global _db, _vector_store, _embed_provider, _agent, _person_service, _sarvam_service, _privacy_engine, _universal_planner
    if _db is None:
        db_p = database_path()
        _db = Database(db_p)
        _vector_store = SQLiteFlatVectorStore(db_p)
        _embed_provider = SentenceTransformerProvider()
        _person_service = PersonService(_db)
        _sarvam_service = SarvamService(_db)
        _privacy_engine = PrivacyEngine(_db)
        _universal_planner = UniversalQueryPlanner(_db)
        _agent = AIAgent(
            _db,
            embedding_provider=_embed_provider,
            vector_store=_vector_store,
            universal_query_planner=_universal_planner,
            person_service=_person_service,
            sarvam_service=_sarvam_service,
            privacy_engine=_privacy_engine,
        )
    return _db, _agent


# ── Pydantic Request & Response Models ────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = "ALL"
    formats: Optional[List[str]] = None      # e.g. ["pdf", "pptx", "png"]
    sort_by: Optional[str] = "relevance"     # "relevance", "date_desc", "date_asc", "size_desc", "size_asc", "name"
    limit: Optional[int] = 60
    save_history: Optional[bool] = True
    privacy_token: Optional[str] = None
    privacy_scope: Optional[str] = "NORMAL"


class OpenFileRequest(BaseModel):
    path: str
    reveal: Optional[bool] = False
    privacy_token: Optional[str] = None
    password: Optional[str] = None


class AddFolderRequest(BaseModel):
    path: str


class SavedSearchRequest(BaseModel):
    query: str
    name: Optional[str] = None


class CreatePersonRequest(BaseModel):
    name: str
    aliases: Optional[List[str]] = None
    reference_image_paths: Optional[List[str]] = None
    notes: Optional[str] = ""


class UpdatePersonRequest(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    aliases: Optional[List[str]] = None


class MergePersonRequest(BaseModel):
    target_person_id: int


class SplitPersonRequest(BaseModel):
    new_person_name: str
    detection_ids: Optional[List[int]] = None
    file_ids: Optional[List[int]] = None


class NameClusterRequest(BaseModel):
    name: str


class PasswordSetupRequest(BaseModel):
    password: str


class PasswordVerifyRequest(BaseModel):
    password: str


class PasswordRecoverRequest(BaseModel):
    recovery_key: str
    new_password: str


class PrivacySettingsUpdateRequest(BaseModel):
    settings: Dict[str, str]


class UpdateFilePrivacyRequest(BaseModel):
    privacy_state: str
    privacy_token: Optional[str] = None


class CreatePersonFromDetectionRequest(BaseModel):
    name: str
    aliases: Optional[List[str]] = None
    notes: Optional[str] = ""


class AddReferencePhotoRequest(BaseModel):
    photo_path: Optional[str] = None
    detection_id: Optional[int] = None


# ── Health & System Status Endpoints ──────────────────────────────────────────

@app.get("/api/status")
def get_system_status():
    db, agent = get_services()
    try:
        total_files = db.total_file_count()
        folders = db.folders_with_counts()
        qwen_healthy = False
        try:
            from intellifile.vlm.model_manager import VLMModelManager
            mgr = VLMModelManager()
            qwen_healthy = mgr.check_health()
        except Exception:
            pass

        # Compute category counts for frontend library cards
        category_counts = {}
        try:
            from intellifile.database import CATEGORY_EXTS
            with db.connection() as conn:
                for cat_k, cat_v in CATEGORY_EXTS.items():
                    if cat_k in ("Media", "Spreadsheet", "Presentation"):
                        continue
                    pl = ",".join("?" for _ in cat_v)
                    c_row = conn.execute(
                        f"SELECT COUNT(*) FROM files WHERE LOWER(extension) IN ({pl}) AND indexing_status = 'indexed'",
                        list(cat_v)
                    ).fetchone()
                    category_counts[cat_k.upper()] = c_row[0] if c_row else 0
        except Exception:
            pass

        return {
            "status": "healthy",
            "database_path": str(db.path),
            "total_files": total_files,
            "folder_count": len(folders),
            "category_counts": category_counts,
            "qwen_available": qwen_healthy,
            "embedding_model_loaded": getattr(agent, "embedding_provider", None) is not None,
            "clip_vision_loaded": True,
            "ai_models": {
                "dense_sbert": "all-MiniLM-L6-v2 (Active)",
                "vision_clip": "clip-ViT-B-32 (Active)",
                "vlm_qwen": "Qwen3.5-4B (Connected)" if qwen_healthy else "Qwen3.5-4B (Standby / Offline)",
            },
            "indexing": _indexing_status,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Search & Retrieval Endpoint ───────────────────────────────────────────────

@app.post("/api/search")
def search_files(req: SearchRequest):
    db, agent = get_services()
    t0 = time.perf_counter()

    pe = agent.privacy_engine
    is_auth = pe.validate_session(req.privacy_token) if pe and req.privacy_token else False
    p_scope = "PRIVATE" if is_auth else (req.privacy_scope or "NORMAL")

    query_text = (req.query or "").strip()
    cat_filter = None if (not req.category or req.category.upper() == "ALL") else req.category.lower()

    # Broad browse mode when query is empty or "*"
    if not query_text or query_text == "*":
        cat_db = cat_filter.capitalize() if cat_filter else None
        recent_hits = db.get_recent_files(category=cat_db, limit=max(req.limit or 60, 60))
        # Enforce privacy scope & sanitization on broad browse
        scoped_hits = []
        for r in recent_hits:
            p_state = (r.get("privacy_state") or "NORMAL").upper()
            if p_state == "HIDDEN" and not is_auth:
                continue
            scoped_hits.append(r)
        if pe:
            raw_results = pe.sanitize_results(scoped_hits, is_authenticated=is_auth)
        else:
            raw_results = scoped_hits
    else:
        # Execute search via AIAgent
        raw_results = agent.search(
            query_text,
            user_category=cat_filter,
            limit=max(req.limit or 60, 60),
            debug=False,
            privacy_scope=p_scope,
            is_authenticated=is_auth,
            privacy_token=req.privacy_token,
        )

    # Normalize all fields on each result dictionary for frontend reliability
    for r in raw_results:
        fid = r.get("file_id") or r.get("id") or 0
        r["file_id"] = fid
        r["id"] = fid
        
        p_str = str(r.get("path") or "")
        p_obj = Path(p_str) if p_str else None
        
        if not r.get("filename"):
            r["filename"] = p_obj.name if p_obj else "Untitled"
            
        ext = r.get("extension")
        if not ext and p_obj:
            ext = p_obj.suffix
        r["extension"] = (ext or "").lower()
        
        # Ensure category / file_type
        cat = r.get("category") or r.get("file_type") or "File"
        r["category"] = cat
        r["file_type"] = r.get("file_type") or cat
        
        # Numeric values
        r["size_bytes"] = int(r.get("size_bytes") or 0)
        r["relevance_score"] = float(r.get("relevance_score") or 0.0)
        r["created_at"] = r.get("created_at") or 0
        r["modified_at"] = r.get("modified_at") or 0
        
        # Strings & evidence
        r["snippet"] = r.get("snippet") or ""
        r["ai_badge"] = r.get("ai_badge") or ""
        r["ai_explanation"] = r.get("ai_explanation") or ""
        if not isinstance(r.get("match_evidence"), dict):
            r["match_evidence"] = {}

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Parse query plan for frontend inspectability
    query_plan_info = {}
    try:
        plan = agent.query_planner.parse_query(query_text)
        cq = getattr(plan, "compositional_query", None)
        query_plan_info = {
            "is_visual": getattr(plan, "is_visual", False),
            "is_academic": getattr(plan, "is_academic", False),
            "raw_query": plan.raw_query,
            "category_filter": plan.category_filter,
            "active_roles": cq.active_roles if cq else [],
            "subjects": cq.subjects if cq else [],
            "attributes": cq.attributes if cq else [],
            "clothing": cq.clothing if cq else [],
            "objects": cq.objects if cq else [],
            "actions": cq.actions if cq else [],
            "scene": cq.scene if cq else [],
            "relationships": cq.relationships if cq else [],
            "original_query": getattr(agent, "last_original_query", query_text),
            "translated_query": getattr(agent, "last_translated_query", query_text),
            "was_translated": getattr(agent, "last_was_translated", False),
            "detected_language": getattr(agent, "last_detected_language", None),
        }
    except Exception:
        pass

    # Granular format filtering (e.g. user selected PDF and PPTX)
    filtered_results = raw_results
    if req.formats:
        norm_formats = {f.lower().lstrip(".") for f in req.formats if f}
        if norm_formats:
            filtered_results = [
                r for r in filtered_results
                if (r.get("extension", "").lower().lstrip(".") in norm_formats)
            ]

    # Sorting
    sort_key = (req.sort_by or "relevance").lower()
    if sort_key == "date_desc":
        filtered_results = sorted(filtered_results, key=lambda r: r.get("modified_at", ""), reverse=True)
    elif sort_key == "date_asc":
        filtered_results = sorted(filtered_results, key=lambda r: r.get("modified_at", ""))
    elif sort_key == "size_desc":
        filtered_results = sorted(filtered_results, key=lambda r: r.get("size_bytes", 0), reverse=True)
    elif sort_key == "size_asc":
        filtered_results = sorted(filtered_results, key=lambda r: r.get("size_bytes", 0))
    elif sort_key == "name":
        filtered_results = sorted(filtered_results, key=lambda r: r.get("filename", "").lower())
    # default is relevance, already sorted by agent

    summary = f"Hybrid AI Search ({len(filtered_results)} matches in {elapsed_ms:.1f}ms)"

    # Save to search history if requested
    if req.save_history:
        try:
            db.add_search_history(query_text, len(filtered_results), int(elapsed_ms), summary)
        except Exception:
            pass

    return {
        "query": query_text,
        "original_query": getattr(agent, "last_original_query", query_text),
        "translated_query": getattr(agent, "last_translated_query", query_text),
        "was_translated": getattr(agent, "last_was_translated", False),
        "detected_language": getattr(agent, "last_detected_language", None),
        "category": req.category or "ALL",
        "total_results": len(filtered_results),
        "unfiltered_count": len(raw_results),
        "elapsed_ms": round(elapsed_ms, 2),
        "summary": summary,
        "query_plan": query_plan_info,
        "results": filtered_results[:req.limit],
    }


# ── File Details & Preview Endpoint ───────────────────────────────────────────

@app.get("/api/file/{file_id}")
def get_file_detail(file_id: int, privacy_token: Optional[str] = None):
    db, agent = get_services()
    pe = agent.privacy_engine
    is_auth = pe.validate_session(privacy_token) if pe and privacy_token else False

    record = db.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File record not found")

    p_state = (record.get("privacy_state") or "NORMAL").upper()
    if p_state == "HIDDEN" and not is_auth:
        raise HTTPException(status_code=404, detail="File record not found")

    res = dict(record)
    if p_state == "PROTECTED" and not is_auth:
        res["is_locked"] = True
        res["is_protected"] = True
        res["snippet"] = "[Protected content - Enter password to view]"
        res["ocr_text"] = ""
        res["extracted_text"] = ""
        if pe and db.get_privacy_setting("hide_protected_filename", "true") == "true":
            ext = res.get("extension", "")
            res["filename"] = f"Protected Document{ext}" if res.get("file_type") == "document" else f"Protected File{ext}"
    else:
        res["is_locked"] = False
        res["is_protected"] = (p_state in ("PROTECTED", "HIDDEN"))

    # Attach document understanding if present and permitted
    try:
        if not (p_state == "PROTECTED" and not is_auth):
            doc_und = db.get_document_understanding(file_id)
            if doc_und:
                res["document_understanding"] = doc_und
    except Exception:
        pass

    # Attach video classification if video
    ext = res.get("extension", "").lower()
    if ext in VIDEO_EXTENSIONS:
        subtype, v_label = classify_video(res.get("path", ""), res.get("size_bytes", 0))
        res["video_classification"] = {"subtype": subtype, "label": v_label}

    return res


# ── Thumbnail Streaming Endpoint ──────────────────────────────────────────────

@app.get("/api/thumbnail/{file_id}")
def get_file_thumbnail(file_id: int, size: int = 360, privacy_token: Optional[str] = None):
    db, agent = get_services()
    pe = agent.privacy_engine
    is_auth = pe.validate_session(privacy_token) if pe and privacy_token else False

    record = db.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    p_state = (record.get("privacy_state") or "NORMAL").upper()
    if p_state == "HIDDEN" and not is_auth:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(record.get("path", ""))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing from disk")

    ext = file_path.suffix.lower()
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}

    if ext in image_exts:
        try:
            # Generate thumbnail in memory for fast local rendering
            with Image.open(file_path) as img:
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                # If protected and unauthenticated, apply blur or hide
                if p_state == "PROTECTED" and not is_auth:
                    preview_mode = db.get_privacy_setting("protected_image_preview", "blur")
                    if preview_mode == "hide":
                        raise HTTPException(status_code=403, detail="Protected image preview is hidden")
                    else:  # blur
                        img = img.filter(ImageFilter.GaussianBlur(radius=20))

                buf = io.BytesIO()
                # Always save as WebP / JPEG for high compression & speed
                img.convert("RGB").save(buf, format="JPEG", quality=85)
                buf.seek(0)
                return Response(content=buf.getvalue(), media_type="image/jpeg")
        except HTTPException:
            raise
        except Exception:
            # Fallback to direct file stream if PIL fails
            return FileResponse(file_path)

    raise HTTPException(status_code=415, detail="Format does not support raster thumbnail")


@app.get("/api/recent-files")
def get_recent_files(limit: int = 12, category: Optional[str] = None):
    db, _ = get_services()
    try:
        cat_name = category.capitalize() if (category and category.upper() != "ALL") else None
        files = db.get_recent_files(category=cat_name, limit=limit * 2)
        normalized = []
        for r in files:
            p_str = str(r.get("path") or "")
            if not p_str:
                continue
            p_obj = Path(p_str)
            if not p_obj.exists():
                continue
            fid = r.get("id") or r.get("file_id") or 0
            r["file_id"] = fid
            r["id"] = fid
            r["filename"] = r.get("filename") or p_obj.name
            ext = r.get("extension") or p_obj.suffix
            r["extension"] = (ext or "").lower()
            cat = r.get("category") or r.get("file_type") or "File"
            r["category"] = cat
            r["file_type"] = r.get("file_type") or cat
            r["size_bytes"] = int(r.get("size_bytes") or 0)
            r["modified_at"] = r.get("modified_at") or 0
            r["relevance_score"] = 0.0
            r["match_evidence"] = {}
            normalized.append(r)
            if len(normalized) >= limit:
                break
        return {"files": normalized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Folder Management & Indexing Endpoints ────────────────────────────────────

@app.get("/api/folders")
def get_indexed_folders():
    db, _ = get_services()
    try:
        return {"folders": db.folders_with_counts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage-analytics")
def get_storage_analytics(privacy_token: Optional[str] = None):
    db, agent = get_services()
    pe = agent.privacy_engine
    is_auth = pe.validate_session(privacy_token) if pe and privacy_token else False

    with db.connection() as conn:
        total_row = conn.execute("SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM files").fetchone()
        total_files = total_row[0] or 0
        total_bytes = total_row[1] or 0

        prot_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM files WHERE privacy_state IN ('PROTECTED', 'HIDDEN')"
        ).fetchone()
        protected_files = prot_row[0] or 0
        protected_bytes = prot_row[1] or 0

        dup_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size_bytes), 0) FROM files WHERE duplicate_of_id IS NOT NULL"
        ).fetchone()
        duplicate_files = dup_row[0] or 0
        duplicate_bytes = dup_row[1] or 0

        cat_rows = conn.execute("""
            SELECT file_type, extension, COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as bytes
            FROM files
            GROUP BY file_type, extension
            ORDER BY bytes DESC
        """).fetchall()

        category_map = {
            "Videos": {"count": 0, "bytes": 0, "color": "#f43f5e"},
            "Archives": {"count": 0, "bytes": 0, "color": "#f59e0b"},
            "Documents": {"count": 0, "bytes": 0, "color": "#3b82f6"},
            "Images": {"count": 0, "bytes": 0, "color": "#10b981"},
            "Audio": {"count": 0, "bytes": 0, "color": "#8b5cf6"},
            "Code": {"count": 0, "bytes": 0, "color": "#06b6d4"},
            "Other": {"count": 0, "bytes": 0, "color": "#71717a"},
        }
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".svg"}
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv"}
        audio_exts = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
        doc_exts = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".txt", ".csv"}
        archive_exts = {".zip", ".rar", ".7z", ".tar", ".gz"}
        code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".sql", ".cpp", ".c", ".java"}

        for r in cat_rows:
            ext = (r["extension"] or "").lower()
            cnt = r["count"]
            b = r["bytes"]
            if ext in video_exts:
                category_map["Videos"]["count"] += cnt
                category_map["Videos"]["bytes"] += b
            elif ext in archive_exts:
                category_map["Archives"]["count"] += cnt
                category_map["Archives"]["bytes"] += b
            elif ext in doc_exts:
                category_map["Documents"]["count"] += cnt
                category_map["Documents"]["bytes"] += b
            elif ext in image_exts:
                category_map["Images"]["count"] += cnt
                category_map["Images"]["bytes"] += b
            elif ext in audio_exts:
                category_map["Audio"]["count"] += cnt
                category_map["Audio"]["bytes"] += b
            elif ext in code_exts:
                category_map["Code"]["count"] += cnt
                category_map["Code"]["bytes"] += b
            else:
                category_map["Other"]["count"] += cnt
                category_map["Other"]["bytes"] += b

        folder_rows = conn.execute("""
            SELECT fo.path, COUNT(fi.id) as count, COALESCE(SUM(fi.size_bytes), 0) as bytes
            FROM indexed_folders fo
            LEFT JOIN files fi ON fi.folder_id = fo.id
            GROUP BY fo.id
            ORDER BY bytes DESC
        """).fetchall()
        folders = [
            {"path": r["path"], "name": Path(r["path"]).name or r["path"], "count": r["count"], "bytes": r["bytes"]}
            for r in folder_rows
        ]

        largest_rows = conn.execute("""
            SELECT id, filename, path, size_bytes, extension, file_type, privacy_state
            FROM files
            ORDER BY size_bytes DESC
            LIMIT 40
        """).fetchall()
        largest_files = []
        for r in largest_rows:
            p_obj = Path(r["path"])
            if p_obj.exists():
                is_file_prot = r["privacy_state"] in ("PROTECTED", "HIDDEN")
                largest_files.append({
                    "id": r["id"],
                    "filename": r["filename"] if (not is_file_prot or is_auth) else f"Protected File{r['extension']}",
                    "path": r["path"],
                    "size_bytes": r["size_bytes"],
                    "extension": r["extension"],
                    "file_type": r["file_type"],
                    "is_protected": is_file_prot,
                })
                if len(largest_files) >= 15:
                    break

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "protected_files": protected_files,
        "protected_bytes": protected_bytes,
        "duplicate_files": duplicate_files,
        "duplicate_bytes": duplicate_bytes,
        "categories": [
            {"name": k, "count": v["count"], "bytes": v["bytes"], "color": v["color"]}
            for k, v in category_map.items() if v["count"] > 0
        ],
        "folders": folders,
        "largest_files": largest_files,
    }


@app.post("/api/folders")
def add_indexed_folder(req: AddFolderRequest, background_tasks: BackgroundTasks):
    db, _ = get_services()
    p = Path(req.path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    try:
        folder_id = db.add_folder(str(p))
        # Trigger background scan
        background_tasks.add_task(run_folder_scan, str(p))
        return {"status": "added", "folder_id": folder_id, "path": str(p)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/folders")
def remove_indexed_folder(req: AddFolderRequest):
    db, _ = get_services()
    try:
        db.remove_folder(req.path)
        return {"status": "removed", "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/indexing/scan")
def trigger_rescan(req: AddFolderRequest, background_tasks: BackgroundTasks):
    p = Path(req.path).resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")
    background_tasks.add_task(run_folder_scan, str(p))
    return {"status": "scanning_started", "path": str(p)}


@app.get("/api/indexing/status")
def get_indexing_progress():
    with _indexing_lock:
        return dict(_indexing_status)


def run_folder_scan(folder_path_str: str):
    global _indexing_status
    db, _ = get_services()

    with _indexing_lock:
        if _indexing_status["is_scanning"]:
            return
        _indexing_status["is_scanning"] = True
        _indexing_status["current_folder"] = folder_path_str
        _indexing_status["current_count"] = 0
        _indexing_status["total_count"] = 0
        _indexing_status["failures"] = 0

    try:
        # Use existing ScanWorker logic directly
        worker = ScanWorker(db, folder_path_str, enable_vlm=True)
        def on_prog(cur, tot, fn):
            with _indexing_lock:
                _indexing_status["current_count"] = cur
                _indexing_status["total_count"] = tot
                _indexing_status["current_file"] = fn

        def on_comp(tot, fail):
            with _indexing_lock:
                _indexing_status["is_scanning"] = False
                _indexing_status["failures"] = fail

        worker.progress.connect(on_prog)
        worker.completed.connect(on_comp)
        worker.run()
    except Exception as exc:
        with _indexing_lock:
            _indexing_status["is_scanning"] = False
            _indexing_status["last_error"] = str(exc)


# ── Search History & Saved Searches Endpoints ─────────────────────────────────

@app.get("/api/history")
def get_search_history(limit: int = 30):
    db, _ = get_services()
    try:
        return {"history": db.get_search_history(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/history/clear")
def clear_search_history():
    db, _ = get_services()
    try:
        db.clear_search_history()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/saved-searches")
def get_saved_searches():
    db, _ = get_services()
    try:
        return {"saved_searches": db.get_saved_searches()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/saved-searches")
def add_saved_search(req: SavedSearchRequest):
    db, _ = get_services()
    try:
        sid = db.add_saved_search(req.query, req.name or req.query)
        return {"status": "saved", "id": sid, "query": req.query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/saved-searches/{search_id}")
def delete_saved_search(search_id: int):
    db, _ = get_services()
    try:
        db.delete_saved_search(search_id)
        return {"status": "deleted", "id": search_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── OS Native File Actions ────────────────────────────────────────────────────

@app.post("/api/open-file")
def open_local_file(req: OpenFileRequest):
    db, agent = get_services()
    pe = agent.privacy_engine

    # Check file privacy state
    f_rec = db.get_file_by_path(req.path)
    if f_rec:
        p_state = (f_rec.get("privacy_state") or "NORMAL").upper()
        if p_state in ("PROTECTED", "HIDDEN"):
            is_auth = False
            if req.privacy_token and pe and pe.validate_session(req.privacy_token):
                is_auth = True
            elif req.password and pe:
                ok, _, _ = pe.verify_password(req.password)
                if ok:
                    is_auth = True
            if not is_auth:
                raise HTTPException(
                    status_code=403,
                    detail=f"This file is {p_state.title()}. Privacy password is required to open it.",
                )

    p = Path(req.path).resolve()
    if not p.exists():
        raise HTTPException(status_code=404, detail="File does not exist on disk")

    try:
        if req.reveal:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{str(p)}"])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(p)])
            else:
                subprocess.run(["xdg-open", str(p.parent)])
            return {"status": "revealed", "path": str(p)}
        else:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)])
            else:
                subprocess.run(["xdg-open", str(p)])
            return {"status": "opened", "path": str(p)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open file: {e}")


# ── Persons Section Endpoints (Requirements 5, 6, 9, 10, 11) ─────────────────

@app.get("/api/persons")
def list_persons(
    include_clusters: bool = True,
    privacy_token: Optional[str] = None,
):
    db, agent = get_services()
    pe = agent.privacy_engine
    is_auth = pe.validate_session(privacy_token) if pe and privacy_token else False
    scope = "PRIVATE" if is_auth else "NORMAL"
    persons = db.list_persons(include_clusters=include_clusters, privacy_scope=scope)
    return {"persons": persons, "total": len(persons)}


@app.post("/api/persons")
def create_person(req: CreatePersonRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    pid = ps.create_person_with_photos(
        name=req.name,
        aliases=req.aliases,
        reference_image_paths=req.reference_image_paths,
        notes=req.notes or "",
    )
    person = agent.database.get_person(pid)
    return {"status": "created", "person": person}


@app.get("/api/persons/{person_id}")
def get_person(
    person_id: int,
    privacy_token: Optional[str] = None,
):
    _, agent = get_services()
    ps = agent.person_service
    pe = agent.privacy_engine
    is_auth = pe.validate_session(privacy_token) if pe and privacy_token else False
    scope = "PRIVATE" if is_auth else "NORMAL"
    details = ps.get_person_details(person_id, privacy_scope=scope) if ps else None
    if not details:
        raise HTTPException(status_code=404, detail="Person not found")
    return details


@app.put("/api/persons/{person_id}")
def update_person(person_id: int, req: UpdatePersonRequest):
    db, _ = get_services()
    if req.name:
        db.update_person(person_id, name=req.name)
    if req.notes is not None:
        db.update_person(person_id, notes=req.notes)
    if req.aliases is not None:
        with db.connection() as conn:
            conn.execute("DELETE FROM person_aliases WHERE person_id = ?", (person_id,))
        for a in req.aliases:
            db.add_person_alias(person_id, a)
    updated = db.get_person(person_id)
    return {"status": "updated", "person": updated}


@app.delete("/api/persons/{person_id}")
def delete_person(person_id: int):
    _, agent = get_services()
    ps = agent.person_service
    if ps:
        ps.delete_person(person_id)
    return {"status": "deleted", "id": person_id}


@app.post("/api/persons/{person_id}/merge")
def merge_persons(person_id: int, req: MergePersonRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    ps.merge_persons(person_id, req.target_person_id)
    merged = agent.database.get_person(req.target_person_id)
    return {"status": "merged", "person": merged}


@app.post("/api/persons/{person_id}/split")
def split_person(person_id: int, req: SplitPersonRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    new_pid = ps.split_person(
        person_id,
        new_person_name=req.new_person_name,
        detection_ids=req.detection_ids,
        file_ids=req.file_ids,
    )
    new_person = agent.database.get_person(new_pid)
    return {"status": "split", "person": new_person}


@app.post("/api/persons/cluster/{cluster_id}/name")
def name_cluster(cluster_id: int, req: NameClusterRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    pid = ps.name_cluster(cluster_id, req.name)
    person = agent.database.get_person(pid)
    return {"status": "named", "person": person}


@app.post("/api/persons/scan-faces")
def scan_library_faces(force: bool = False):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    res = ps.scan_and_cluster_all_library_faces(force=force)
    return res


@app.post("/api/persons/reprocess-faces")
def reprocess_faces(backup: bool = True):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    return ps.reprocess_all_faces(backup=backup, force=True)


@app.get("/api/face-detections/{detection_id}/crop")
def get_face_detection_crop(detection_id: int):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    crop_bytes = ps.get_detection_face_crop(detection_id)
    if not crop_bytes:
        raise HTTPException(status_code=404, detail="Face crop not found or image missing")
    return Response(content=crop_bytes, media_type="image/jpeg")


@app.get("/api/face-detections/unassigned")
def get_unassigned_faces(limit: int = 100):
    db, _ = get_services()
    return {"unassigned_faces": db.get_unassigned_face_detections(limit=limit)}


@app.get("/api/face-detections/review")
def get_face_review_queue(limit: int = 150):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    return {"review_queue": ps.get_face_review_queue(limit=limit)}


@app.get("/api/files/{file_id}/faces")
def get_file_face_detections(file_id: int):
    db, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")

    record = db.get_file_by_id(file_id)
    img_w, img_h = 0, 0
    file_path = record.get("path") if record else None
    if file_path:
        try:
            p = Path(file_path)
            if p.is_file():
                with Image.open(p) as img:
                    img_w, img_h = img.size
        except Exception:
            pass

    faces = ps.get_file_faces(file_id)
    for f in faces:
        if img_w > 0 and img_h > 0:
            f["norm_x"] = round(f["box_x"] / img_w, 4)
            f["norm_y"] = round(f["box_y"] / img_h, 4)
            f["norm_w"] = round(f["box_w"] / img_w, 4)
            f["norm_h"] = round(f["box_h"] / img_h, 4)
        else:
            f["norm_x"] = None
            f["norm_y"] = None
            f["norm_w"] = None
            f["norm_h"] = None

    return {
        "file_id": file_id,
        "image_width": img_w,
        "image_height": img_h,
        "path": file_path,
        "faces": faces,
    }


@app.post("/api/face-detections/confirm-all")
def confirm_all_face_detections(person_id: Optional[int] = None):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    count = ps.propagate_and_link_known_persons(target_person_id=person_id)
    return {"status": "ok", "confirmed_count": count}


@app.post("/api/face-detections/{detection_id}/create-person")
def create_person_from_detection(detection_id: int, req: CreatePersonFromDetectionRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    try:
        res = ps.create_person_from_detection(
            detection_id=detection_id,
            name=req.name,
            aliases=req.aliases,
            notes=req.notes or "",
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/face-detections/{detection_id}/assign")
def assign_face_detection(detection_id: int, person_id: int):
    db, _ = get_services()
    det = db.get_face_detection_by_id(detection_id)
    if not det:
        raise HTTPException(status_code=404, detail="Face detection not found")
    db.assign_face_detection_to_person(detection_id, person_id, match_confidence=1.0)
    return {"status": "assigned", "detection_id": detection_id, "person_id": person_id}


class ConfirmFaceRequest(BaseModel):
    person_id: Optional[int] = None


@app.post("/api/face-detections/{detection_id}/confirm")
def confirm_face_detection(
    detection_id: int,
    person_id: Optional[int] = Query(None),
    req: Optional[ConfirmFaceRequest] = Body(None),
):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    try:
        target_pid = person_id
        if target_pid is None and req is not None:
            target_pid = req.person_id
        return ps.confirm_face_detection(detection_id, person_id=target_pid)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/face-detections/{detection_id}/reject")
def reject_face_detection(detection_id: int):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    try:
        return ps.reject_face_detection(detection_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/face-detections/{detection_id}/keep-unknown")
def keep_unknown_face_detection(detection_id: int):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    try:
        return ps.keep_unknown_face_detection(detection_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/persons/{person_id}/reference-photos")
def add_reference_photo_to_person(person_id: int, req: AddReferencePhotoRequest):
    _, agent = get_services()
    ps = agent.person_service
    if not ps:
        raise HTTPException(status_code=500, detail="PersonService not initialized")
    try:
        return ps.add_reference_photo_to_person(
            person_id=person_id,
            photo_path=req.photo_path,
            detection_id=req.detection_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Voice Search (Requirements 21, 22) ───────────────────────────────────────

@app.post("/api/voice-search")
async def voice_search(
    file: Optional[UploadFile] = None,
    privacy_token: Optional[str] = None,
):
    _, agent = get_services()
    ss = agent.sarvam_service
    if not ss or not ss.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Voice search requires SARVAM_API_KEY to be set in environment or settings.",
        )

    if not file:
        raise HTTPException(status_code=400, detail="No audio file uploaded")
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file was empty")

    mime_type = file.content_type or "audio/wav"
    transcript = ss.transcribe_speech(audio_bytes, mime_type=mime_type, mode="translate")
    if not transcript or not transcript.strip():
        raise HTTPException(status_code=422, detail="Speech could not be transcribed.")

    return {"transcript": transcript.strip(), "language": "en"}


# ── Privacy Center Endpoints (Requirements 26-37) ─────────────────────────────

@app.get("/api/privacy/status")
def privacy_status(privacy_token: Optional[str] = None):
    _, agent = get_services()
    pe = agent.privacy_engine
    is_conf = pe.is_password_configured() if pe else False
    is_unlocked = pe.validate_session(privacy_token) if pe and privacy_token else False
    return {
        "is_configured": is_conf,
        "is_unlocked": is_unlocked,
    }


@app.post("/api/privacy/setup")
def privacy_setup(req: PasswordSetupRequest):
    _, agent = get_services()
    pe = agent.privacy_engine
    if not pe:
        raise HTTPException(status_code=500, detail="PrivacyEngine not initialized")
    try:
        rec_key = pe.setup_password(req.password)
        ok, token, _ = pe.verify_password(req.password)
        return {
            "status": "configured",
            "recovery_key": rec_key,
            "token": token,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/privacy/verify")
def privacy_verify(req: PasswordVerifyRequest):
    _, agent = get_services()
    pe = agent.privacy_engine
    if not pe:
        raise HTTPException(status_code=500, detail="PrivacyEngine not initialized")
    ok, token, msg = pe.verify_password(req.password)
    if not ok:
        raise HTTPException(status_code=401, detail=msg)
    return {"status": "authenticated", "token": token, "message": msg}


@app.post("/api/privacy/recover")
def privacy_recover(req: PasswordRecoverRequest):
    _, agent = get_services()
    pe = agent.privacy_engine
    if not pe:
        raise HTTPException(status_code=500, detail="PrivacyEngine not initialized")
    ok, msg = pe.verify_recovery_key(req.recovery_key, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    _, token, _ = pe.verify_password(req.new_password)
    return {"status": "recovered", "token": token, "message": msg}


@app.post("/api/privacy/lock")
def privacy_lock(privacy_token: Optional[str] = None):
    _, agent = get_services()
    pe = agent.privacy_engine
    if pe and privacy_token:
        pe.revoke_session(privacy_token)
    return {"status": "locked"}


@app.get("/api/privacy/settings")
def get_privacy_settings():
    db, _ = get_services()
    return db.get_all_privacy_settings()


@app.put("/api/privacy/settings")
def update_privacy_settings(req: PrivacySettingsUpdateRequest):
    db, agent = get_services()
    for k, v in req.settings.items():
        db.set_privacy_setting(k, str(v))
    applied_counts = {}
    if agent.privacy_engine:
        try:
            applied_counts = agent.privacy_engine.apply_policies_to_all_files()
        except Exception:
            pass
    return {"status": "saved", "settings": db.get_all_privacy_settings(), "applied_counts": applied_counts}


@app.post("/api/privacy/apply-policies")
def apply_privacy_policies():
    _, agent = get_services()
    if not agent.privacy_engine:
        raise HTTPException(status_code=500, detail="PrivacyEngine not initialized")
    counts = agent.privacy_engine.apply_policies_to_all_files()
    return {"status": "applied", "classified_counts": counts}


@app.post("/api/files/{file_id}/privacy")
def update_file_privacy(file_id: int, req: UpdateFilePrivacyRequest):
    db, agent = get_services()
    pe = agent.privacy_engine
    if pe and pe.is_password_configured():
        if not pe.validate_session(req.privacy_token):
            raise HTTPException(status_code=403, detail="Password authentication required to change file privacy.")
    db.update_file_privacy(
        file_id=file_id,
        privacy_state=req.privacy_state.upper(),
        manual=True,
    )
    return {"status": "updated", "file_id": file_id, "privacy_state": req.privacy_state.upper()}


# ── Mount Built Frontend SPA (if present) ────────────────────────────────────
from fastapi.staticfiles import StaticFiles

_frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"

@app.get("/")
def serve_index():
    index_file = _frontend_dist / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return {"message": "i-file Core API running"}

if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


def start_server(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
