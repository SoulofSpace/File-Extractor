"""
run_all_tests.py — Master Test Runner for FILE XTRACTOR V2.
Discovers and runs all test functions across architecture, features, robustness, and offline suites.
Outputs exact counts of Total, Passed, and Failed tests.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import test_v2_architecture
import test_v2_features
import test_robustness
import test_offline_verification
import test_evaluation_benchmark
import test_ablation
import test_vlm_provider
import test_universal_retrieval
import test_blind_generalization

TEST_FUNCTIONS = [
    # Architecture tests (6)
    ("Architecture: Hashing & Fast-path", test_v2_architecture.test_hashing_and_fast_path),
    ("Architecture: Perceptual Hashing", test_v2_architecture.test_perceptual_hash),
    ("Architecture: SQLiteFlatVectorStore", test_v2_architecture.test_vector_store),
    ("Architecture: Database V2 Migration", test_v2_architecture.test_database_v2_migration),
    ("Architecture: Evaluation Harness IR Metrics", test_v2_architecture.test_evaluation_harness_metrics),
    ("Architecture: TextEmbeddingProvider Contract", test_v2_architecture.test_embedding_provider_contract),
    # V3 Universal Multimodal Intelligence Tests (3)
    ("V3 Multimodal: VLM Provider & DB V3 Storage", test_vlm_provider.run_all_vlm_tests),
    ("V3 Multimodal: Universal Retrieval 50+ Concepts", test_universal_retrieval.run_all_universal_tests),
    ("V3 Multimodal: Blind Generalization Benchmark", test_blind_generalization.run_blind_generalization_benchmark),
    # Feature tests (3)
    ("Features: AI Agent Multi-Modal Fusion", test_v2_features.test_ai_agent_fusion),
    ("Features: Duplicate Detection", test_v2_features.test_duplicate_detection),
    ("Features: Watcher Ignore Rules", test_v2_features.test_watcher_ignore_rules),
    # Robustness failure tests (14)
    ("Robustness: 1. Corrupted PDFs", test_robustness.test_corrupted_pdfs),
    ("Robustness: 2. Zero-byte Files", test_robustness.test_zero_byte_files),
    ("Robustness: 3. Locked Files", test_robustness.test_locked_files),
    ("Robustness: 4. Unreadable Files", test_robustness.test_unreadable_files),
    ("Robustness: 5. Malformed Images", test_robustness.test_malformed_images),
    ("Robustness: 6. Huge Images (OOM Guard)", test_robustness.test_huge_images),
    ("Robustness: 7. Rotated & Noisy OCR Images", test_robustness.test_rotated_noisy_ocr_images),
    ("Robustness: 8. Very Large PDFs", test_robustness.test_very_large_pdfs),
    ("Robustness: 9. Deleted Files During Scan", test_robustness.test_deleted_files_during_indexing),
    ("Robustness: 10. Renamed Files During Scan", test_robustness.test_renamed_files_during_indexing),
    ("Robustness: 11. Modified Files During Scan", test_robustness.test_modified_files_during_indexing),
    ("Robustness: 12. Duplicate Files", test_robustness.test_duplicate_files),
    ("Robustness: 13. Unsupported File Types", test_robustness.test_unsupported_file_types),
    ("Robustness: 14. Concurrent Search & Indexing", test_robustness.test_concurrent_search_during_indexing),
    ("Robustness: 15. Empty & Whitespace Queries", test_robustness.test_empty_and_whitespace_queries),
    ("Robustness: 16. Unicode & Long Filenames", test_robustness.test_unicode_and_long_filenames),
    ("Robustness: 17. Missing Modalities Fallback", test_robustness.test_missing_modalities_fallback),
    ("Robustness: 18. Zero Search Results", test_robustness.test_zero_search_results),
    ("Robustness: 19. Duplicate Results Prevented", test_robustness.test_duplicate_search_results_prevented),
    ("Robustness: 20. Interrupted Indexing & Restart", test_robustness.test_interrupted_indexing_and_restart),
    # Strict Offline Verification (1)
    ("Offline: 100% Sockets Blocked Verification", test_offline_verification.run_offline_verification),
    # Benchmark verification (1)
    ("Benchmark: 25 Gold Queries Evaluation", test_evaluation_benchmark.run_gold_benchmark),
]



def main():
    print("=" * 80)
    print(f"FILE XTRACTOR V2: EXECUTING FULL MASTER VERIFICATION SUITE ({len(TEST_FUNCTIONS)} TESTS)")
    print("=" * 80)

    passed = 0
    failed = 0
    failed_names = []

    for name, fn in TEST_FUNCTIONS:
        t0 = time.time()
        try:
            fn()
            elapsed = time.time() - t0
            print(f"  [PASS] {name} ({elapsed:.2f}s)")
            passed += 1
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  [FAIL] {name} ({elapsed:.2f}s) -> {e}")
            failed += 1
            failed_names.append((name, str(e)))

    print("=" * 80)
    print("TEST EXECUTION SUMMARY:")
    print(f"  Total Test Cases : {len(TEST_FUNCTIONS)}")
    print(f"  Passed Tests     : {passed}")
    print(f"  Failed Tests     : {failed}")
    if failed_names:
        print("  Failures:")
        for name, err in failed_names:
            print(f"    - {name}: {err}")
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
