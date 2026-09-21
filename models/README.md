# Local Model Management — FILE XTRACTOR V3

## Overview
FILE XTRACTOR V3 is built on a 100% offline, local-first architecture. No file contents, queries, or embeddings are transmitted to cloud services.

## Models

### 1. Vision-Language Model: Qwen3.5-4B (GGUF)
- **Model Identifier**: `lmstudio-community/Qwen3.5-4B-GGUF:Q4_K_M`
- **GGUF File**: `Qwen3.5-4B-Q4_K_M.gguf`
- **Multimodal Projector**: `mmproj-Qwen3.5-4B-BF16.gguf`
- **Serving Engine**: `llama.cpp` (`llama.exe`)
- **Default Endpoint**: `http://127.0.0.1:8080`
- **Context Length**: 96,768 tokens
- **Capabilities**: Document understanding, poster title/prize extraction, object recognition, layout parsing, candidate reranking.

#### Launching the llama.cpp Server
```powershell
& llama.exe --model "<path_to_gguf>/Qwen3.5-4B-Q4_K_M.gguf" --mmproj "<path_to_gguf>/mmproj-Qwen3.5-4B-BF16.gguf" --port 8080 --ngl 99 --ctx-size 8192
```

### 2. Dense Semantic Embedding: all-MiniLM-L6-v2
- **Dimension**: 384
- **Backend**: Sentence Transformers / HuggingFace Transformers
- **Purpose**: Fast lexical-semantic text retrieval for documents, code, and notes.

### 3. Fast Multimodal Vision Embedding: clip-ViT-B-32
- **Dimension**: 512
- **Backend**: Sentence Transformers / OpenAI weights
- **Purpose**: Sub-10ms visual retrieval across indexed image collections.

## Fallback & Graceful Degradation
If the local `llama.cpp` server is not running:
1. Retrieval automatically uses the V2 hybrid engine (BM25 + OCR + SBERT + CLIP).
2. All search operations continue normally without errors or crashes.
3. When the server becomes active, VLM understanding is enabled automatically.
