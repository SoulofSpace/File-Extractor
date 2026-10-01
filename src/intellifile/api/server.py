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

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Response
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
from PIL import Image

# Initialize core services
app = FastAPI(title="FILE XTRACTOR Core API", version="3.0.0")

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
    global _db, _vector_store, _embed_provider, _agent
    if _db is None:
        db_p = database_path()
        _db = Database(db_p)
        _vector_store = SQLiteFlatVectorStore(db_p)
        _embed_provider = SentenceTransformerProvider()
        _agent = AIAgent(
            _db,
            embedding_provider=_embed_provider,
            vector_store=_vector_store,
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


class OpenFileRequest(BaseModel):
    path: str
    reveal: Optional[bool] = False


class AddFolderRequest(BaseModel):
    path: str


class SavedSearchRequest(BaseModel):
    query: str
    name: Optional[str] = None


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

        return {
            "status": "healthy",
            "database_path": str(db.path),
            "total_files": total_files,
            "folder_count": len(folders),
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

    query_text = (req.query or "").strip()
    if not query_text:
        return {
            "query": "",
            "category": req.category,
            "total_results": 0,
            "elapsed_ms": 0.0,
            "summary": "Empty query",
            "query_plan": {},
            "results": [],
        }

    cat_filter = None if (not req.category or req.category.upper() == "ALL") else req.category.lower()

    # Execute search via AIAgent
    raw_results = agent.search(
        query_text,
        user_category=cat_filter,
        limit=max(req.limit or 60, 60),
        debug=False,
    )

    # Normalize file_id on each result dictionary
    for r in raw_results:
        fid = r.get("file_id") or r.get("id")
        r["file_id"] = fid
        r["id"] = fid

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
def get_file_detail(file_id: int):
    db, _ = get_services()
    record = db.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File record not found")

    res = dict(record)

    # Attach document understanding if present
    try:
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
def get_file_thumbnail(file_id: int, size: int = 360):
    db, _ = get_services()
    record = db.get_file_by_id(file_id)
    if not record:
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
                buf = io.BytesIO()
                # Always save as WebP / JPEG for high compression & speed
                img.convert("RGB").save(buf, format="JPEG", quality=85)
                buf.seek(0)
                return Response(content=buf.getvalue(), media_type="image/jpeg")
        except Exception:
            # Fallback to direct file stream if PIL fails
            return FileResponse(file_path)

    raise HTTPException(status_code=415, detail="Format does not support raster thumbnail")


# ── Folder Management & Indexing Endpoints ────────────────────────────────────

@app.get("/api/folders")
def get_indexed_folders():
    db, _ = get_services()
    try:
        return {"folders": db.folders_with_counts()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ── Mount Built Frontend SPA (if present) ────────────────────────────────────
from fastapi.staticfiles import StaticFiles

_frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


def start_server(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
