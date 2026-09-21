import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json
from unittest.mock import MagicMock, patch
from PIL import Image

from intellifile.domain.vlm_provider import (
    DocumentUnderstandingResult,
    ModelInfo,
    VLMResponse,
)
from intellifile.vlm.model_manager import ModelManager, get_model_manager
from intellifile.vlm.local_qwen import LocalQwen35Provider


def test_model_manager_hardware():
    manager = ModelManager()
    hw = manager.detect_hardware()
    assert hw is not None
    assert hw.device_type in ("cuda", "cpu")
    assert isinstance(hw.gpu_name, str)


def test_model_manager_health():
    manager = get_model_manager()
    # If the local server is running, check_health returns True; if not, False without crashing
    healthy = manager.check_health()
    assert isinstance(healthy, bool)


def test_qwen_json_extraction_clean():
    provider = LocalQwen35Provider()
    raw = '{"document_type": "poster", "title": "Data Quest 3.0", "objects": ["laptop", "phone"]}'
    res = provider._extract_json(raw)
    assert res == {"document_type": "poster", "title": "Data Quest 3.0", "objects": ["laptop", "phone"]}


def test_qwen_json_extraction_markdown_fence():
    provider = LocalQwen35Provider()
    raw = 'Here is the result:\n```json\n{"document_type": "receipt", "title": "Store Receipt", "objects": []}\n```\nHope that helps!'
    res = provider._extract_json(raw)
    assert res is not None
    assert res["document_type"] == "receipt"
    assert res["title"] == "Store Receipt"


def test_build_result_from_json():
    provider = LocalQwen35Provider()
    data = {
        "document_type": "poster",
        "title": "Data Quest 3.0",
        "description": "Annual 24-hour hackathon",
        "event_name": "Data Quest",
        "dates": ["October 7 & 8"],
        "locations": ["MG Auditorium"],
        "objects": ["dog", "laptop"],
        "semantic_tags": ["hackathon", "coding"],
        "attributes": {"prize_pool": "₹25K", "registration_fee": "₹199"},
        "important_text": ["DATA QUEST 3.0", "VIT Chennai"],
    }
    result = provider._build_result_from_json(data)
    assert isinstance(result, DocumentUnderstandingResult)
    assert result.document_type == "poster"
    assert result.title == "Data Quest 3.0"
    assert "dog" in result.objects
    assert "laptop" in result.objects
    assert "hackathon" in result.semantic_tags

    terms = result.all_searchable_terms()
    assert "dog" in terms
    assert "hackathon" in terms
    assert "quest" in terms


def test_live_qwen_text_generation():
    provider = LocalQwen35Provider()
    resp = provider.generate(
        prompt="Reply with exactly one word: 'READY'.",
        max_tokens=64,
        temperature=0.0,
    )
    assert isinstance(resp, VLMResponse)
    assert "READY" in resp.content.upper() or "READY" in (resp.reasoning_content or "").upper()


def test_concept_normalizer():
    from intellifile.vlm.normalizer import ConceptNormalizer
    assert ConceptNormalizer.clean_term("QR-Code") == "qr code"
    assert ConceptNormalizer.clean_term("puppy") == "dog"
    assert ConceptNormalizer.clean_term("laptop computer") == "laptop"

    norm = ConceptNormalizer.categorize_concepts(
        objects=["dog", "pup", "laptop"],
        visual_concepts=["warm lighting", "modern", "blue banner"],
        semantic_tags=["hackathon", "technology"],
    )
    assert "dog" in norm.core_concepts
    assert "laptop" in norm.core_concepts
    assert "hackathon" in norm.core_concepts
    assert "warm lighting" in norm.secondary_concepts
    assert "blue banner" in norm.core_concepts


def test_database_v3_document_understanding():
    import tempfile
    from intellifile.database import Database
    from intellifile.models import DiscoveredFile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_v3.sqlite3"
        db = Database(db_path)

        # Check PRAGMA user_version is 3
        with db.connection() as conn:
            ver = conn.execute("PRAGMA user_version").fetchone()[0]
            assert ver == 3

        # Add a folder and file
        folder_id = db.add_folder(tmpdir)
        dummy_file = Path(tmpdir) / "IMG_1234.jpg"
        dummy_file.write_text("dummy")
        file_id = db.upsert_file(
            folder_id,
            DiscoveredFile(dummy_file, ".jpg", 5, 1000.0, 1000.0),
        )

        # Upsert document understanding
        res = DocumentUnderstandingResult(
            document_type="poster",
            title="Data Quest 3.0",
            description="VIT Chennai 24 hour hackathon with ₹25K prize",
            event_name="Data Quest",
            objects=["laptop", "phone"],
            semantic_tags=["hackathon", "coding", "prize"],
            visual_concepts=["dark theme", "neon banner"],
            attributes={"prize_pool": "₹25K", "entry_fee": "₹199"},
            important_text=["DATA QUEST 3.0", "VIT Chennai"],
        )
        du_id = db.upsert_document_understanding(
            file_id=file_id,
            result=res,
            content_hash="abc123hash",
        )
        assert du_id > 0

        # Retrieve by file_id
        fetched = db.get_document_understanding(file_id)
        assert fetched is not None
        assert fetched["document_type"] == "poster"
        assert fetched["title"] == "Data Quest 3.0"

        # Retrieve by hash
        by_hash = db.get_document_understanding_by_hash("abc123hash")
        assert by_hash is not None
        assert by_hash["title"] == "Data Quest 3.0"

        # Search by concept
        search_res = db.search_document_understanding("hackathon")
        assert len(search_res) == 1
        assert search_res[0]["file_id"] == file_id

        # Search FTS5 file_search to verify enriched full-text
        fts_res = db.keyword_search("hackathon")
        assert len(fts_res) == 1
        assert fts_res[0]["id"] == file_id


def run_all_vlm_tests():
    print("Running VLM Provider tests...")
    test_model_manager_hardware()
    print("  [PASS] test_model_manager_hardware")
    test_model_manager_health()
    print("  [PASS] test_model_manager_health")
    test_qwen_json_extraction_clean()
    print("  [PASS] test_qwen_json_extraction_clean")
    test_qwen_json_extraction_markdown_fence()
    print("  [PASS] test_qwen_json_extraction_markdown_fence")
    test_build_result_from_json()
    print("  [PASS] test_build_result_from_json")
    test_concept_normalizer()
    print("  [PASS] test_concept_normalizer")
    test_database_v3_document_understanding()
    print("  [PASS] test_database_v3_document_understanding")
    
    manager = get_model_manager()
    if manager.check_health():
        test_live_qwen_text_generation()
        print("  [PASS] test_live_qwen_text_generation")
    else:
        print("  [SKIP] test_live_qwen_text_generation (server offline)")
    print("All VLM Provider & DB V3 tests passed successfully!")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    run_all_vlm_tests()


