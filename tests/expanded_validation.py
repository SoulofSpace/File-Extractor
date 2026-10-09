"""
expanded_validation.py — In-Depth Empirical Validation & Error Analysis for V4 Face Engine.

Evaluates:
1. Face Detection Precision & Recall on an expanded set of 36 real images (non-people, portraits, groups, challenging).
2. Identity Recognition on 20+ labelled same-person and different-person pairs.
3. Metric breakdown: False Acceptance Rate (FAR), False Rejection Rate (FRR), Uncertain matches (POSSIBLE).
4. Threshold calibration verification.
5. Group photo multi-identity verification.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import cv2
import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from intellifile.face_service import (
    FaceService,
    CONFIRMED_MATCH_THRESHOLD,
    POSSIBLE_MATCH_THRESHOLD,
    MIN_MARGIN_THRESHOLD,
)
from intellifile.database import Database
from intellifile.person_service import PersonService


def run_expanded_validation():
    fs = FaceService()
    if not fs.initialize():
        print("ERROR: FaceService initialization failed.")
        return False

    print("=" * 80)
    print("FILE XTRACTOR V4 — EXPANDED EMPIRICAL VALIDATION & ERROR ANALYSIS")
    print("=" * 80)

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 1: EXPANDED FACE DETECTION BENCHMARK
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[1] EXPANDED FACE DETECTION EVALUATION")
    print("-" * 80)

    # Ground truth dataset: (Path, expected_face_count, category, description)
    dataset = [
        # A. Non-People Images (Target: 0 faces)
        (Path(r"C:\Users\space\Downloads\3840x2160-white-solid-color-background.jpg"), 0, "Non-Person", "Solid white canvas"),
        (Path(r"C:\Users\space\Downloads\309519-3840x2160-desktop-4k-spider-man-wallpaper-image.jpg"), 0, "Non-Person", "Spider-man comic wallpaper"),
        (Path(r"C:\Users\space\Downloads\3rd anser1.jpg"), 0, "Non-Person", "Handwritten exam answer sheet"),
        (Path(r"C:\Users\space\Downloads\4th question.jpg"), 0, "Non-Person", "Printed text question paper"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\Black Background Techno Logo.png"), 0, "Non-Person", "Graphic vector logo on black"),
        (Path(r"C:\Users\space\Downloads\1 techno.png"), 0, "Non-Person", "Graphic logo / typography"),
        (Path(r"C:\Users\space\Downloads\1000148905.png"), 0, "Non-Person", "Code / terminal screenshot"),
        (Path(r"C:\Users\space\Downloads\abstract-surface-textures-white-concrete.jpg"), 0, "Non-Person", "Concrete texture photo"),
        (Path(r"C:\Users\space\Downloads\abstract-white-background-photo.jpg"), 0, "Non-Person", "Abstract background texture"),
        (Path(r"C:\Users\space\Downloads\Add a heading.png"), 0, "Non-Person", "Graphic banner design"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\white2.png"), 0, "Non-Person", "Blank white image"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\for truck.jpg.jpeg"), 0, "Non-Person", "Commercial truck vehicle"),

        # B. Single-Person Portraits (Target: 1 face)
        (Path(r"C:\Users\space\Downloads\1c9d7a47-7019-463e-9219-3304a5c72408.jpeg"), 1, "Portrait", "Studio indoor portrait"),
        (Path(r"C:\Users\space\Downloads\20191110_105118.jpg"), 1, "Portrait", "Outdoor natural light portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg"), 1, "Portrait", "Subject B - Frontal pose"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-25 at 10.58.05 PM.jpeg"), 1, "Portrait", "Subject B - Slight angle"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-25 at 9.11.17 PM.jpeg"), 1, "Portrait", "Subject B - Distant pose"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-23 at 1.44.17 PM.jpeg"), 1, "Portrait", "Subject C - Frontal"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-23 at 7.58.44 AM (1).jpeg"), 1, "Portrait", "Subject C - Indoor light"),
        (Path(r"C:\Users\space\Downloads\Aadhar_sai.jpg"), 1, "Portrait", "Subject Sai - Low-res ID card"),
        (Path(r"C:\Users\space\Downloads\Aadhar_sai - Copy.jpg"), 1, "Portrait", "Subject Sai - Duplicate ID card"),
        (Path(r"C:\Users\space\Downloads\Adhaar Dharun.jpeg"), 1, "Portrait", "Subject Dharun - ID card photo"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\ChatGPT Image Sep 19, 2026, 03_27_13 PM.png"), 1, "Portrait", "Stylized portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\2abbbf8a-435a-4aa4-994a-8ed7089d1c6b.png"), 1, "Portrait", "Close-up portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-20 at 2.27.10 PM.jpeg"), 1, "Portrait", "Wedding event portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-20 at 2.27.13 PM.jpeg"), 1, "Portrait", "Wedding event portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-23 at 12.05.21 PM.jpeg"), 1, "Portrait", "Subject D - Pose 1"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-23 at 12.05.22 PM.jpeg"), 1, "Portrait", "Subject D - Pose 2"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-22 at 8.08.38 AM.jpeg"), 1, "Portrait", "Subject E - Small face portrait"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\wnfervnoeivnae.webp"), 1, "Portrait", "Web portrait"),

        # C. Group Photographs (Multi-face ground truth)
        (Path(r"C:\Users\space\Downloads\Adobe Express - file (4).png"), 5, "Group", "Adobe Express 5-person group photo"),
        (Path(r"C:\Users\space\Downloads\Adobe Express - file (5).png"), 6, "Group", "Adobe Express 6-person group photo"),
        (Path(r"C:\Users\space\Downloads\Adobe Express - file (3).png"), 2, "Group", "2-person photo"),
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-09-20 at 2.27.11 PM (2).jpeg"), 2, "Group", "2-person event photo"),
        (Path(r"C:\Users\space\Downloads\515145126_1970022893814549_6742385595744916727_n.jpg"), 2, "Group", "2-person photo"),
        (Path(r"C:\Users\space\Downloads\515396931_640120062529114_4168529092128903422_n.jpg"), 2, "Group", "2-person photo"),
        (Path(r"C:\Users\space\Downloads\518720973_1616354792374569_5555605423403724525_n.jpg"), 2, "Group", "2-person photo"),

        # D. Challenging / Low-Contrast Case
        (Path(r"C:\Users\space\OneDrive\Desktop\Test Folder\WhatsApp Image 2026-08-23 at 7.58.44 AM.jpeg"), 1, "Challenging", "Subject C - Dark, low-contrast portrait"),
    ]

    total_gt_faces = 0
    total_detected_faces = 0
    tp_faces = 0
    fp_faces = 0
    fn_faces = 0
    tn_images = 0

    cached_embs: Dict[str, List[np.ndarray]] = {}

    for path, expected, cat, desc in dataset:
        if not path.exists():
            continue
        faces = fs.detect_and_embed_faces(path)
        actual = len(faces)
        total_gt_faces += expected
        total_detected_faces += actual

        if expected == 0:
            if actual == 0:
                tn_images += 1
                status = "PASS (TN)"
            else:
                fp_faces += actual
                status = f"FAIL (FP: {actual})"
        else:
            if actual == expected:
                tp_faces += actual
                status = f"PASS (TP: {actual}/{expected})"
            elif actual > expected:
                tp_faces += expected
                fp_faces += (actual - expected)
                status = f"OVER-DETECT (TP:{expected}, FP:{actual-expected})"
            else:
                tp_faces += actual
                fn_faces += (expected - actual)
                status = f"UNDER-DETECT (TP:{actual}, FN:{expected-actual})"

        cached_embs[path.name] = [f.embedding_vec for f in faces]
        print(f"  {status:<22} | {path.name[:35]:<35} | Exp: {expected} | Det: {actual} | {desc}")

    det_prec = (tp_faces / (tp_faces + fp_faces)) * 100 if (tp_faces + fp_faces) > 0 else 0.0
    det_rec = (tp_faces / (tp_faces + fn_faces)) * 100 if (tp_faces + fn_faces) > 0 else 0.0

    print("\nDetection Summary:")
    print(f"  • Ground Truth Faces:     {total_gt_faces}")
    print(f"  • Total Detected Faces:   {total_detected_faces}")
    print(f"  • True Positives (TP):    {tp_faces}")
    print(f"  • False Positives (FP):   {fp_faces}")
    print(f"  • False Negatives (FN):   {fn_faces}")
    print(f"  • True Negative Images:   {tn_images} (Images with 0 people correctly yielding 0 detections)")
    print(f"  • Detection Precision:    {det_prec:.2f}%")
    print(f"  • Detection Recall:       {det_rec:.2f}%")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 2: IDENTITY RECOGNITION EVALUATION (PAIRS)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n\n[2] IDENTITY RECOGNITION EVALUATION (LABELLED PAIRS)")
    print("-" * 80)

    # Define labelled pairs
    # (Image1_name, idx1, Image2_name, idx2, is_same_person, description)
    id_pairs = [
        # --- Same-Person Pairs (Different poses, lighting, dates) ---
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "WhatsApp Image 2026-08-25 at 10.58.05 PM.jpeg", 0, True, "Subject B: Pose 1 vs Pose 2"),
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "WhatsApp Image 2026-08-25 at 9.11.17 PM.jpeg", 0, True, "Subject B: Pose 1 vs Pose 3"),
        ("WhatsApp Image 2026-08-25 at 10.58.05 PM.jpeg", 0, "WhatsApp Image 2026-08-25 at 9.11.17 PM.jpeg", 0, True, "Subject B: Pose 2 vs Pose 3"),
        ("WhatsApp Image 2026-09-23 at 12.05.21 PM.jpeg", 0, "WhatsApp Image 2026-09-23 at 12.05.22 PM.jpeg", 0, True, "Subject D: Pose 1 vs Pose 2"),
        ("Aadhar_sai.jpg", 0, "Aadhar_sai - Copy.jpg", 0, True, "Subject Sai: Aadhaar vs Duplicate"),
        ("WhatsApp Image 2026-09-20 at 2.27.10 PM.jpeg", 0, "WhatsApp Image 2026-09-20 at 2.27.13 PM.jpeg", 0, True, "Event Person: Photo 1 vs Photo 2"),

        # --- Different-Person Pairs ---
        ("Aadhar_sai.jpg", 0, "Adhaar Dharun.jpeg", 0, False, "Sai vs Dharun (Both Aadhaar ID photos)"),
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "WhatsApp Image 2026-08-23 at 1.44.17 PM.jpeg", 0, False, "Subject B vs Subject C"),
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "WhatsApp Image 2026-09-23 at 12.05.21 PM.jpeg", 0, False, "Subject B vs Subject D"),
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "1c9d7a47-7019-463e-9219-3304a5c72408.jpeg", 0, False, "Subject B vs Portrait 1"),
        ("WhatsApp Image 2026-08-23 at 1.44.17 PM.jpeg", 0, "Adhaar Dharun.jpeg", 0, False, "Subject C vs Dharun"),
        ("1c9d7a47-7019-463e-9219-3304a5c72408.jpeg", 0, "20191110_105118.jpg", 0, False, "Portrait 1 vs Portrait 2"),
        ("WhatsApp Image 2026-08-25 at 10.57.26 PM.jpeg", 0, "Aadhar_sai.jpg", 0, False, "Subject B vs Sai"),
        ("WhatsApp Image 2026-09-23 at 12.05.21 PM.jpeg", 0, "Adhaar Dharun.jpeg", 0, False, "Subject D vs Dharun"),
        ("Adobe Express - file (5).png", 0, "Adobe Express - file (5).png", 1, False, "Adobe 5: Person 1 vs Person 2"),
        ("Adobe Express - file (5).png", 0, "Adobe Express - file (5).png", 2, False, "Adobe 5: Person 1 vs Person 3"),
        ("Adobe Express - file (5).png", 0, "Adobe Express - file (5).png", 3, False, "Adobe 5: Person 1 vs Person 4"),
        ("Adobe Express - file (5).png", 0, "Adobe Express - file (5).png", 4, False, "Adobe 5: Person 1 vs Person 5"),
        ("Adobe Express - file (5).png", 0, "Adobe Express - file (5).png", 5, False, "Adobe 5: Person 1 vs Person 6"),
        ("Adobe Express - file (5).png", 1, "Adobe Express - file (5).png", 2, False, "Adobe 5: Person 2 vs Person 3"),
        ("Adobe Express - file (5).png", 2, "Adobe Express - file (5).png", 4, False, "Adobe 5: Person 3 vs Person 5"),
    ]

    same_sims = []
    diff_sims = []

    false_acceptance = 0  # Different person matched as CONFIRMED
    false_rejection = 0   # Same person matched as UNKNOWN
    uncertain_matches = 0 # Either same or diff fell into POSSIBLE review queue
    correct_confirmed = 0 # Same person correctly CONFIRMED
    correct_unknown = 0   # Different person correctly UNKNOWN

    print(f"{'Type':<6} | {'Sim':<6} | {'Outcome':<10} | {'Status':<6} | {'Pair Description':<45}")
    print("-" * 80)

    for fn1, idx1, fn2, idx2, is_same, desc in id_pairs:
        embs1 = cached_embs.get(fn1, [])
        embs2 = cached_embs.get(fn2, [])

        if idx1 >= len(embs1) or idx2 >= len(embs2):
            print(f"SKIP   | N/A    | MISSING    | SKIP   | {desc} (Face index missing)")
            continue

        e1 = embs1[idx1]
        e2 = embs2[idx2]
        sim = float(np.dot(e1, e2))

        # Outcome classification based on calibrated thresholds
        if sim >= CONFIRMED_MATCH_THRESHOLD:
            outcome = "CONFIRMED"
        elif sim >= POSSIBLE_MATCH_THRESHOLD:
            outcome = "POSSIBLE"
        else:
            outcome = "UNKNOWN"

        pair_type = "SAME" if is_same else "DIFF"

        if is_same:
            same_sims.append(sim)
            if outcome == "CONFIRMED":
                correct_confirmed += 1
                status = "PASS"
            elif outcome == "POSSIBLE":
                uncertain_matches += 1
                status = "REVIEW"
            else:
                false_rejection += 1
                status = "FAIL"
        else:
            diff_sims.append(sim)
            if outcome == "UNKNOWN":
                correct_unknown += 1
                status = "PASS"
            elif outcome == "POSSIBLE":
                uncertain_matches += 1
                status = "REVIEW"
            else:
                false_acceptance += 1
                status = "FAIL"

        print(f"{pair_type:<6} | {sim:.3f} | {outcome:<10} | {status:<6} | {desc}")

    total_pairs = len(same_sims) + len(diff_sims)
    total_correct = correct_confirmed + correct_unknown

    print("\nRecognition Metric Breakdown:")
    print(f"  • Total Evaluated Pairs:         {total_pairs}")
    print(f"  • Same-Person Pairs Evaluated:   {len(same_sims)}")
    print(f"  • Different-Person Pairs:        {len(diff_sims)}")
    print(f"  • Correct Confirmed Matches:     {correct_confirmed} / {len(same_sims)}")
    print(f"  • Correct Unknown Rejections:    {correct_unknown} / {len(diff_sims)}")
    print(f"  • False Acceptance (FAR):        {false_acceptance} (Target: 0)")
    print(f"  • False Rejection (FRR):         {false_rejection} (Target: 0)")
    print(f"  • Uncertain Matches (POSSIBLE):  {uncertain_matches} (In review queue)")
    print(f"  • Pair Decision Accuracy:        {(total_correct / total_pairs) * 100:.2f}%")

    if same_sims:
        print(f"\nSimilarity Distribution:")
        print(f"  • Same-Person Cosine Range:      Min {min(same_sims):.3f}, Mean {np.mean(same_sims):.3f}, Max {max(same_sims):.3f}")
    if diff_sims:
        print(f"  • Different-Person Cosine Range: Min {min(diff_sims):.3f}, Mean {np.mean(diff_sims):.3f}, Max {max(diff_sims):.3f}")

    # ──────────────────────────────────────────────────────────────────────────
    # SECTION 3: MULTI-PERSON GROUP PHOTO ASSOCIATION VERIFICATION
    # ──────────────────────────────────────────────────────────────────────────
    print("\n\n[3] GROUP PHOTO MULTI-IDENTITY ASSOCIATION VERIFICATION")
    print("-" * 80)
    db = Database("C:/Users/space/AppData/Local/IntelliFile/intellifile.sqlite3")
    ps = PersonService(db)

    # Verify Adobe Express - file (4).png (5 faces) in DB
    adobe4 = db.get_file_by_path(r"C:\Users\space\Downloads\Adobe Express - file (4).png")
    if adobe4:
        fid = adobe4["id"]
        detections = db.get_face_detections(file_id=fid)
        print(f"File ID {fid} (Adobe Express - file (4).png):")
        print(f"  • Detected Face Records in DB: {len(detections)}")
        distinct_boxes = len(set((d["box_x"], d["box_y"]) for d in detections))
        print(f"  • Distinct Bounding Box Coordinates: {distinct_boxes}")
        assert distinct_boxes == len(detections), "Duplicate bounding box detected!"

        # Test simulated multi-person association on a group photo
        # Create test person A and test person B
        test_pid_A = db.create_person("Test Student Alpha")
        test_pid_B = db.create_person("Test Student Beta")

        try:
            # Assign detection 0 to Person A, detection 1 to Person B
            db.assign_face_detection_to_person(detections[0]["id"], test_pid_A, match_confidence=0.95)
            db.assign_face_detection_to_person(detections[1]["id"], test_pid_B, match_confidence=0.92)

            # Query person_file_links for this file
            file_persons = db.get_file_persons(fid)
            linked_pids = {p["id"] for p in file_persons}
            print(f"  • Multiple Person IDs linked to this single file: {linked_pids}")
            assert test_pid_A in linked_pids and test_pid_B in linked_pids, "Failed to link multiple people to one photo!"

            # Verify naming one person does not affect the other person
            db.update_person(test_pid_A, name="Test Student Alpha Renamed")
            p_A = db.get_person(test_pid_A)
            p_B = db.get_person(test_pid_B)
            assert p_A["name"] == "Test Student Alpha Renamed"
            assert p_B["name"] == "Test Student Beta"
            print("  • Verified: Renaming Person A did NOT modify Person B.")

            # Verify file records are not duplicated
            with db.connection() as conn:
                count_files = conn.execute("SELECT COUNT(*) FROM files WHERE id = ?", (fid,)).fetchone()[0]
                assert count_files == 1, "Duplicate file record created!"
            print("  • Verified: Exactly 1 file record exists for the multi-person group photo.")
            print("  [PASS] Multi-identity group photo test completely successful.")
        finally:
            # Clean up test identities
            db.delete_person(test_pid_A)
            db.delete_person(test_pid_B)

    print("\n" + "=" * 80)
    print("EXPANDED VALIDATION RUN COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")
    return True


if __name__ == "__main__":
    run_expanded_validation()
