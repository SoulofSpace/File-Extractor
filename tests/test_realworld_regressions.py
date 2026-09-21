"""
test_realworld_regressions.py — Real-World Search Regression Test Suite (R01–R12)
Validates that FILE XTRACTOR V2 avoids real-world regressions identified in production:
  R01: "guy in blue dress" -> Blue dress image ranks above Red dress image
  R02: "guy in red dress" -> Red dress image ranks above Blue dress image
  R03: "guy in green dress" -> Green dress image ranks above Red & Blue dress images
  R04: "time table" -> Timetable image retrieved at Rank 1
  R05: "timetable" -> Timetable image retrieved at Rank 1
  R06: "time_table" -> Timetable image retrieved at Rank 1
  R07: "my college timetable" -> Timetable image retrieved in Top-3
  R08: "id card" -> ID card image ranks #1, unrelated crash reports excluded/suppressed
  R09: "identity card" -> ID card image ranks #1
  R10: "college ID card" -> College ID card front ranks #1
  R11: "student ID card" -> College ID card front ranks in Top-3
  R12: "my ID" -> User identity documents retrieved without crash report false positives
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Auto-add src to sys.path
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from intellifile.database import Database
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider


class TestRealWorldRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real_db_path = Path(r"C:\Users\space\AppData\Local\IntelliFile\intellifile.sqlite3")
        cls.use_real_db = cls.real_db_path.exists()
        
        if cls.use_real_db:
            cls.db = Database(cls.real_db_path)
            cls.vstore = SQLiteFlatVectorStore(cls.real_db_path)
            cls.embed_provider = SentenceTransformerProvider()
            cls.agent = AIAgent(
                cls.db,
                embedding_provider=cls.embed_provider,
                vector_store=cls.vstore,
            )
        else:
            # Fallback for isolated CI environments without user directory
            cls.agent = None

    def _get_ranks(self, query: str, limit: int = 15) -> list[str]:
        results = self.agent.search(query, limit=limit)
        return [str(r.get("filename", Path(r.get("path", "")).name)) for r in results]

    def test_R01_guy_in_blue_dress(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("guy in blue dress")
        self.assertTrue(len(ranks) > 0, "Should return results")
        # 2abbbf8a... is the blue dress image, WhatsApp ... 9.11.17 PM is red
        blue_idx = next((i for i, fn in enumerate(ranks) if "2abbbf8a" in fn), 999)
        red_idx = next((i for i, fn in enumerate(ranks) if "9.11.17 PM" in fn), 999)
        self.assertLess(blue_idx, red_idx, f"Blue image (rank {blue_idx}) must rank above Red image (rank {red_idx})")
        self.assertEqual(blue_idx, 0, "Blue image should be Rank 1")

    def test_R02_guy_in_red_dress(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("guy in red dress")
        self.assertTrue(len(ranks) > 0, "Should return results")
        # All three photos from August 25 (9.11.17 PM, 10.57.26 PM, 10.58.05 PM) are red dress images
        red_photos = [i for i, fn in enumerate(ranks) if any(t in fn for t in ["9.11.17 PM", "10.57.26 PM", "10.58.05 PM"])]
        self.assertTrue(len(red_photos) > 0, "At least one red image should be returned")
        blue_idx = next((i for i, fn in enumerate(ranks) if "2abbbf8a" in fn), 999)
        self.assertLess(red_photos[0], blue_idx, f"Red image (rank {red_photos[0]}) must rank above Blue image (rank {blue_idx})")
        self.assertEqual(red_photos[0], 0, "A red image should be Rank 1")

    def test_R03_guy_in_third_color(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("guy in green dress")
        self.assertTrue(len(ranks) > 0, "Should return results")
        green_idx = next((i for i, fn in enumerate(ranks) if "ChatGPT Image" in fn or "03_27_13" in fn), 999)
        red_idx = next((i for i, fn in enumerate(ranks) if "9.11.17 PM" in fn), 999)
        blue_idx = next((i for i, fn in enumerate(ranks) if "2abbbf8a" in fn), 999)
        self.assertLess(green_idx, red_idx, "Green image must rank above Red image")
        self.assertLess(green_idx, blue_idx, "Green image must rank above Blue image")
        self.assertEqual(green_idx, 0, "Green image should be Rank 1")

    def test_R04_time_table(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("time table")
        self.assertTrue(len(ranks) > 0, "Should return results")
        # WhatsApp Image 2026-08-24 at 12.10.55 PM is the timetable
        self.assertIn("12.10.55 PM", ranks[0], f"Timetable image must be Rank 1, got {ranks[0]}")

    def test_R05_timetable(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("timetable")
        self.assertTrue(len(ranks) > 0, "Should return results")
        self.assertIn("12.10.55 PM", ranks[0], f"Timetable image must be Rank 1, got {ranks[0]}")

    def test_R06_time_table_underscore(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("time_table")
        self.assertTrue(len(ranks) > 0, "Should return results")
        self.assertIn("12.10.55 PM", ranks[0], f"Timetable image must be Rank 1, got {ranks[0]}")

    def test_R07_my_college_timetable(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("my college timetable")
        self.assertTrue(len(ranks) > 0, "Should return results")
        tt_idx = next((i for i, fn in enumerate(ranks) if "12.10.55 PM" in fn), 999)
        self.assertLess(tt_idx, 3, f"Timetable image should be in Top-3, got rank {tt_idx}")

    def test_R08_id_card(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("id card")
        self.assertTrue(len(ranks) > 0, "Should return results")
        # Top 1 should be the college ID card front (7.58.44 AM (1))
        self.assertTrue("7.58.44 AM (1)" in ranks[0] or "1.44.17 PM" in ranks[0],
                        f"Rank 1 should be ID card image, got {ranks[0]}")
        # AI171 Report.pdf should NOT be in top 3
        top_3 = ranks[:3]
        self.assertNotIn("AI171 Report.pdf", top_3, "AI171 crash report must not falsely appear in Top-3 for id card")

    def test_R09_identity_card(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("identity card")
        self.assertTrue(len(ranks) > 0, "Should return results")
        self.assertTrue("7.58.44 AM" in ranks[0] or "1.44.17 PM" in ranks[0],
                        f"Rank 1 should be ID card image, got {ranks[0]}")

    def test_R10_college_id_card(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("college ID card")
        self.assertTrue(len(ranks) > 0, "Should return results")
        self.assertIn("7.58.44 AM (1)", ranks[0], f"College ID card front must be Rank 1, got {ranks[0]}")

    def test_R11_student_id_card(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("student ID card")
        self.assertTrue(len(ranks) > 0, "Should return results")
        id_idx = next((i for i, fn in enumerate(ranks) if "7.58.44 AM (1)" in fn or "1.44.17 PM" in fn), 999)
        self.assertLess(id_idx, 3, f"ID card should be in Top-3, got rank {id_idx}")

    def test_R12_my_id(self):
        if not self.use_real_db:
            self.skipTest("Real user database not present")
        ranks = self._get_ranks("my ID")
        self.assertTrue(len(ranks) > 0, "Should return results")
        # Verify AI171 Report.pdf does not appear at Rank 1
        self.assertNotEqual(ranks[0], "AI171 Report.pdf", "AI171 crash report must not be Rank 1 for 'my ID'")


if __name__ == "__main__":
    unittest.main()
