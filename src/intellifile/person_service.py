"""
person_service.py — V4 Person Management & Entity Linking Service for FILE XTRACTOR.
Coordinates local face detection, identity matching, unknown face clustering,
and multi-signal person-file linking (Face, OCR, Filename, Entity).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

from .database import Database
from .face_service import FaceService, DetectedFace, HIGH_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD


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
        Creates a new Person profile with multiple reference photos (Requirement 6).
        Extracts local face embeddings from reference photos and stores them as reference anchors.
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

                # Query or register file in database to obtain file_id
                f_rec = self.database.get_file_by_path(str(p))
                file_id = f_rec["id"] if f_rec else None

                if avatar_file_id is None and file_id:
                    avatar_file_id = file_id

                faces = self.face_service.detect_and_embed_faces(p)
                for face in faces:
                    # Store reference face embedding
                    self.database.add_person_embedding(
                        person_id=person_id,
                        embedding=face.embedding,
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

        if avatar_file_id:
            self.database.update_person(person_id, avatar_file_id=avatar_file_id)

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
        """Requirement 9: Names an unknown face cluster into an approved person."""
        return self.database.name_cluster(cluster_id, person_name.strip())

    def process_file_faces_and_entities(
        self,
        file_id: int,
        file_path: Path | str,
        ocr_text: str = "",
        document_text: str = "",
    ) -> List[dict]:
        """
        Executes face detection & multi-signal entity linking for an indexed file (Requirements 12, 14, 15).
        Supports multiple people per image and respects face indexing toggle.
        """
        p = Path(file_path).resolve()
        linked_associations: List[dict] = []

        # ── 1. Face Recognition Pipeline (Images only, when enabled) ───────────
        if self.is_face_indexing_enabled and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            try:
                faces = self.face_service.detect_and_embed_faces(p)
                if faces:
                    # Load known person embeddings library
                    known_raw = self.database.get_all_person_embeddings()
                    known_list: List[Tuple[int, np.ndarray]] = []
                    for k in known_raw:
                        vec = np.frombuffer(k["embedding"], dtype=np.float32)
                        known_list.append((k["person_id"], vec))

                    for face in faces:
                        # Match against known persons
                        matched_pid, sim, grade = self.face_service.match_against_known_persons(
                            face.embedding_vec, known_list
                        )

                        # Check if matched identity is an unknown cluster or a named person
                        target_pid = matched_pid
                        if target_pid is None:
                            # Create or group into an unknown face cluster (Requirement 9)
                            cluster_count = len([x for x in self.database.list_persons(include_clusters=True) if x.get("is_cluster")])
                            cluster_label = f"Unknown Person {cluster_count + 1}"
                            target_pid = self.database.create_person(
                                name=cluster_label,
                                is_cluster=True,
                                cluster_label=cluster_label,
                                avatar_file_id=file_id,
                            )
                            # Register this embedding to the new cluster
                            self.database.add_person_embedding(target_pid, face.embedding, source_file_id=file_id)
                            known_list.append((target_pid, face.embedding_vec))
                            grade = "UNKNOWN_CLUSTER"

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
                            match_confidence=sim,
                        )

                        # Link file to person (Requirement 14: multiple people per image)
                        is_confirmed = (grade == "HIGH")
                        self.database.link_person_to_file(
                            person_id=target_pid,
                            file_id=file_id,
                            link_type="face",
                            confidence=sim if sim > 0 else 0.5,
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
                    if not kp_name:
                        continue
                    patterns = [kp_name.lower()] + [a.lower() for a in kp.get("aliases", [])]

                    matched_mention = False
                    for pat in patterns:
                        if len(pat) >= 3 and pat in all_text:
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
