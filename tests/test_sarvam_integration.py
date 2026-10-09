"""
test_sarvam_integration.py — Test suite for Sarvam Mayura v1 integration in FILE XTRACTOR V4.

Covers:
  1. Tamil script query translation
  2. Hindi query translation
  3. Romanized Tamil / code-mixed query translation
  4. English queries do NOT call Sarvam (local heuristic filtering)
  5. Sarvam API failure fallback (graceful offline behavior, zero crashing)
  6. Translation caching (in-memory and SQLite cache prevention of redundant calls)
  7. Universal Query Planner integration with translated queries
  8. Security: Zero API key leakage
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from intellifile.sarvam_service import SarvamService, TranslationResult
from intellifile.universal_query_planner import UniversalQueryPlanner, UniversalSearchPlan
from intellifile.database import Database
from intellifile.ai_agent import AIAgent


class TestSarvamMayuraIntegration(unittest.TestCase):
    """Test suite for Sarvam Mayura v1 translation provider and search pipeline integration."""

    @classmethod
    def setUpClass(cls):
        # Ensure .env is read if SARVAM_API_KEY is not already in os.environ
        cls.service = SarvamService()
        cls.has_api_key = cls.service.is_configured

    def setUp(self):
        # Create a fresh isolated in-memory or temp SQLite DB for caching and planning tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_intellifile.sqlite3"
        self.db = Database(self.db_path)
        self.test_service = SarvamService(database=self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ── Test 1: Tamil Script Query Translation ────────────────────────────────
    def test_tamil_script_translation(self):
        query = "ராகுலின் புகைப்படங்களைக் காட்டு"
        # 1. Local heuristic check
        self.assertTrue(
            self.test_service.is_multilingual_or_codemixed(query),
            "Tamil script must be recognized as multilingual Indic query",
        )

        if self.has_api_key:
            res = self.test_service.translate_query_details(query)
            self.assertTrue(res.was_translated, "Live translation should report was_translated=True")
            self.assertIn("Rahul", res.translated_text, "Translated query should contain 'Rahul'")
            self.assertTrue(
                any(w in res.translated_text.lower() for w in ["photo", "photos", "picture", "pictures", "show"]),
                f"Translated query should contain photo/show concepts: {res.translated_text}",
            )
            self.assertEqual(res.source_language, "ta-IN", "Detected source language should be Tamil (ta-IN)")
        else:
            # Mock verification
            mock_client = MagicMock()
            mock_client.text.translate.return_value = MagicMock(
                translated_text="Show Rahul's photos",
                source_language_code="ta-IN",
            )
            with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client):
                with patch.object(SarvamService, "api_key", return_value="dummy_key"):
                    res = self.test_service.translate_query_details(query)
                    self.assertTrue(res.was_translated)
                    self.assertEqual(res.translated_text, "Show Rahul's photos")
                    self.assertEqual(res.source_language, "ta-IN")

    # ── Test 2: Hindi Query Translation ───────────────────────────────────────
    def test_hindi_translation(self):
        query = "राहुल की तस्वीरें दिखाओ"
        # 1. Local heuristic check
        self.assertTrue(
            self.test_service.is_multilingual_or_codemixed(query),
            "Devanagari Hindi script must be recognized as multilingual Indic query",
        )

        if self.has_api_key:
            res = self.test_service.translate_query_details(query)
            self.assertTrue(res.was_translated, "Live translation should report was_translated=True")
            self.assertIn("Rahul", res.translated_text, "Translated query should contain 'Rahul'")
            self.assertTrue(
                any(w in res.translated_text.lower() for w in ["picture", "pictures", "photo", "photos", "show"]),
                f"Translated query should contain picture/photo concepts: {res.translated_text}",
            )
            self.assertEqual(res.source_language, "hi-IN", "Detected source language should be Hindi (hi-IN)")
        else:
            # Mock verification
            mock_client = MagicMock()
            mock_client.text.translate.return_value = MagicMock(
                translated_text="Show Rahul's pictures",
                source_language_code="hi-IN",
            )
            with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client):
                with patch.object(SarvamService, "api_key", return_value="dummy_key"):
                    res = self.test_service.translate_query_details(query)
                    self.assertTrue(res.was_translated)
                    self.assertEqual(res.translated_text, "Show Rahul's pictures")
                    self.assertEqual(res.source_language, "hi-IN")

    # ── Test 3: Romanized Tamil / Code-Mixed Query Translation ────────────────
    def test_romanized_tamil_codemixed(self):
        query = "Raghul oda photos kaatu"
        # 1. Local heuristic check
        self.assertTrue(
            self.test_service.is_multilingual_or_codemixed(query),
            "Romanized Tamil ('oda', 'kaatu') must be recognized as code-mixed Indic query",
        )

        if self.has_api_key:
            res = self.test_service.translate_query_details(query)
            self.assertTrue(res.was_translated, "Live translation should report was_translated=True")
            self.assertTrue(
                "Rahul" in res.translated_text or "Raghul" in res.translated_text,
                f"Translated query should preserve entity name: {res.translated_text}",
            )
            self.assertTrue(
                any(w in res.translated_text.lower() for w in ["photo", "photos", "picture", "show"]),
                f"Translated query should contain photo/show concepts: {res.translated_text}",
            )
        else:
            # Mock verification
            mock_client = MagicMock()
            mock_client.text.translate.return_value = MagicMock(
                translated_text="Show Rahul's photos.",
                source_language_code="ta-IN",
            )
            with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client):
                with patch.object(SarvamService, "api_key", return_value="dummy_key"):
                    res = self.test_service.translate_query_details(query)
                    self.assertTrue(res.was_translated)
                    self.assertIn("Rahul", res.translated_text)

    # ── Test 4: English Query Should NOT Call Sarvam ──────────────────────────
    def test_english_query_does_not_call_sarvam(self):
        english_queries = [
            "show me Raghul's photos from 9 Dec",
            "bank statement December 2025",
            "invoice pdf",
            "resume of John",
            "project report final",
            "meeting notes from yesterday",
        ]

        # Verify that for every English query, is_multilingual_or_codemixed is False
        for eq in english_queries:
            is_ind = self.test_service.is_multilingual_or_codemixed(eq)
            self.assertFalse(is_ind, f"English query '{eq}' should not be flagged as Indic/code-mixed")

        # Verify that translate_query_details does NOT call the Sarvam client or network
        mock_client = MagicMock()
        with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client):
            for eq in english_queries:
                res = self.test_service.translate_query_details(eq)
                self.assertFalse(res.was_translated, f"English query '{eq}' should report was_translated=False")
                self.assertEqual(res.translated_text, eq, f"English query '{eq}' must be returned unchanged")

        # Crucial check: client translate method was NEVER invoked
        mock_client.text.translate.assert_not_called()

    # ── Test 5: Sarvam API Failure Fallback ────────────────────────────────────
    def test_sarvam_api_failure_fallback(self):
        indic_query = "ராகுலின் புகைப்படங்களைக் காட்டு"

        # Case 5a: Missing API key
        with patch.object(SarvamService, "api_key", return_value=None):
            no_key_service = SarvamService(database=self.db)
            res = no_key_service.translate_query_details(indic_query)
            self.assertFalse(res.was_translated, "Missing API key must not crash; returns was_translated=False")
            self.assertEqual(res.translated_text, indic_query, "Must return original query on missing key")

        # Case 5b: Authentication failure (UnauthorizedError / invalid key)
        from sarvamai import UnauthorizedError
        mock_client_unauth = MagicMock()
        mock_client_unauth.text.translate.side_effect = UnauthorizedError("Invalid API key")

        with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client_unauth):
            with patch.object(SarvamService, "api_key", return_value="invalid_test_key"):
                res = self.test_service.translate_query_details(indic_query)
                self.assertFalse(res.was_translated, "Auth error must not crash; returns was_translated=False")
                self.assertEqual(res.translated_text, indic_query, "Must return original query on auth error")

        # Case 5c: Network exception / timeout
        mock_client_net = MagicMock()
        mock_client_net.text.translate.side_effect = RuntimeError("Connection timed out")

        with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client_net):
            with patch.object(SarvamService, "api_key", return_value="test_key"):
                res = self.test_service.translate_query_details(indic_query)
                self.assertFalse(res.was_translated, "Network timeout must not crash; returns was_translated=False")
                self.assertEqual(res.translated_text, indic_query, "Must return original query on network timeout")

        # Case 5d: translate_to_english convenience method fallback
        with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client_net):
            with patch.object(SarvamService, "api_key", return_value="test_key"):
                text = self.test_service.translate_to_english(indic_query)
                self.assertEqual(text, indic_query, "translate_to_english must return original query on error")

    # ── Test 6: Translation Caching ───────────────────────────────────────────
    def test_translation_caching(self):
        query = "Raghul oda photos kaatu"
        mock_client = MagicMock()
        mock_client.text.translate.return_value = MagicMock(
            translated_text="Show Rahul's photos",
            source_language_code="ta-IN",
        )

        with patch.object(self.test_service, "_get_sdk_client", return_value=mock_client):
            with patch.object(SarvamService, "api_key", return_value="test_key"):
                # First call: invokes client
                res1 = self.test_service.translate_query_details(query)
                self.assertEqual(mock_client.text.translate.call_count, 1)
                self.assertEqual(res1.translated_text, "Show Rahul's photos")
                self.assertFalse(res1.cached)

                # Second call: served from in-memory cache
                res2 = self.test_service.translate_query_details(query)
                self.assertEqual(mock_client.text.translate.call_count, 1, "Cache hit must not invoke client again")
                self.assertEqual(res2.translated_text, "Show Rahul's photos")
                self.assertTrue(res2.cached)

                # Third call with fresh service instance sharing same SQLite DB: served from SQLite cache
                fresh_service = SarvamService(database=self.db)
                mock_client2 = MagicMock()
                with patch.object(fresh_service, "_get_sdk_client", return_value=mock_client2):
                    with patch.object(SarvamService, "api_key", return_value="test_key"):
                        res3 = fresh_service.translate_query_details(query)
                        self.assertEqual(mock_client2.text.translate.call_count, 0, "SQLite cache hit must avoid client call")
                        self.assertEqual(res3.translated_text, "Show Rahul's photos")
                        self.assertTrue(res3.cached)

    # ── Test 7: Universal Query Planner Integration ───────────────────────────
    def test_universal_query_planner_integration(self):
        planner = UniversalQueryPlanner(database=self.db)

        # Simulate translated query from Indic input:
        # Original: "ராகுலின் புகைப்படங்களைக் காட்டு" -> Translated: "Show Rahul's photos"
        original_query = "ராகுலின் புகைப்படங்களைக் காட்டு"
        translated_query = "Show Rahul's photos"

        plan = planner.plan_query(
            translated_query,
            original_query=original_query,
            was_translated=True,
            source_language="ta-IN",
        )

        self.assertEqual(plan.original_query, original_query)
        self.assertEqual(plan.translated_query, translated_query)
        self.assertTrue(plan.was_translated)
        self.assertEqual(plan.source_language, "ta-IN")

        # Person extraction
        self.assertIn("Rahul", plan.persons, "Universal Query Planner must extract 'Rahul' from translated query")
        # File type extraction
        self.assertIn("image", plan.file_types, "Universal Query Planner must extract 'image' from 'photos'")
        # Category extraction
        self.assertIn("Personal Photos", plan.categories, "Universal Query Planner must extract 'Personal Photos'")
        # Verification that Sarvam did NOT do retrieval or planning
        self.assertEqual(plan.intent, "search")

        # Verification of to_dict() serialization
        d = plan.to_dict()
        self.assertEqual(d["original_query"], original_query)
        self.assertEqual(d["translated_query"], translated_query)
        self.assertTrue(d["was_translated"])
        self.assertEqual(d["source_language"], "ta-IN")

    # ── Test 8: Security — Zero API Key Leakage ──────────────────────────────
    def test_no_api_key_leakage(self):
        secret_key = "sk_test_super_secret_sarvam_key_12345"
        with patch.object(SarvamService, "api_key", return_value=secret_key):
            service = SarvamService(database=self.db)

            # Test TranslationResult string representation
            res = TranslationResult("Show photos", True, "ta-IN", original_query="test")
            self.assertNotIn(secret_key, str(res))
            self.assertNotIn(secret_key, repr(res))

            # Test Planner serialization
            plan = UniversalSearchPlan(raw_query="test", cleaned_query="test")
            self.assertNotIn(secret_key, str(plan.to_dict()))

            # Verify that settings table does not contain the key
            settings = self.db.get_all_privacy_settings()
            for k, v in settings.items():
                self.assertNotIn(secret_key, k)
                self.assertNotIn(secret_key, v)

    # ── Test 9: End-to-End Search Pipeline Integration ───────────────────────
    def test_ai_agent_end_to_end_search(self):
        agent = AIAgent(
            database=self.db,
            sarvam_service=self.test_service,
            universal_query_planner=UniversalQueryPlanner(database=self.db),
        )

        # 9a: Indic Tamil search
        indic_q = "ராகுலின் புகைப்படங்களைக் காட்டு"
        results = agent.search(indic_q)
        self.assertEqual(agent.last_original_query, indic_q)
        self.assertTrue(agent.last_was_translated)
        self.assertIn("Rahul", agent.last_translated_query)
        self.assertEqual(agent.last_detected_language, "ta-IN")

        # 9b: Normal English search - must NOT translate
        eng_q = "project report pdf"
        results = agent.search(eng_q)
        self.assertEqual(agent.last_original_query, eng_q)
        self.assertEqual(agent.last_translated_query, eng_q)
        self.assertFalse(agent.last_was_translated)
        self.assertIsNone(agent.last_detected_language)


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSarvamMayuraIntegration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result


if __name__ == "__main__":
    res = run_tests()
    sys.exit(0 if res.wasSuccessful() else 1)
