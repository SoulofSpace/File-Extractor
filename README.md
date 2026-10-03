# FILE XTRACTOR (IntelliFile V3)
### Universal Multimodal File Intelligence & Hybrid Semantic Retrieval Engine

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Status: Release Candidate](https://img.shields.io/badge/Status-Release%20Candidate%20(RC1)-green.svg)]()
[![Privacy: 100% Offline](https://img.shields.io/badge/Privacy-100%25%20Offline%20Local-success.svg)]()
[![Hardware: RTX 4060 / CPU](https://img.shields.io/badge/Hardware-RTX%204060%20%2F%20CPU-orange.svg)]()

FILE XTRACTOR is an offline, local-first multimodal file intelligence platform and desktop search engine. It seamlessly bridges natural language queries with local documents, photos, diagrams, scanned forms, posters, and receipts through deep neural fusion—combining SQLite FTS5 lexical search, Tesseract layout OCR, dense SBERT text embeddings, OpenAI CLIP visual embeddings, and local Qwen3.5-4B Vision-Language Models (VLM).

---

## Key Features & Architecture

### 1. Hybrid 5-Branch Retrieval Engine
- **Branch 1a (Deep Multimodal CLIP Vision):** Vector search over image contents via OpenAI `clip-ViT-B-32` 512-dimensional embeddings.
- **Branch 1b (Universal VLM Document Understanding):** High-level semantic tagging, object detection, and title extraction via local `Qwen3.5-4B` through `llama.cpp`.
- **Branch 2 (Full-Text Lexical Search):** Fast SQLite FTS5 BM25 search across document text, transcripts, and OCR.
- **Branch 3 (Exact Terms & Acronym Expansion):** Automatic academic curriculum and technical abbreviation expansion (e.g. `DBMS`, `OS`, `DSA`, `DA 3`).
- **Branch 4 (Filename & Entity Matching):** Fuzzy and exact filename token matching.
- **Branch 5 (Dense Text Vector Retrieval):** 384-dimensional dense semantic vector similarity using `all-MiniLM-L6-v2` with pluggable `VectorStore` (`SQLiteFlatVectorStore`).

### 2. Dual-Pass Layout-Aware OCR
- Native Tesseract OCR pipeline with dynamic rotation correction, noise reduction, and dual-pass display text extraction for complex receipts, ID cards, certificates, and presentation slides.

### 3. Open-Vocabulary Query Planner
- Free-form natural language query decomposition without hardcoded trigger lists.
- Automatic filtering for file types (`ext:pdf`, `type:png`) and file sizes (`size:>10MB`).
- Conversational filler stripping (`"can you please find my..."`).

### 4. Zero Data Leakage & 100% Offline Privacy
- All models (SBERT, CLIP, Qwen3.5-4B, Tesseract) run completely on-device.
- Zero telemetry, zero cloud calls, zero external socket connections.
- Cryptographic SHA-256 content deduplication and perceptual hashing (pHash).

### 5. Modern Commercial AI Desktop UI (React 19 + TypeScript + Electron)
- Next-generation desktop interface built with React 19, TypeScript, Tailwind CSS, Framer Motion, and Electron.
- Clean desktop file dashboard featuring live library statistics across Documents, Images, Videos, Audio, Code, and Archives.
- Deep visual file inspection with thumbnail generation, rich metadata preview drawers, OCR viewer, and AI match evidence inspection.
- Interactive multi-select format popovers (`.pdf`, `.docx`, `.pptx`, `.xlsx`, etc.) and active chip filters.
- Real-time indexing monitor and folder manager with native Windows folder selection.
- Isolated legacy Qt/PySide6 desktop UI available as a seamless fallback.

---

## System Requirements

- **OS:** Windows 10/11, Linux, or macOS
- **Node.js:** v18+ (for Electron desktop shell)
- **Python:** 3.11, 3.12, or 3.13
- **RAM:** 16 GB DDR4/DDR5 recommended
- **GPU (Optional):** NVIDIA RTX 3060 / 4060 (8 GB VRAM) for CUDA acceleration; runs on CPU via llama.cpp
- **Tesseract OCR:** Installed locally and added to PATH (or default location `C:\Program Files\Tesseract-OCR`)

---

## Installation & Quickstart

### 1. Clone & Set Up Virtual Environment

```powershell
git clone https://github.com/SoulofSpace/File-Extractor.git
cd File-Extractor

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Launch the Application

```powershell
# Launch the primary modern AI desktop application (React + Electron):
python run.py
# Or run with web browser mode:
python run.py --web
```
*Or simply double-click `run.bat` or `run_intellifile.bat`.*

### 3. Launching Legacy Interface (Fallback)

The original PySide6 Qt GUI is preserved as a fallback:
```powershell
# Launch legacy interface via CLI flag:
python run.py --legacy
# Or via dedicated script:
python launch_legacy.py
```
*Or double-click `run_legacy.bat`.*

---

## Running Verification & Benchmarks

The repository includes a comprehensive 34-test master verification suite and empirical IR evaluation harnesses:

```powershell
# Run the complete master verification suite (34 architecture, feature, robustness, and offline tests)
python tests\run_all_tests.py

# Run real-world regression tests (12 tests)
python tests\test_realworld_regressions.py

# Run the 112-query comprehensive blind evaluation & latency audit
python tests\audit_v3_evaluation.py
```

---

## License

MIT License. Designed and built with local-first privacy.
