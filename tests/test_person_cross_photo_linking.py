"""
tests/test_person_cross_photo_linking.py
Verification suite for cross-photo person recognition, auto-linking,
deduplication, and Photo Face Inspector endpoints.
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from fastapi.testclient import TestClient
from intellifile.api.server import app, get_services


class TestPersonCrossPhotoLinking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db, cls.agent = get_services()
        cls.ps = cls.agent.person_service

    def test_01_photo_inspector_metadata_and_norm_boxes(self):
        """Verify GET /api/files/{file_id}/faces returns image dimensions and normalized box coordinates."""
        # File 262 is a verified test group photograph
        res = self.client.get("/api/files/262/faces")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("image_width", data)
        self.assertIn("image_height", data)
        self.assertGreater(data["image_width"], 0)
        self.assertGreater(data["image_height"], 0)
        self.assertIn("faces", data)
        self.assertGreater(len(data["faces"]), 0)

        for f in data["faces"]:
            self.assertIn("norm_x", f)
            self.assertIn("norm_y", f)
            self.assertIn("norm_w", f)
            self.assertIn("norm_h", f)
            self.assertIsNotNone(f["norm_x"])
            self.assertTrue(0.0 <= f["norm_x"] <= 1.0)
            self.assertTrue(0.0 <= f["norm_y"] <= 1.0)
            self.assertTrue(0.0 < f["norm_w"] <= 1.0)
            self.assertTrue(0.0 < f["norm_h"] <= 1.0)

    def test_02_review_queue_filters_missing_disk_files(self):
        """Verify that files deleted or missing from disk never appear in the review queue."""
        res = self.client.get("/api/face-detections/review?limit=100")
        self.assertEqual(res.status_code, 200)
        items = res.json().get("review_queue", [])

        for item in items:
            self.assertTrue(
                Path(item["path"]).is_file(),
                f"Face detection #{item['id']} references missing path on disk: {item['path']}"
            )

    def test_03_duplicate_person_name_auto_merge(self):
        """Verify that creating two person profiles with the same name reuses and merges the profile."""
        p1 = self.db.create_person(name="Unified Test Person", is_cluster=False)
        p2 = self.db.create_person(name="unified test person", is_cluster=False)
        self.assertEqual(p1, p2, "Creating person with existing name must reuse existing person ID")
        self.db.delete_person(p1)

    def test_04_cross_photo_propagation_links_matching_faces(self):
        """
        Verify that creating a person from Face #203 (Aadhar_sai - Copy.jpg)
        automatically links Face #204 (Aadhar_sai.jpg) across different photos.
        """
        # Detection 203 and 204 are twin photos of Sai
        # Create person from detection 203
        create_res = self.client.post(
            "/api/face-detections/203/create-person",
            json={"name": "Auto Link Sai Test"}
        )
        self.assertEqual(create_res.status_code, 200)
        pid = create_res.json()["person_id"]

        try:
            # Check if detection 204 was automatically claimed and linked to pid
            det204 = self.db.get_face_detection_by_id(204)
            self.assertEqual(det204["person_id"], pid, "Det #204 must be automatically linked across photos to Sai")

            # Check files linked to this person
            person_files = self.db.get_person_files(pid)
            file_ids = [f.get("file_id") or f.get("id") for f in person_files]
            self.assertIn(det204["file_id"], file_ids, "Twin file must be automatically linked to Sai's profile")
        finally:
            self.db.delete_person(pid)

    def test_05_confirm_all_endpoint(self):
        """Verify POST /api/face-detections/confirm-all runs library propagation cleanly."""
        res = self.client.post("/api/face-detections/confirm-all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
