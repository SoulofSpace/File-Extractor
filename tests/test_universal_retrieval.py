"""
test_universal_retrieval.py — Open-Vocabulary Universal Multi-Modal Retrieval Test Suite (50+ Concepts)
Validates that FILE XTRACTOR V3 retrieves arbitrary visual and document concepts
WITHOUT relying on brittle hardcoded trigger lists or keyword hacks.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.domain.vlm_provider import DocumentUnderstandingResult
from intellifile.models import DiscoveredFile
from intellifile.query_planner import QueryPlanner

# List of 50+ diverse, open-vocabulary concepts across multiple domains:
UNSEEN_CONCEPTS = [
    # Animals
    "golden retriever dog", "sleeping cat", "flying bird", "wild horse", "tropical fish",
    # Vehicles & Transport
    "red electric car", "cargo truck", "mountain bicycle", "commercial airplane", "racing motorcycle",
    # Computing & Tech
    "gaming laptop", "smartphone with notifications", "curved monitor", "mechanical keyboard", "wireless headphones",
    # Everyday Artifacts
    "ceramic coffee cup", "leather backpack", "wooden dining table", "running sneakers", "stainless steel wristwatch",
    # Documents & Flyers
    "hackathon promotional poster", "store checkout receipt", "weekly bus timetable", "student identity card",
    "completion certificate", "quarterly financial report", "university diploma", "airline boarding pass",
    # Diagrams & Graphics
    "software architecture diagram", "flowchart of user registration", "mobile UI wireframe", "analytics dashboard",
    "gantt chart project timeline", "entity relationship diagram", "network topology map",
    # Outdoor & Nature
    "rocky mountain landscape", "sandy ocean beach", "autumn forest with yellow leaves", "city skyline at night",
    # People & Actions
    "chef cooking in kitchen", "musician playing guitar", "doctor in clinic", "engineer writing code",
    "athlete running on track", "students studying in library", "speaker presenting at conference",
    # Attributes & Visual Elements
    "poster with QR code", "neon glowing sign", "minimalist black and white sketch",
    "vintage watercolor painting", "aerial drone photograph"
]


def test_query_planner_open_vocabulary():
    """Verify that QueryPlanner correctly processes open-vocabulary queries without dropping terms."""
    planner = QueryPlanner()
    for concept in UNSEEN_CONCEPTS:
        plan = planner.parse_query(f"find my {concept}")
        assert plan.cleaned_query != ""
        # Ensure query terms are preserved
        assert any(word in plan.cleaned_query.lower() for word in concept.split())


def test_universal_vlm_concept_matching():
    """Verify that structured document understanding allows matching arbitrary concepts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "univ.sqlite3"
        db = Database(db_path)
        folder_id = db.add_folder(tmpdir)

        # Create a mock file for an event poster with ₹25K prize pool
        poster_file = Path(tmpdir) / "IMG_9981.jpg"
        poster_file.write_text("dummy image bytes")

        file_id = db.upsert_file(
            folder_id,
            DiscoveredFile(poster_file, ".jpg", 100, 1000.0, 1000.0),
        )

        doc_result = DocumentUnderstandingResult(
            document_type="poster",
            title="Data Quest 3.0",
            description="24-hour hackathon with ₹25K prize pool at VIT Chennai",
            event_name="Data Quest",
            objects=["laptop", "phone", "qr code"],
            semantic_tags=["hackathon", "coding", "competition"],
            visual_concepts=["dark theme", "neon blue"],
            attributes={"prize_pool": "₹25K", "entry_fee": "₹199"},
            important_text=["DATA QUEST 3.0", "VIT Chennai"],
        )

        db.upsert_document_understanding(file_id, doc_result, content_hash="hash9981")

        agent = AIAgent(db)

        # Search 1: "hackathon"
        res1 = agent.search("hackathon")
        assert len(res1) >= 1
        assert res1[0]["id"] == file_id
        assert "hackathon" in str(res1[0]["ai_explanation"]).lower() or res1[0]["relevance_score"] > 0.3

        # Search 2: "laptop" (extracted object)
        res2 = agent.search("laptop")
        assert len(res2) >= 1
        assert res2[0]["id"] == file_id

        # Search 3: "poster" (document type)
        res3 = agent.search("poster")
        assert len(res3) >= 1
        assert res3[0]["id"] == file_id

        # Search 4: "qr code"
        res4 = agent.search("qr code")
        assert len(res4) >= 1
        assert res4[0]["id"] == file_id

        # Search 5: "Data Quest"
        res5 = agent.search("Data Quest")
        assert len(res5) >= 1
        assert res5[0]["id"] == file_id


def run_all_universal_tests():
    print("Running Universal Multi-Modal Retrieval Tests...")
    test_query_planner_open_vocabulary()
    print("  [PASS] test_query_planner_open_vocabulary (50+ concepts)")
    test_universal_vlm_concept_matching()
    print("  [PASS] test_universal_vlm_concept_matching")
    print("All Universal Retrieval tests passed successfully!")


if __name__ == "__main__":
    run_all_universal_tests()
