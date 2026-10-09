"""
person_service.py — V4 Person Management & Entity Linking Service for FILE XTRACTOR.
Coordinates local face detection, identity matching, unknown face clustering,
and multi-signal person-file linking (Face, OCR, Filename, Entity).
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

from .database import Database
from .face_service import (
    FaceService,
    DetectedFace,
    CONFIRMED_MATCH_THRESHOLD,
    POSSIBLE_MATCH_THRESHOLD,
    MIN_MARGIN_THRESHOLD,
)


class PersonService:
    """
    Manages Person profiles, aliases, face embeddings, unknown face clusters,
    and multi-signal file associations.
    """

    def __init__(self, database: Database, face_service: Optional[FaceService] = None) -> None:
        self.database = database
        self.face_service = face_service or FaceService()

    @property
    def is_face_indexing_enabled(self) -> bool:
        setting = self.database.get_privacy_setting("face_indexing_enabled", "1")
        return str(setting).strip() in ("1", "true", "True", "on", "ON")

    def create_person(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        reference_image_paths: Optional[List[Path | str]] = None,
        notes: str = "",
    ) -> int:
        return self.create_person_with_photos(
            name=name,
            aliases=aliases,
            reference_image_paths=reference_image_paths,
            notes=notes,
        )

    def create_person_with_photos(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        reference_image_paths: Optional[List[Path | str]] = None,
        notes: str = "",
    ) -> int:
        """
        Creates a new Person profile with multiple reference photos (Requirement 2 & 6).
        Extracts local face embeddings from reference photos.
        Prevents accidentally enrolling all faces in a group photo.
        """
        person_id = self.database.create_person(
            name=name,
            aliases=aliases,
            notes=notes,
            is_cluster=False,
        )

        avatar_file_id: Optional[int] = None

        if reference_image_paths:
            for img_p in reference_image_paths:
                p = Path(img_p).resolve()
                if not p.is_file():
                    continue

                f_rec = self.database.get_file_by_path(str(p))
                file_id = f_rec["id"] if f_rec else None

                faces = self.face_service.detect_and_embed_faces(p)
                if not faces:
                    logger.warning("No face detected in reference photo: %s", p.name)
                    continue

                # Group photo protection: If multiple faces are detected in a reference photo,
                # only select the primary/dominant face if it is significantly larger and central.
                # Never enrol every face in a group photo as the same person!
                chosen_face: Optional[DetectedFace] = None
                if len(faces) == 1:
                    chosen_face = faces[0]
                else:
                    sorted_by_area = sorted(faces, key=lambda f: f.box_w * f.box_h, reverse=True)
                    largest_area = sorted_by_area[0].box_w * sorted_by_area[0].box_h
                    second_area = sorted_by_area[1].box_w * sorted_by_area[1].box_h
                    # Dominant check: largest face must be >= 2.0x larger than second face
                    if largest_area >= 2.0 * second_area and sorted_by_area[0].face_quality >= 0.45:
                        chosen_face = sorted_by_area[0]
                        logger.info(
                            "Selected dominant face in reference photo %s for person %s",
                            p.name, name
                        )
                    else:
                        logger.warning(
                            "Multiple comparable faces detected in reference photo %s. Skipping ambiguous auto-enrolment.",
                            p.name
                        )
                        continue

                if chosen_face and chosen_face.face_quality >= 0.35:
                    if avatar_file_id is None and file_id:
                        avatar_file_id = file_id

                    # Store approved reference face embedding
                    self.database.add_person_embedding(
                        person_id=person_id,
                        embedding=chosen_face.embedding,
                        source_file_id=file_id,
                        is_reference=True,
                    )

                    # Link file to person as confirmed reference
                    if file_id:
                        self.database.link_person_to_file(
                            person_id=person_id,
                            file_id=file_id,
                            link_type="face",
                            confidence=1.0,
                            is_confirmed=True,
                            notes="Reference photo",
                        )

                        # Record face detection with person_id
                        self.database.add_face_detection(
                            file_id=file_id,
                            box_x=chosen_face.box_x,
                            box_y=chosen_face.box_y,
                            box_w=chosen_face.box_w,
                            box_h=chosen_face.box_h,
                            confidence=chosen_face.confidence,
                            embedding=chosen_face.embedding,
                            person_id=person_id,
                            match_confidence=1.0,
                            face_quality=chosen_face.face_quality,
                            landmarks=chosen_face.landmarks,
                        )

        if avatar_file_id:
            self.database.update_person(person_id, avatar_file_id=avatar_file_id)

        self.propagate_and_link_known_persons(person_id)

        return person_id

    def list_persons(self, include_clusters: bool = True, privacy_scope: str = "NORMAL") -> List[dict]:
        """Returns all known persons and unknown face clusters respecting privacy scope (Requirement 32)."""
        return self.database.list_persons(include_clusters=include_clusters, privacy_scope=privacy_scope)

    def get_person_details(self, person_id: int, privacy_scope: str = "NORMAL") -> Optional[dict]:
        p = self.database.get_person(person_id)
        if not p:
            return None
        files = self.database.get_person_files(person_id, privacy_scope=privacy_scope)
        p["files"] = files
        p["photo_count"] = sum(1 for f in files if f.get("link_type") == "face")
        p["doc_count"] = sum(1 for f in files if f.get("link_type") in ("ocr", "filename", "entity"))
        return p

    def rename_person(self, person_id: int, new_name: str) -> None:
        self.database.update_person(person_id, name=new_name.strip())

    def add_alias(self, person_id: int, alias: str) -> None:
        self.database.add_person_alias(person_id, alias.strip())

    def remove_alias(self, person_id: int, alias: str) -> None:
        self.database.remove_person_alias(person_id, alias.strip())

    def delete_person(self, person_id: int) -> None:
        """Requirement 40: Deleting identity removes profiles, embeddings, and links; does NOT delete files."""
        self.database.delete_person(person_id)

    def merge_persons(self, source_person_id: int, target_person_id: int) -> None:
        """Requirement 10: Merges source person into target person."""
        self.database.merge_persons(source_person_id, target_person_id)

    def split_person(
        self,
        person_id: int,
        new_person_name: str,
        detection_ids: Optional[List[int]] = None,
        file_ids: Optional[List[int]] = None,
    ) -> int:
        """Requirement 10: Splits selected detections or files into a new person."""
        return self.database.split_person(person_id, new_person_name, detection_ids, file_ids)

    def name_cluster(self, cluster_id: int, person_name: str) -> int:
        """Requirement 9: Names an unknown face cluster into an approved person and propagates across photos."""
        pid = self.database.name_cluster(cluster_id, person_name.strip())
        self.propagate_and_link_known_persons(pid)
        return pid

    def process_file_faces_and_entities(
        self,
        file_id: int,
        file_path: Path | str,
        ocr_text: str = "",
        document_text: str = "",
    ) -> List[dict]:
        """
        Executes face detection & multi-signal entity linking for an indexed file (Requirements 1, 3, 4).
        - Images with zero detected faces create zero face records.
        - Multiple faces in group photos create independent records.
        - Matched faces are assigned to known people.
        - Unmatched faces are left unassigned (person_id = None), NOT creating empty person profiles.
        """
        p = Path(file_path).resolve()
        linked_associations: List[dict] = []

        # ── 1. Face Recognition Pipeline (Images only, when enabled) ───────────
        if self.is_face_indexing_enabled and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            try:
                faces = self.face_service.detect_and_embed_faces(p)
                if faces:
                    # Pre-load known person reference embeddings
                    known_raw = self.database.get_all_person_embeddings()
                    known_list: List[Tuple[int, np.ndarray, bool]] = []
                    for k in known_raw:
                        vec = np.frombuffer(k["embedding"], dtype=np.float32)
                        known_list.append((k["person_id"], vec, bool(k.get("is_reference", 1))))

                    for face in faces:
                        matched_pid, sim, grade = self.face_service.match_against_known_persons(
                            face.embedding_vec, known_list
                        )

                        target_pid = matched_pid if grade in ("CONFIRMED", "POSSIBLE") else None
                        is_confirmed = (grade == "CONFIRMED")

                        # Record face detection in DB
                        det_id = self.database.add_face_detection(
                            file_id=file_id,
                            box_x=face.box_x,
                            box_y=face.box_y,
                            box_w=face.box_w,
                            box_h=face.box_h,
                            confidence=face.confidence,
                            embedding=face.embedding,
                            person_id=target_pid,
                            match_confidence=sim if target_pid else None,
                            face_quality=face.face_quality,
                            landmarks=face.landmarks,
                        )

                        # Only link file to person if a match was found
                        if target_pid:
                            self.database.link_person_to_file(
                                person_id=target_pid,
                                file_id=file_id,
                                link_type="face",
                                confidence=sim,
                                is_confirmed=is_confirmed,
                                notes=f"Face match ({grade}, {sim:.2f})",
                            )

                            linked_associations.append({
                                "person_id": target_pid,
                                "type": "face",
                                "confidence": sim,
                                "grade": grade,
                                "box": [face.box_x, face.box_y, face.box_w, face.box_h],
                            })
            except Exception as face_err:
                logger.debug("Face processing skipped for %s: %s", p.name, face_err)

        # ── 2. Text / OCR / Filename Person Mention Linking (Requirement 12) ──
        all_text = f"{p.name} {ocr_text or ''} {document_text or ''}".lower()
        if all_text.strip():
            try:
                known_persons = self.database.list_persons(include_clusters=False)
                for kp in known_persons:
                    kp_name = kp["name"].strip()
                    if not kp_name or len(kp_name) < 3:
                        continue

                    # Whole-word regex matching to prevent false substring matches (e.g. 'arun' in 'dharun')
                    patterns = [kp_name.lower()] + [a.lower() for a in kp.get("aliases", []) if len(a) >= 3]
                    matched_mention = False
                    for pat in patterns:
                        regex = r"\b" + re.escape(pat) + r"\b"
                        if re.search(regex, all_text):
                            matched_mention = True
                            break

                    if matched_mention:
                        link_type = "filename" if kp_name.lower() in p.name.lower() else "ocr"
                        self.database.link_person_to_file(
                            person_id=kp["id"],
                            file_id=file_id,
                            link_type=link_type,
                            confidence=0.85 if link_type == "filename" else 0.75,
                            is_confirmed=True,
                            notes=f"Mention in {link_type}",
                        )
                        linked_associations.append({
                            "person_id": kp["id"],
                            "type": link_type,
                            "confidence": 0.80,
                        })
            except Exception as text_link_err:
                logger.debug("Text mention linking skipped for %s: %s", p.name, text_link_err)

        return linked_associations

    def scan_and_cluster_all_library_faces(
        self,
        force: bool = False,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Scans all image files in the library, runs local YuNet face detection and SFace embeddings,
        and matches against known persons. Unmatched faces remain unassigned detections.
        Then clusters recurring unassigned faces into clean clusters (Unknown Person 1, 2...).
        """
        if not self.is_face_indexing_enabled:
            return {
                "status": "disabled",
                "message": "Face indexing is currently disabled in Privacy settings.",
                "images_scanned": 0,
                "faces_detected": 0,
            }

        with self.database.connection() as conn:
            sql = """
                SELECT id, filename, path
                FROM files
                WHERE LOWER(extension) IN ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
                ORDER BY id ASC
            """
            rows = [dict(r) for r in conn.execute(sql).fetchall()]

        scanned = 0
        faces_found = 0
        matched_faces = 0

        # Pre-load known person embeddings
        known_raw = self.database.get_all_person_embeddings()
        known_list: List[Tuple[int, np.ndarray, bool]] = []
        for k in known_raw:
            vec = np.frombuffer(k["embedding"], dtype=np.float32)
            known_list.append((k["person_id"], vec, bool(k.get("is_reference", 1))))

        for idx, row in enumerate(rows):
            p = Path(row["path"])
            if not p.is_file():
                continue

            if not force:
                existing = self.database.get_face_detections(file_id=row["id"])
                if existing:
                    continue

            scanned += 1
            if progress_callback:
                try:
                    progress_callback(idx + 1, len(rows), row["filename"])
                except Exception:
                    pass

            try:
                faces = self.face_service.detect_and_embed_faces(p)
                if faces:
                    file_id = row["id"]
                    for face in faces:
                        faces_found += 1
                        matched_pid, sim, grade = self.face_service.match_against_known_persons(
                            face.embedding_vec, known_list
                        )

                        target_pid = matched_pid if grade in ("CONFIRMED", "POSSIBLE") else None
                        is_confirmed = (grade == "CONFIRMED")
                        if target_pid:
                            matched_faces += 1

                        self.database.add_face_detection(
                            file_id=file_id,
                            box_x=face.box_x,
                            box_y=face.box_y,
                            box_w=face.box_w,
                            box_h=face.box_h,
                            confidence=face.confidence,
                            embedding=face.embedding,
                            person_id=target_pid,
                            match_confidence=sim if target_pid else None,
                            face_quality=face.face_quality,
                            landmarks=face.landmarks,
                        )

                        if target_pid:
                            self.database.link_person_to_file(
                                person_id=target_pid,
                                file_id=file_id,
                                link_type="face",
                                confidence=sim,
                                is_confirmed=is_confirmed,
                                notes=f"Face match ({grade}, {sim:.2f})",
                            )
            except Exception as err:
                logger.warning("Error scanning faces in %s: %s", p.name, err)

        # Proactively link known persons across all photos and cluster remaining unassigned faces
        self.propagate_and_link_known_persons()
        clusters_formed = self.cluster_unassigned_faces(min_cluster_size=2, similarity_threshold=0.48)

        return {
            "status": "completed",
            "images_scanned": scanned,
            "faces_detected": faces_found,
            "matched_to_known": matched_faces,
            "new_clusters_created": clusters_formed,
            "total_persons": len(self.database.list_persons(include_clusters=True)),
        }

    def propagate_and_link_known_persons(self, target_person_id: Optional[int] = None) -> int:
        """
        Cross-photo person linking and identity propagation across the entire library.
        - Evaluates unassigned faces and automated cluster faces against known enrolled persons.
        - Matches using multi-reference maximum cosine similarity.
        - When a confirmed match (similarity >= 0.52 and margin >= 0.03) is found:
            * Automatically assigns the face detection to the person.
            * Links the file to the person.
            * Adds the embedding to person_embeddings to continuously enrich the person's profile.
            * Cleans up empty automated clusters if all members were claimed.
        - Also deduplicates and merges any person profiles sharing the exact same name.
        """
        # 1. Deduplicate any existing human persons with identical names (e.g. Kaavya 94 & Kaavya 96)
        with self.database.connection() as conn:
            human_persons = conn.execute("SELECT id, name FROM persons WHERE is_cluster = 0 ORDER BY id ASC").fetchall()
            seen_names: Dict[str, int] = {}
            for hp in human_persons:
                norm_n = hp["name"].strip().lower()
                if norm_n in seen_names:
                    primary_id = seen_names[norm_n]
                    dup_id = hp["id"]
                    logger.info("Auto-merging duplicate person profile %d into %d for name '%s'", dup_id, primary_id, hp["name"])
                    self.database.merge_persons(dup_id, primary_id)
                else:
                    seen_names[norm_n] = hp["id"]

        # 2. Gather all known non-cluster person embeddings (including reference & confirmed embeddings)
        all_emb_rows = self.database.get_all_person_embeddings()
        known_embs: Dict[int, List[np.ndarray]] = {}
        for r in all_emb_rows:
            if not r.get("is_cluster") and r.get("embedding"):
                try:
                    vec = np.frombuffer(r["embedding"], dtype=np.float32).copy()
                    n = np.linalg.norm(vec)
                    if n > 1e-6:
                        pid = r["person_id"]
                        if target_person_id is not None and pid != target_person_id:
                            continue
                        known_embs.setdefault(pid, []).append(vec / n)
                except Exception:
                    pass

        if not known_embs:
            return 0

        # 3. Query candidate face detections: unassigned (person_id IS NULL) or in clusters (is_cluster = 1)
        with self.database.connection() as conn:
            cand_rows = conn.execute("""
                SELECT fd.id, fd.file_id, fd.embedding, fd.person_id, p.is_cluster
                FROM face_detections fd
                LEFT JOIN persons p ON fd.person_id = p.id
                WHERE fd.embedding IS NOT NULL
                  AND (fd.person_id IS NULL OR p.is_cluster = 1)
            """).fetchall()

        auto_linked_count = 0
        for cand in cand_rows:
            try:
                c_vec = np.frombuffer(cand["embedding"], dtype=np.float32).copy()
                c_norm = np.linalg.norm(c_vec)
                if c_norm < 1e-6:
                    continue
                c_norm_vec = c_vec / c_norm

                best_pid = None
                best_sim = -1.0
                second_sim = -1.0

                for pid, ref_vecs in known_embs.items():
                    sim = max(float(np.dot(c_norm_vec, rv)) for rv in ref_vecs)
                    if sim > best_sim:
                        second_sim = best_sim
                        best_sim = sim
                        best_pid = pid
                    elif sim > second_sim:
                        second_sim = sim

                margin = best_sim - second_sim if second_sim >= 0.0 else 1.0

                # Confirmed match threshold >= 0.52 and margin >= 0.03
                if best_pid and best_sim >= CONFIRMED_MATCH_THRESHOLD and margin >= MIN_MARGIN_THRESHOLD:
                    self.database.assign_face_detection_to_person(
                        detection_id=cand["id"],
                        person_id=best_pid,
                        match_confidence=best_sim,
                    )
                    self.database.link_person_to_file(
                        person_id=best_pid,
                        file_id=cand["file_id"],
                        link_type="face",
                        confidence=best_sim,
                        is_confirmed=True,
                        notes=f"Auto-linked across photos (sim={best_sim:.2f})",
                    )
                    # Add embedding to enrich person profile
                    self.database.add_person_embedding(
                        person_id=best_pid,
                        embedding=c_vec.tobytes(),
                        source_file_id=cand["file_id"],
                        is_reference=False,
                    )
                    known_embs[best_pid].append(c_norm_vec)
                    auto_linked_count += 1
            except Exception as e:
                logger.debug("Error auto-linking face #%s: %s", cand["id"], e)

        # 4. Clean up any empty automated clusters
        with self.database.connection() as conn:
            empty_clusters = conn.execute("""
                SELECT p.id FROM persons p
                WHERE p.is_cluster = 1
                  AND (SELECT COUNT(*) FROM face_detections fd WHERE fd.person_id = p.id) = 0
            """).fetchall()
            for ec in empty_clusters:
                conn.execute("DELETE FROM person_embeddings WHERE person_id = ?", (ec["id"],))
                conn.execute("DELETE FROM person_file_links WHERE person_id = ?", (ec["id"],))
                conn.execute("DELETE FROM persons WHERE id = ?", (ec["id"],))

        return auto_linked_count

    def cluster_unassigned_faces(
        self,
        min_cluster_size: int = 2,
        similarity_threshold: float = 0.48,
    ) -> int:
        """
        Clusters unassigned face detections into verified Unknown Person groups.
        - First runs propagation to ensure all known persons have claimed their faces.
        - Groups recurring unassigned faces using connected components with calibrated threshold 0.48.
        """
        # Step 1: Ensure known persons have claimed all matching faces
        self.propagate_and_link_known_persons()

        # Step 2: Query remaining unassigned faces
        unassigned = self.database.get_unassigned_face_detections(limit=1000)
        if len(unassigned) < min_cluster_size:
            return 0

        # Extract embeddings
        det_data: List[Tuple[int, int, np.ndarray]] = []
        for d in unassigned:
            if not d.get("embedding"):
                continue
            arr = np.frombuffer(d["embedding"], dtype=np.float32).copy()
            norm = np.linalg.norm(arr)
            if norm > 1e-6:
                det_data.append((d["id"], d["file_id"], arr / norm))

        if len(det_data) < min_cluster_size:
            return 0

        # Build adjacency graph for connected components
        n = len(det_data)
        adj: List[List[int]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                sim = float(np.dot(det_data[i][2], det_data[j][2]))
                if sim >= similarity_threshold:
                    adj[i].append(j)
                    adj[j].append(i)

        visited = [False] * n
        new_clusters_count = 0

        for i in range(n):
            if visited[i]:
                continue
            # BFS connected component
            component: List[int] = []
            queue = [i]
            visited[i] = True
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in adj[curr]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)

            if len(component) >= min_cluster_size:
                existing_clusters = [x for x in self.database.list_persons(include_clusters=True) if x.get("is_cluster")]
                cluster_label = f"Unknown Person {len(existing_clusters) + 1}"
                first_item = det_data[component[0]]

                cluster_pid = self.database.create_person(
                    name=cluster_label,
                    is_cluster=True,
                    cluster_label=cluster_label,
                    avatar_file_id=first_item[1],
                )

                for member_idx in component:
                    m_det_id, m_file_id, m_vec = det_data[member_idx]
                    self.database.assign_face_detection_to_person(
                        detection_id=m_det_id,
                        person_id=cluster_pid,
                        match_confidence=similarity_threshold,
                    )
                    self.database.add_person_embedding(
                        person_id=cluster_pid,
                        embedding=m_vec.tobytes(),
                        source_file_id=m_file_id,
                        is_reference=(member_idx == component[0]),
                    )

                new_clusters_count += 1

        return new_clusters_count

    def reprocess_all_faces(
        self,
        backup: bool = True,
        force: bool = True,
    ) -> Dict[str, Any]:
        """
        Requirement 7: Safe reprocessing mechanism.
        - Backs up the SQLite database file before modification.
        - Preserves all confirmed human person profiles and their enrolled reference embeddings.
        - Clears stale automated clusters and stale detections safely inside a transaction.
        - Re-runs calibrated face detection and identity matching on all library images.
        - Rebuilds person-file associations cleanly without destroying V3 search indexes.
        """
        # 1. Safe backup
        backup_path = None
        db_file = getattr(self.database, "path", None) or getattr(self.database, "db_path", None)
        if backup and db_file and Path(db_file).exists():
            db_p = Path(db_file)
            ts = int(time.time())
            backup_path = db_p.parent / f"intellifile_backup_pre_reprocess_{ts}.sqlite3"
            try:
                shutil.copy2(db_p, backup_path)
                logger.info("Created safe database backup at %s", backup_path)
            except Exception as b_err:
                logger.warning("Database backup failed: %s", b_err)

        # 2. Transactional cleanup of stale automated clusters and face links
        with self.database.connection() as conn:
            # Delete auto-generated clusters (is_cluster = 1), preserving known user profiles (is_cluster = 0)
            cluster_rows = conn.execute("SELECT id FROM persons WHERE is_cluster = 1").fetchall()
            cluster_ids = [r["id"] for r in cluster_rows]

            if cluster_ids:
                pl = ",".join("?" for _ in cluster_ids)
                conn.execute(f"DELETE FROM person_embeddings WHERE person_id IN ({pl})", cluster_ids)
                conn.execute(f"DELETE FROM person_file_links WHERE person_id IN ({pl})", cluster_ids)
                conn.execute(f"DELETE FROM persons WHERE id IN ({pl})", cluster_ids)

            # Clear stale face detections and face links
            conn.execute("DELETE FROM face_detections")
            conn.execute("DELETE FROM person_file_links WHERE link_type = 'face'")

        # 3. Re-run calibrated scan across all library images
        scan_results = self.scan_and_cluster_all_library_faces(force=True)

        return {
            "status": "completed",
            "backup_created": str(backup_path) if backup_path else None,
            "scan_results": scan_results,
        }

    def get_detection_face_crop(self, detection_id: int) -> Optional[bytes]:
        """Extracts the exact cropped face image for a specific face detection record."""
        det = self.database.get_face_detection_by_id(detection_id)
        if not det:
            return None

        file_rec = self.database.get_file_by_id(det["file_id"])
        if not file_rec or not file_rec.get("path"):
            return None

        return self.face_service.extract_face_crop(
            image_path=file_rec["path"],
            box_x=det["box_x"],
            box_y=det["box_y"],
            box_w=det["box_w"],
            box_h=det["box_h"],
        )

    def get_file_faces(self, file_id: int) -> List[dict]:
        """Returns all detected faces in a file with their bounding boxes and identities."""
        faces = self.database.get_file_face_detections(file_id)
        # Check if known persons have suggestions for any unassigned face
        all_emb_rows = self.database.get_all_person_embeddings()
        known_embs: Dict[int, List[np.ndarray]] = {}
        person_name_map: Dict[int, str] = {}
        for r in all_emb_rows:
            if not r.get("is_cluster") and r.get("embedding"):
                try:
                    emb_arr = np.frombuffer(r["embedding"], dtype=np.float32).copy()
                    n = np.linalg.norm(emb_arr)
                    if n > 1e-6:
                        pid = r["person_id"]
                        known_embs.setdefault(pid, []).append(emb_arr / n)
                        person_name_map[pid] = r["name"]
                except Exception:
                    pass

        if known_embs:
            for f in faces:
                if not f.get("person_id") and f.get("id"):
                    det_row = self.database.get_face_detection_by_id(f["id"])
                    if det_row and det_row.get("embedding") and (det_row.get("match_confidence") is None or det_row.get("match_confidence") > 0.0):
                        try:
                            det_vec = np.frombuffer(det_row["embedding"], dtype=np.float32).copy()
                            d_norm = np.linalg.norm(det_vec)
                            if d_norm > 1e-6:
                                d_norm_vec = det_vec / d_norm
                                best_p = None
                                best_s = -1.0
                                for pid, ref_vecs in known_embs.items():
                                    s = max(float(np.dot(d_norm_vec, rv)) for rv in ref_vecs)
                                    if s > best_s:
                                        best_s = s
                                        best_p = pid
                                if best_p and best_s >= POSSIBLE_MATCH_THRESHOLD:
                                    f["suggested_person_id"] = best_p
                                    f["suggested_person_name"] = person_name_map.get(best_p, f"Person {best_p}")
                                    f["suggested_similarity"] = round(float(best_s), 3)
                        except Exception:
                            pass
        return faces

    def get_face_review_queue(self, limit: int = 150) -> List[dict]:
        """
        Returns face detections requiring user review.
        Evaluates unassigned faces and clusters against known enrolled persons to offer candidate suggestions.
        """
        # Purge missing file records and proactively link known matches
        self.database.clean_missing_face_files()
        self.propagate_and_link_known_persons()

        raw_items = self.database.get_face_review_queue(limit=limit)
        if not raw_items:
            return []

        # Load known non-cluster person embeddings to suggest candidate matches
        known_embs: Dict[int, List[np.ndarray]] = {}
        person_name_map: Dict[int, str] = {}
        all_emb_rows = self.database.get_all_person_embeddings()
        for r in all_emb_rows:
            if not r.get("is_cluster") and r.get("embedding"):
                try:
                    emb_arr = np.frombuffer(r["embedding"], dtype=np.float32).copy()
                    n = np.linalg.norm(emb_arr)
                    if n > 1e-6:
                        pid = r["person_id"]
                        known_embs.setdefault(pid, []).append(emb_arr / n)
                        person_name_map[pid] = r["name"]
                except Exception:
                    pass

        review_queue = []
        for item in raw_items:
            # Skip if file does not exist on disk
            if not Path(item["path"]).is_file():
                continue

            res_item = {
                "id": item["id"],
                "file_id": item["file_id"],
                "filename": item["filename"],
                "path": item["path"],
                "box": [item["box_x"], item["box_y"], item["box_w"], item["box_h"]],
                "confidence": round(float(item["confidence"]), 3) if item["confidence"] else None,
                "face_quality": round(float(item["face_quality"]), 3) if item["face_quality"] else None,
                "person_id": item["person_id"],
                "person_name": item["person_name"],
                "is_cluster": bool(item.get("is_cluster")),
                "match_confidence": round(float(item["match_confidence"]), 3) if item.get("match_confidence") else None,
                "is_confirmed": bool(item.get("link_confirmed")),
                "created_at": item["created_at"],
            }

            # Check if this face matches any known person
            cand_pid = None
            cand_sim = 0.0
            if known_embs:
                det_row = self.database.get_face_detection_by_id(item["id"])
                if det_row and det_row.get("embedding"):
                    try:
                        det_vec = np.frombuffer(det_row["embedding"], dtype=np.float32).copy()
                        d_norm = np.linalg.norm(det_vec)
                        if d_norm > 1e-6:
                            d_norm_vec = det_vec / d_norm
                            best_p = None
                            best_s = -1.0
                            for pid, ref_vecs in known_embs.items():
                                s = max(float(np.dot(d_norm_vec, rv)) for rv in ref_vecs)
                                if s > best_s:
                                    best_s = s
                                    best_p = pid
                            if best_p and best_s >= POSSIBLE_MATCH_THRESHOLD:
                                cand_pid = best_p
                                cand_sim = best_s
                    except Exception:
                        pass

            if cand_pid and cand_sim >= POSSIBLE_MATCH_THRESHOLD:
                res_item["suggested_person_id"] = cand_pid
                res_item["suggested_person_name"] = person_name_map.get(cand_pid, f"Person {cand_pid}")
                res_item["suggested_similarity"] = round(float(cand_sim), 3)
            elif item.get("person_id") and item.get("is_cluster"):
                res_item["suggested_person_id"] = item["person_id"]
                res_item["suggested_person_name"] = item["person_name"]
                res_item["suggested_similarity"] = res_item["match_confidence"] or 0.50
            elif item.get("person_id") and not item.get("is_cluster"):
                res_item["suggested_person_id"] = item["person_id"]
                res_item["suggested_person_name"] = item["person_name"]
                res_item["suggested_similarity"] = res_item["match_confidence"] or 1.0
            else:
                res_item["suggested_person_id"] = None
                res_item["suggested_person_name"] = None
                res_item["suggested_similarity"] = None

            review_queue.append(res_item)

        return review_queue

    def create_person_from_detection(
        self,
        detection_id: int,
        name: str,
        aliases: Optional[List[str]] = None,
        notes: str = "",
    ) -> dict:
        """
        Creates a new person profile using a specific face detection as the reference.
        Never affects other faces in the same photograph.
        Automatically links matching faces across other photos in the library.
        """
        det = self.database.get_face_detection_by_id(detection_id)
        if not det:
            raise ValueError(f"Face detection {detection_id} not found")

        person_id = self.database.create_person(
            name=name.strip(),
            aliases=aliases,
            notes=notes,
            is_cluster=False,
            avatar_file_id=det["file_id"],
        )

        if det.get("embedding"):
            self.database.add_person_embedding(
                person_id=person_id,
                embedding=det["embedding"],
                source_file_id=det["file_id"],
                is_reference=True,
            )

        self.database.assign_face_detection_to_person(
            detection_id=detection_id,
            person_id=person_id,
            match_confidence=1.0,
        )

        self.propagate_and_link_known_persons(person_id)

        return {
            "status": "created",
            "person_id": person_id,
            "name": name.strip(),
            "detection_id": detection_id,
        }

    def confirm_face_detection(
        self,
        detection_id: int,
        person_id: Optional[int] = None,
    ) -> dict:
        """
        Confirms the person identity for a single face detection.
        Supports:
        - Explicitly provided person_id (from suggested identity or assignment)
        - Already linked person_id (from cluster or pending link)
        - Automatic fallback resolution against known enrolled profiles if unassigned
        """
        det = self.database.get_face_detection_by_id(detection_id)
        if not det:
            raise ValueError(f"Face detection {detection_id} not found")

        pid = person_id or det.get("person_id")

        # If person_id is not yet assigned on this detection, dynamically resolve
        # candidate match from known enrolled persons using embedding similarity
        if not pid:
            all_emb_rows = self.database.get_all_person_embeddings()
            if all_emb_rows and det.get("embedding"):
                try:
                    det_vec = np.frombuffer(det["embedding"], dtype=np.float32).copy()
                    d_norm = np.linalg.norm(det_vec)
                    if d_norm > 1e-6:
                        d_norm_vec = det_vec / d_norm
                        best_p = None
                        best_s = -1.0
                        for r in all_emb_rows:
                            if not r.get("is_cluster") and r.get("embedding"):
                                emb_arr = np.frombuffer(r["embedding"], dtype=np.float32).copy()
                                n = np.linalg.norm(emb_arr)
                                if n > 1e-6:
                                    s = float(np.dot(d_norm_vec, emb_arr / n))
                                    if s > best_s:
                                        best_s = s
                                        best_p = r["person_id"]
                        if best_p and best_s >= POSSIBLE_MATCH_THRESHOLD:
                            pid = best_p
                except Exception as e:
                    logger.debug("Error resolving candidate person for face %s: %s", detection_id, e)

        if not pid:
            raise ValueError(
                f"Face detection {detection_id} has no assigned identity to confirm. "
                "Please assign to a person or create a new profile."
            )

        now = self.database.now()
        with self.database.connection() as conn:
            conn.execute(
                "UPDATE face_detections SET person_id = ?, match_confidence = 1.0 WHERE id = ?",
                (pid, detection_id),
            )
            conn.execute(
                """
                INSERT INTO person_file_links (person_id, file_id, link_type, confidence, is_confirmed, notes, created_at)
                VALUES (?, ?, 'face', 1.0, 1, 'Confirmed match', ?)
                ON CONFLICT(person_id, file_id, link_type) DO UPDATE SET
                    confidence = 1.0,
                    is_confirmed = 1,
                    notes = 'Confirmed match'
                """,
                (pid, det["file_id"], now),
            )

        person = self.database.get_person(pid)
        if person and not person.get("is_cluster") and (det.get("face_quality") or 0) >= 0.40 and det.get("embedding"):
            self.database.add_person_embedding(
                person_id=pid,
                embedding=det["embedding"],
                source_file_id=det["file_id"],
                is_reference=True,
            )

        if person and not person.get("is_cluster"):
            self.propagate_and_link_known_persons(pid)

        return {
            "status": "confirmed",
            "detection_id": detection_id,
            "person_id": pid,
            "person_name": person.get("name") if person else None,
        }

    def reject_face_detection(self, detection_id: int) -> dict:
        """Rejects suggested match, returning this face detection to unassigned status and suppressing auto-suggestions."""
        det = self.database.get_face_detection_by_id(detection_id)
        if not det:
            raise ValueError(f"Face detection {detection_id} not found")

        old_pid = det.get("person_id")
        file_id = det["file_id"]

        with self.database.connection() as conn:
            conn.execute(
                "UPDATE face_detections SET person_id = NULL, match_confidence = 0.0 WHERE id = ?",
                (detection_id,),
            )
            if old_pid is not None:
                other_count = conn.execute(
                    "SELECT COUNT(*) FROM face_detections WHERE file_id = ? AND person_id = ?",
                    (file_id, old_pid),
                ).fetchone()[0]
                if other_count == 0:
                    conn.execute(
                        "DELETE FROM person_file_links WHERE file_id = ? AND person_id = ? AND link_type = 'face'",
                        (file_id, old_pid),
                    )

        return {
            "status": "rejected",
            "detection_id": detection_id,
            "previous_person_id": old_pid,
        }

    def keep_unknown_face_detection(self, detection_id: int) -> dict:
        """Keeps face detection as unassigned/unknown and suppresses automatic match suggestions."""
        det = self.database.get_face_detection_by_id(detection_id)
        if not det:
            raise ValueError(f"Face detection {detection_id} not found")

        old_pid = det.get("person_id")
        file_id = det["file_id"]

        with self.database.connection() as conn:
            conn.execute(
                "UPDATE face_detections SET person_id = NULL, match_confidence = 0.0 WHERE id = ?",
                (detection_id,),
            )
            if old_pid is not None:
                other_count = conn.execute(
                    "SELECT COUNT(*) FROM face_detections WHERE file_id = ? AND person_id = ?",
                    (file_id, old_pid),
                ).fetchone()[0]
                if other_count == 0:
                    conn.execute(
                        "DELETE FROM person_file_links WHERE file_id = ? AND person_id = ? AND link_type = 'face'",
                        (file_id, old_pid),
                    )

        return {
            "status": "kept_unknown",
            "detection_id": detection_id,
        }

    def add_reference_photo_to_person(
        self,
        person_id: int,
        photo_path: Optional[str] = None,
        detection_id: Optional[int] = None,
    ) -> dict:
        """
        Adds a new reference photo/embedding to an existing person (allowing multiple reference photos).
        Can be done from an existing face detection or by scanning a new image file path.
        """
        person = self.database.get_person(person_id)
        if not person:
            raise ValueError(f"Person {person_id} not found")

        if detection_id is not None:
            det = self.database.get_face_detection_by_id(detection_id)
            if not det:
                raise ValueError(f"Face detection {detection_id} not found")
            if det.get("embedding"):
                self.database.add_person_embedding(
                    person_id=person_id,
                    embedding=det["embedding"],
                    source_file_id=det["file_id"],
                    is_reference=True,
                )
            self.database.assign_face_detection_to_person(detection_id, person_id, match_confidence=1.0)
            self.propagate_and_link_known_persons(person_id)
            return {"status": "added", "person_id": person_id, "detection_id": detection_id}

        if photo_path:
            p = Path(photo_path).resolve()
            if not p.is_file():
                raise FileNotFoundError(f"Image file not found: {photo_path}")

            f_rec = self.database.get_file_by_path(str(p))
            file_id = f_rec["id"] if f_rec else None

            faces = self.face_service.detect_and_embed_faces(p)
            if not faces:
                raise ValueError(f"No face detected in reference photo: {p.name}")

            # If multiple faces, choose dominant/largest face
            chosen_face = faces[0]
            if len(faces) > 1:
                sorted_by_area = sorted(faces, key=lambda f: f.box_w * f.box_h, reverse=True)
                chosen_face = sorted_by_area[0]

            emb_id = self.database.add_person_embedding(
                person_id=person_id,
                embedding=chosen_face.embedding,
                source_file_id=file_id,
                is_reference=True,
            )

            if file_id:
                self.database.link_person_to_file(
                    person_id=person_id,
                    file_id=file_id,
                    link_type="face",
                    confidence=1.0,
                    is_confirmed=True,
                    notes="Reference photo added",
                )
                self.database.add_face_detection(
                    file_id=file_id,
                    box_x=chosen_face.box_x,
                    box_y=chosen_face.box_y,
                    box_w=chosen_face.box_w,
                    box_h=chosen_face.box_h,
                    confidence=chosen_face.confidence,
                    embedding=chosen_face.embedding,
                    person_id=person_id,
                    match_confidence=1.0,
                    face_quality=chosen_face.face_quality,
                    landmarks=chosen_face.landmarks,
                )

            self.propagate_and_link_known_persons(person_id)

            return {
                "status": "added",
                "person_id": person_id,
                "embedding_id": emb_id,
                "file_id": file_id,
                "face_quality": chosen_face.face_quality,
            }

        raise ValueError("Either photo_path or detection_id must be provided")
