"""
tests/test_persons_frontend_workflow.py
Verification suite for Persons frontend workflow endpoints and group photo isolation.
Tests real SQLite records and live local endpoints.
"""

import sys
import unittest
from pathlib import Path

# Add src to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from fastapi.testclient import TestClient
from intellifile.api.server import app, get_services


class TestPersonsFrontendWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db, cls.agent = get_services()
        cls.ps = cls.agent.person_service

    def test_01_face_review_queue_endpoint(self):
        """Verify GET /api/face-detections/review returns actual detected faces."""
        response = self.client.get("/api/face-detections/review?limit=50")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("review_queue", data)
        queue = data["review_queue"]
        self.assertIsInstance(queue, list)
        self.assertGreater(len(queue), 0, "Review queue should contain detected faces needing review")

        first = queue[0]
        self.assertIn("id", first)
        self.assertIn("file_id", first)
        self.assertIn("filename", first)
        self.assertIn("box", first)
        self.assertEqual(len(first["box"]), 4)
        self.assertIn("confidence", first)
        self.assertIn("face_quality", first)
        print(f"Review queue verified: {len(queue)} items. Sample: Face #{first['id']} in {first['filename']}")

    def test_02_face_crop_streaming(self):
        """Verify GET /api/face-detections/{id}/crop streams valid JPEG bytes."""
        queue_res = self.client.get("/api/face-detections/review?limit=5")
        first_det_id = queue_res.json()["review_queue"][0]["id"]

        crop_res = self.client.get(f"/api/face-detections/{first_det_id}/crop")
        self.assertEqual(crop_res.status_code, 200)
        self.assertEqual(crop_res.headers["content-type"], "image/jpeg")
        crop_bytes = crop_res.content
        self.assertGreater(len(crop_bytes), 100)
        # Check JPEG magic header
        self.assertTrue(crop_bytes.startswith(b"\xff\xd8\xff"), "Face crop must be valid JPEG image bytes")
        print(f"Face crop verified: {len(crop_bytes)} bytes streamed for detection #{first_det_id}")

    def test_03_get_file_faces_for_group_photo(self):
        """Verify GET /api/files/{file_id}/faces returns all detected faces for group photos."""
        # Find a file with multiple faces
        with self.db.connection() as conn:
            row = conn.execute("""
                SELECT file_id, COUNT(*) as cnt 
                FROM face_detections 
                GROUP BY file_id 
                HAVING cnt >= 2 
                ORDER BY cnt DESC 
                LIMIT 1
            """).fetchone()

        self.assertIsNotNone(row, "Should find at least one group photo in test database")
        group_file_id = row[0]
        face_count = row[1]

        res = self.client.get(f"/api/files/{group_file_id}/faces")
        self.assertEqual(res.status_code, 200)
        faces = res.json()["faces"]
        self.assertEqual(len(faces), face_count)

        det_ids = [f["id"] for f in faces]
        self.assertEqual(len(det_ids), len(set(det_ids)), "All face detection IDs must be unique")
        print(f"Group photo file #{group_file_id} faces verified: {len(faces)} independent faces")

    def test_04_group_photo_isolation_create_person(self):
        """
        Verify that creating a person from Face A in a group photo:
        1. Associates ONLY Face A with the new person
        2. Leaves Face B and other faces completely independent and unaltered
        """
        with self.db.connection() as conn:
            rows = conn.execute("""
                SELECT id, file_id FROM face_detections 
                WHERE file_id IN (
                    SELECT file_id FROM face_detections GROUP BY file_id HAVING COUNT(*) >= 3
                )
                LIMIT 3
            """).fetchall()

        self.assertGreaterEqual(len(rows), 2)
        face_a_id = rows[0]["id"]
        face_b_id = rows[1]["id"]
        self.assertNotEqual(face_a_id, face_b_id)

        # Get initial state of Face B
        face_b_initial = self.db.get_face_detection_by_id(face_b_id)

        # Create new person strictly from Face A
        test_name = f"Test Isolation Person {face_a_id}"
        create_res = self.client.post(
            f"/api/face-detections/{face_a_id}/create-person",
            json={"name": test_name, "aliases": ["IsolatedTest"], "notes": "Testing isolation"}
        )
        self.assertEqual(create_res.status_code, 200)
        person_id = create_res.json()["person_id"]

        # Verify Face A was updated
        face_a_after = self.db.get_face_detection_by_id(face_a_id)
        self.assertEqual(face_a_after["person_id"], person_id)

        # CRITICAL ASSERTION: Face B must NOT have been changed or assigned to Face A's person!
        face_b_after = self.db.get_face_detection_by_id(face_b_id)
        self.assertEqual(face_b_after["person_id"], face_b_initial["person_id"],
                         "Naming Face A must NEVER rename or reassign Face B in the same image!")

        print(f"Group photo isolation confirmed: Face #{face_a_id} enrolled as '{test_name}', Face #{face_b_id} untouched")

    def test_05_confirm_and_reject_actions(self):
        """Verify Confirm and Reject actions on candidate matches."""
        # Create a test person
        test_person_id = self.db.create_person(name="Test Confirm Person", is_cluster=False)

        # Pick an unassigned face detection
        unassigned = self.db.get_unassigned_face_detections(limit=1)
        self.assertGreater(len(unassigned), 0)
        target_det_id = unassigned[0]["id"]

        # 1. Assign to test person
        assign_res = self.client.post(f"/api/face-detections/{target_det_id}/assign?person_id={test_person_id}")
        self.assertEqual(assign_res.status_code, 200)

        # 2. Confirm match
        confirm_res = self.client.post(f"/api/face-detections/{target_det_id}/confirm")
        self.assertEqual(confirm_res.status_code, 200)
        det_after_confirm = self.db.get_face_detection_by_id(target_det_id)
        self.assertEqual(det_after_confirm["person_id"], test_person_id)
        self.assertEqual(det_after_confirm["match_confidence"], 1.0)

        # 3. Reject match
        reject_res = self.client.post(f"/api/face-detections/{target_det_id}/reject")
        self.assertEqual(reject_res.status_code, 200)
        det_after_reject = self.db.get_face_detection_by_id(target_det_id)
        self.assertIsNone(det_after_reject["person_id"], "Rejected match must return face to unassigned status")

        # Clean up test person
        self.db.delete_person(test_person_id)
        print(f"Confirm & Reject workflow verified cleanly on Face #{target_det_id}")

    def test_06_add_reference_photo_to_existing_person(self):
        """Verify adding multiple reference photos / embeddings to an existing person profile."""
        person_id = self.db.create_person(name="Multi Ref Test Person", is_cluster=False)

        # Count initial embeddings
        initial_embs = [
            e for e in self.db.get_all_person_embeddings() if e["person_id"] == person_id
        ]
        self.assertEqual(len(initial_embs), 0)

        # Add from an existing face detection
        detections = self.db.get_face_detections()
        valid_det = next(d for d in detections if d.get("embedding"))

        add_res = self.client.post(
            f"/api/persons/{person_id}/reference-photos",
            json={"detection_id": valid_det["id"]}
        )
        self.assertEqual(add_res.status_code, 200)

        # Check embeddings count increased
        updated_embs = [
            e for e in self.db.get_all_person_embeddings() if e["person_id"] == person_id
        ]
        self.assertGreaterEqual(len(updated_embs), 1)
        self.assertEqual(updated_embs[0]["is_reference"], 1)

        # Clean up
        self.db.delete_person(person_id)
        print(f"Multi-reference photo addition verified for person profile #{person_id}")

    def test_07_confirm_unassigned_face_with_direct_person_id(self):
        """Verify confirming an unassigned face directly with person_id (fixing previous 'no assigned identity' error)."""
        person_id = self.db.create_person(name="Direct Confirm Test Person", is_cluster=False)

        # Pick an unassigned face detection
        unassigned = self.db.get_unassigned_face_detections(limit=1)
        self.assertGreater(len(unassigned), 0)
        target_det_id = unassigned[0]["id"]

        # Confirm directly with person_id query param
        confirm_res = self.client.post(f"/api/face-detections/{target_det_id}/confirm?person_id={person_id}")
        self.assertEqual(confirm_res.status_code, 200)
        res_json = confirm_res.json()
        self.assertEqual(res_json["status"], "confirmed")
        self.assertEqual(res_json["person_id"], person_id)

        # Verify DB state
        det = self.db.get_face_detection_by_id(target_det_id)
        self.assertEqual(det["person_id"], person_id)
        self.assertEqual(det["match_confidence"], 1.0)

        # Revert/clean up
        with self.db.connection() as conn:
            conn.execute("UPDATE face_detections SET person_id = NULL, match_confidence = NULL WHERE id = ?", (target_det_id,))
        self.db.delete_person(person_id)
        print(f"Direct confirmation of unassigned Face #{target_det_id} verified cleanly")


if __name__ == "__main__":
    unittest.main()
