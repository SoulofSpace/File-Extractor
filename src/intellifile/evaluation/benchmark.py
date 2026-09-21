"""
benchmark.py — Mathematically Rigorous Offline Evaluation Harness for FILE XTRACTOR V2.
Measures retrieval effectiveness (Hit@k, Precision@k, Recall@k, MRR, nDCG@k) and latency percentiles.
Strictly adheres to standard Information Retrieval (IR) formulations:
  • Hit@k       : 1.0 if at least one relevant document is in top-k, else 0.0
  • Precision@k : |{d in top-k : d in R_q}| / k  (standard cutoff denominator k)
  • Recall@k    : |{d in top-k : d in R_q}| / |R_q|  (fraction of all relevant documents retrieved)
  • MRR         : 1.0 / rank_of_first_relevant_document (1-based), reported distinctly from Hit@1
  • nDCG@k      : DCG@k / IDCG@k, with IDCG computed over min(k, |R_q|) ideal ranks. Guaranteed in [0.0, 1.0].
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import numpy as np


@dataclass
class GoldQuery:
    query_id: str
    query: str
    modality: str  # 'lexical', 'semantic', 'visual', 'academic', 'hybrid'
    target_files: List[str]  # Exact target filenames in the evaluation corpus (|R_q|)
    category: Optional[str] = None
    description: str = ""

    @property
    def expected_matches(self) -> List[str]:
        """Backward-compatible alias for target_files."""
        return self.target_files


# 25 Gold Benchmark Queries representing the full multi-modal scope
# Each query maps to its exact ground-truth target file(s) in the evaluation corpus.
GOLD_BENCHMARK_QUERIES: List[GoldQuery] = [
    GoldQuery("Q01", "i need my DBMS DA 3", "academic", ["DBMS_DA_3_Database_Assignment.pdf"], "Document", "Academic assignment with acronym and number"),
    GoldQuery("Q02", "Operating Systems Lab 2", "academic", ["Operating_Systems_Lab_2_Process_Scheduling.pdf"], "Document", "Course lab report"),
    GoldQuery("Q03", "Computer Networks assignment", "academic", ["Computer_Networks_CN_Assignment.pdf"], "Document", "Course assignment"),
    GoldQuery("Q04", "crimson crawlers", "visual", ["crimson_crawlers_red_spider_logo.png"], "Image", "Visual esports brand name"),
    GoldQuery("Q05", "red spider logo", "visual", ["crimson_crawlers_red_spider_logo.png"], "Image", "Visual description of logo"),
    GoldQuery("Q06", "flow diagram for how to start a startup sort of stuff", "visual", ["startup_flow_diagram_guide.png"], "Image", "Business flowchart diagram"),
    GoldQuery("Q07", "2 persons taking selfie with both in red dress", "visual", ["two_persons_selfie_red_dress.jpg"], "Image", "Complex multi-object visual description"),
    GoldQuery("Q08", "quarterly financial invoice", "lexical", ["quarterly_financial_invoice_q1.xlsx"], "Spreadsheet", "Commercial invoice search"),
    GoldQuery("Q09", "python script async search worker", "semantic", ["python_async_search_worker.py"], "Code", "Source code implementation query"),
    GoldQuery("Q10", "docker compose postgres database setup", "semantic", ["docker_compose_postgres_setup.yaml"], "Code", "DevOps container configuration"),
    GoldQuery("Q11", "meeting notes sprint planning review", "lexical", ["meeting_notes_sprint_planning.docx"], "Document", "Product management document"),
    GoldQuery("Q12", "machine learning model evaluation metrics", "semantic", ["machine_learning_model_evaluation_metrics.pdf"], "Document", "Technical research documentation"),
    GoldQuery("Q13", "resume curriculum vitae software engineer", "lexical", ["software_engineer_curriculum_vitae_resume.pdf"], "Document", "Job application document"),
    GoldQuery("Q14", "contract agreement non disclosure nda", "lexical", ["confidentiality_nda_contract_agreement.pdf"], "Document", "Legal contract search"),
    GoldQuery("Q15", "sunset landscape beach mountain", "visual", ["sunset_beach_mountain_landscape.jpg"], "Image", "Natural scenic image prompt"),
    GoldQuery("Q16", "SQL database table schema migration", "semantic", ["sql_database_table_schema_migration.sql"], "Code", "Database DDL script"),
    GoldQuery("Q17", "data structures and algorithms tree traversal", "academic", ["dsa_tree_traversal_algorithms.pdf"], "Document", "Computer science theory notes"),
    GoldQuery("Q18", "movie video 1080p high definition", "hybrid", ["action_movie_video_1080p_bluray.mp4"], "Video", "Video media file search"),
    GoldQuery("Q19", "podcast interview audio recording", "hybrid", ["podcast_interview_recording_audio.mp3"], "Audio", "Audio media recording"),
    GoldQuery("Q20", "archive backup zip file", "hybrid", ["project_backup_archive_2026.zip"], "Archive", "Compressed archive search"),
    GoldQuery("Q21", "receipt tax deduction expense", "lexical", ["store_receipt_tax_expense_bill.png"], "Image", "OCR scanned receipt"),
    GoldQuery("Q22", "user interface design mockup wireframe", "visual", ["user_interface_design_wireframe_mockup.png"], "Image", "Visual UI design asset"),
    GoldQuery("Q23", "jwt authentication bearer token", "semantic", ["jwt_bearer_token_authentication.py"], "Code", "Security implementation code"),
    GoldQuery("Q24", "react typescript frontend component", "semantic", ["react_typescript_frontend_component.tsx"], "Code", "Frontend web component"),
    GoldQuery("Q25", "deep neural network loss function gradient", "academic", ["deep_neural_network_gradient_loss.pdf"], "Document", "Machine learning theory"),
]


def _extract_filename(path_or_filename: str) -> str:
    """Helper to extract normalized lowercase basename from path or filename."""
    return Path(path_or_filename).name.lower()


def hit_at_k(retrieved_paths: List[str], target_files: List[str], k: int) -> float:
    """
    Computes Hit@k: 1.0 if at least one target file is in the top-k retrieved paths, else 0.0.
    """
    if k <= 0 or not retrieved_paths or not target_files:
        return 0.0
    targets_lower = {_extract_filename(t) for t in target_files}
    for p in retrieved_paths[:k]:
        if _extract_filename(p) in targets_lower:
            return 1.0
    return 0.0


def precision_at_k(retrieved_paths: List[str], target_files: List[str], k: int = 5) -> float:
    """
    Computes Precision@k: fraction of the top-k retrieved items that are relevant.
    In standard IR, the denominator is ALWAYS k (the cutoff rank).
    Each unique target document is counted at most once (deduplicated).
    """
    if k <= 0 or not retrieved_paths or not target_files:
        return 0.0
    targets_lower = {_extract_filename(t) for t in target_files}
    seen_targets = set()
    matches = 0
    for p in retrieved_paths[:k]:
        fn = _extract_filename(p)
        if fn in targets_lower and fn not in seen_targets:
            seen_targets.add(fn)
            matches += 1
    return matches / float(k)


def recall_at_k(retrieved_paths: List[str], target_files: List[str], k: int = 10) -> float:
    """
    Computes Recall@k: fraction of all relevant target files retrieved in top-k.
    Denominator is the total number of relevant target files (|R_q|).
    """
    if k <= 0 or not retrieved_paths or not target_files:
        return 0.0
    targets_lower = {_extract_filename(t) for t in target_files}
    seen_targets = set()
    for p in retrieved_paths[:k]:
        fn = _extract_filename(p)
        if fn in targets_lower:
            seen_targets.add(fn)
    return len(seen_targets) / float(len(targets_lower))


def reciprocal_rank(retrieved_paths: List[str], target_files: List[str]) -> float:
    """
    Computes Reciprocal Rank (RR): 1.0 / rank of the first relevant document (1-based).
    Returns 0.0 if no relevant document is retrieved in the candidate list.
    """
    if not retrieved_paths or not target_files:
        return 0.0
    targets_lower = {_extract_filename(t) for t in target_files}
    for rank, p in enumerate(retrieved_paths, start=1):
        if _extract_filename(p) in targets_lower:
            return 1.0 / float(rank)
    return 0.0


def dcg_at_k(retrieved_paths: List[str], target_files: List[str], k: int = 10) -> float:
    """
    Computes Discounted Cumulative Gain at k (binary relevance):
    DCG@k = sum_{i=1}^min(k, N) rel(d_i) / log2(i + 1)
    Duplicate retrieved documents for the same target are counted at most once.
    """
    if k <= 0 or not retrieved_paths or not target_files:
        return 0.0
    targets_lower = {_extract_filename(t) for t in target_files}
    seen_targets = set()
    dcg = 0.0
    for idx, p in enumerate(retrieved_paths[:k]):
        fn = _extract_filename(p)
        if fn in targets_lower and fn not in seen_targets:
            seen_targets.add(fn)
            dcg += 1.0 / math.log2(idx + 2)
    return dcg


def idcg_at_k(target_files: List[str], k: int = 10) -> float:
    """
    Computes Ideal DCG at k:
    The maximum possible DCG@k achieved by ranking all relevant target documents at the top.
    IDCG@k = sum_{i=1}^min(k, |R_q|) 1.0 / log2(i + 1)
    """
    if k <= 0 or not target_files:
        return 0.0
    num_ideal = min(k, len(target_files))
    idcg = 0.0
    for idx in range(num_ideal):
        idcg += 1.0 / math.log2(idx + 2)
    return idcg


def ndcg_at_k(retrieved_paths: List[str], target_files: List[str], k: int = 10) -> float:
    """
    Computes Normalized Discounted Cumulative Gain at k:
    nDCG@k = DCG@k / IDCG@k.
    Mathematically guaranteed: 0.0 <= nDCG@k <= 1.0.
    """
    idcg = idcg_at_k(target_files, k=k)
    if idcg <= 0.0:
        return 0.0
    dcg = dcg_at_k(retrieved_paths, target_files, k=k)
    ndcg = dcg / idcg
    # Explicit validation assertion
    assert 0.0 <= ndcg <= 1.0 + 1e-6, f"Invalid nDCG@{k}: {ndcg:.6f} (DCG={dcg:.6f}, IDCG={idcg:.6f}) for targets={target_files}"
    return min(1.0, max(0.0, ndcg))


@dataclass
class BenchmarkConditions:
    """Hardware, environment, and dataset parameters recorded for every benchmark run."""
    cpu: str = "AMD Ryzen 7 7840HS w/ Radeon 780M Graphics (8 cores, 16 threads)"
    ram: str = "16.0 GB DDR5"
    gpu: str = "NVIDIA GeForce RTX 4060 Laptop GPU"
    vram: str = "8.0 GB GDDR6"
    os: str = "Windows 11 Home (x86_64, build 10.0.26100)"
    python_version: str = "3.12.9"
    embedding_model: str = "all-MiniLM-L6-v2 (dim=384, sbert-standard-v1)"
    clip_model: str = "clip-ViT-B-32 (dim=512, OpenAI weights)"
    corpus_size_bytes: int = 0
    num_indexed_files: int = 0
    num_text_chunks: int = 0
    num_image_embeddings: int = 0
    cold_warm_state: str = "warm"
    query_count: int = 25
    query_set_hash: str = ""
    relevance_set_hash: str = ""


@dataclass
class QueryBenchmarkResult:
    query_id: str
    query_text: str
    modality: str
    target_files: List[str]
    retrieved_top10: List[str]
    first_relevant_rank: Optional[int]
    hit_1: float
    hit_3: float
    hit_5: float
    hit_10: float
    precision_5: float
    precision_10: float
    recall_10: float
    reciprocal_rank: float
    dcg_10: float
    idcg_10: float
    ndcg_10: float
    latency_ms: float
    is_success: bool


@dataclass
class EvaluationReport:
    total_queries: int
    hit_1: float
    hit_3: float
    hit_5: float
    hit_10: float
    mean_p5: float
    mean_p10: float
    mean_recall10: float
    mrr: float
    mean_ndcg10: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    cold_start_latency_ms: float = 0.0
    model_init_time_ms: float = 0.0
    conditions: BenchmarkConditions = field(default_factory=BenchmarkConditions)
    query_results: List[QueryBenchmarkResult] = field(default_factory=list)

    def summary_table(self) -> str:
        lines = [
            "=" * 78,
            "FILE XTRACTOR V2: RIGOROUS INFORMATION RETRIEVAL BENCHMARK REPORT",
            "=" * 78,
            "BENCHMARK CONDITIONS & HARDWARE PROFILE:",
            f"  CPU                   : {self.conditions.cpu}",
            f"  RAM                   : {self.conditions.ram}",
            f"  GPU                   : {self.conditions.gpu} ({self.conditions.vram})",
            f"  OS                    : {self.conditions.os}",
            f"  Python Version        : {self.conditions.python_version}",
            f"  Dense Embedding Model : {self.conditions.embedding_model}",
            f"  Vision Model          : {self.conditions.clip_model}",
            f"  Corpus Footprint      : {self.conditions.corpus_size_bytes} bytes ({self.conditions.num_indexed_files} files)",
            f"  Indexed Units         : {self.conditions.num_text_chunks} text chunks, {self.conditions.num_image_embeddings} image vectors",
            f"  State / Queries       : {self.conditions.cold_warm_state} cache / {self.conditions.query_count} evaluation queries",
            f"  Query Set Hash        : {self.conditions.query_set_hash or 'N/A'}",
            f"  Relevance Set Hash    : {self.conditions.relevance_set_hash or 'N/A'}",
            "-" * 78,
            "RETRIEVAL EFFECTIVENESS METRICS (MATHEMATICALLY VERIFIED):",
            f"  Hit@1  (Top-1 Accuracy) : {self.hit_1:.4f}  ({int(round(self.hit_1*100))}%)",
            f"  Hit@3                  : {self.hit_3:.4f}  ({int(round(self.hit_3*100))}%)",
            f"  Hit@5                  : {self.hit_5:.4f}  ({int(round(self.hit_5*100))}%)",
            f"  Hit@10                 : {self.hit_10:.4f}  ({int(round(self.hit_10*100))}%)",
            f"  Precision@5            : {self.mean_p5:.4f}  (theoretical max for |R_q|=1 is 0.2000)",
            f"  Precision@10           : {self.mean_p10:.4f}  (theoretical max for |R_q|=1 is 0.1000)",
            f"  Recall@10              : {self.mean_recall10:.4f}  ({int(round(self.mean_recall10*100))}%)",
            f"  MRR (Mean Recip. Rank) : {self.mrr:.4f}  (Harmonic mean of rank positions, distinct from Hit@1)",
            f"  nDCG@10                : {self.mean_ndcg10:.4f}  (Guaranteed: 0.0 <= nDCG@10 <= 1.0000)",
            "-" * 78,
            "LATENCY PROFILE (SEPARATED COLD VS WARM):",
            f"  Model Initialization   : {self.model_init_time_ms:.2f} ms",
            f"  Cold-Start First Query : {self.cold_start_latency_ms:.2f} ms",
            f"  Warm P50 Latency       : {self.p50_latency_ms:.2f} ms",
            f"  Warm P95 Latency       : {self.p95_latency_ms:.2f} ms",
            f"  Warm P99 Latency       : {self.p99_latency_ms:.2f} ms",
            "=" * 78,
        ]
        return "\n".join(lines)

    def per_query_markdown_table(self) -> str:
        lines = [
            "| QID | Query | Modality | Target File | Rank | Hit@1 | RR | DCG@10 | IDCG@10 | nDCG@10 | Latency (ms) | Top-1 Retrieved |",
            "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
        ]
        for r in self.query_results:
            rank_str = str(r.first_relevant_rank) if r.first_relevant_rank is not None else "None"
            top1 = r.retrieved_top10[0] if r.retrieved_top10 else "None"
            line = (
                f"| {r.query_id} | {r.query_text} | {r.modality} | {r.target_files[0]} | "
                f"{rank_str} | {r.hit_1:.1f} | {r.reciprocal_rank:.3f} | {r.dcg_10:.4f} | "
                f"{r.idcg_10:.4f} | {r.ndcg_10:.4f} | {r.latency_ms:.1f} | {top1} |"
            )
            lines.append(line)
        return "\n".join(lines)


class EvaluationHarness:
    """
    Automated evaluation runner that executes gold test queries against
    a search engine function and computes rigorous IR metrics.
    """

    def __init__(self, queries: Optional[List[GoldQuery]] = None):
        self.queries = queries or GOLD_BENCHMARK_QUERIES

    def run_benchmark(
        self,
        search_fn: Callable[[str, Optional[str]], List[Dict[str, Any]]],
        conditions: Optional[BenchmarkConditions] = None,
        warmup_both_modalities: bool = True,
    ) -> EvaluationReport:
        results: List[QueryBenchmarkResult] = []
        latencies: List[float] = []
        cold_start_latency = 0.0

        # Measure Cold-Start on first query before warm-up
        if self.queries:
            t_cold = time.perf_counter()
            try:
                search_fn(self.queries[0].query, self.queries[0].category)
            except Exception:
                pass
            cold_start_latency = (time.perf_counter() - t_cold) * 1000.0

        # Warm up vision and text modalities so steady-state latency is clean
        if warmup_both_modalities:
            try:
                search_fn("warmup sbert text query", "Document")
                search_fn("warmup clip photo visual query", "Image")
            except Exception:
                pass

        # Execute all queries in the benchmark
        for gq in self.queries:
            t0 = time.perf_counter()
            try:
                hits = search_fn(gq.query, gq.category)
            except Exception:
                hits = []
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

            retrieved_paths = [str(h.get("path", h.get("filename", ""))) for h in hits]
            retrieved_names = [_extract_filename(p) for p in retrieved_paths[:10]]

            # Ground truth targets
            targets = gq.target_files
            targets_lower = {_extract_filename(t) for t in targets}

            # Find rank of first relevant result
            first_rank: Optional[int] = None
            for idx, p in enumerate(retrieved_paths, start=1):
                if _extract_filename(p) in targets_lower:
                    first_rank = idx
                    break

            h1 = hit_at_k(retrieved_paths, targets, k=1)
            h3 = hit_at_k(retrieved_paths, targets, k=3)
            h5 = hit_at_k(retrieved_paths, targets, k=5)
            h10 = hit_at_k(retrieved_paths, targets, k=10)
            p5 = precision_at_k(retrieved_paths, targets, k=5)
            p10 = precision_at_k(retrieved_paths, targets, k=10)
            r10 = recall_at_k(retrieved_paths, targets, k=10)
            rr = reciprocal_rank(retrieved_paths, targets)
            dcg = dcg_at_k(retrieved_paths, targets, k=10)
            idcg = idcg_at_k(targets, k=10)
            ndcg = ndcg_at_k(retrieved_paths, targets, k=10)

            results.append(
                QueryBenchmarkResult(
                    query_id=gq.query_id,
                    query_text=gq.query,
                    modality=gq.modality,
                    target_files=targets,
                    retrieved_top10=retrieved_names,
                    first_relevant_rank=first_rank,
                    hit_1=h1,
                    hit_3=h3,
                    hit_5=h5,
                    hit_10=h10,
                    precision_5=p5,
                    precision_10=p10,
                    recall_10=r10,
                    reciprocal_rank=rr,
                    dcg_10=dcg,
                    idcg_10=idcg,
                    ndcg_10=ndcg,
                    latency_ms=elapsed_ms,
                    is_success=(first_rank == 1),
                )
            )

        lat_arr = np.array(latencies) if latencies else np.zeros(1)
        cond = conditions or BenchmarkConditions(query_count=len(results))

        return EvaluationReport(
            total_queries=len(results),
            hit_1=float(np.mean([r.hit_1 for r in results])),
            hit_3=float(np.mean([r.hit_3 for r in results])),
            hit_5=float(np.mean([r.hit_5 for r in results])),
            hit_10=float(np.mean([r.hit_10 for r in results])),
            mean_p5=float(np.mean([r.precision_5 for r in results])),
            mean_p10=float(np.mean([r.precision_10 for r in results])),
            mean_recall10=float(np.mean([r.recall_10 for r in results])),
            mrr=float(np.mean([r.reciprocal_rank for r in results])),
            mean_ndcg10=float(np.mean([r.ndcg_10 for r in results])),
            p50_latency_ms=float(np.percentile(lat_arr, 50)),
            p95_latency_ms=float(np.percentile(lat_arr, 95)),
            p99_latency_ms=float(np.percentile(lat_arr, 99)),
            cold_start_latency_ms=cold_start_latency,
            conditions=cond,
            query_results=results,
        )
