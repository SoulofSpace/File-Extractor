"""
face_service.py — Dedicated Local Face Detection & Face Recognition Service for FILE XTRACTOR V4.
Runs 100% locally on CPU / GPU fallback without any cloud APIs.
Uses YuNet (fast ONNX face detection) and SFace (deep face embedding, 128-d L2 normalized).
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Default model paths in models/ directory
DEFAULT_YUNET_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "face_detection_yunet_2023mar.onnx"
DEFAULT_SFACE_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "face_recognition_sface_2021dec.onnx"

# Calibrated matching thresholds
# SFace cosine similarity on normalized vectors:
# >= 0.52 + margin >= 0.03: Confirmed match (automatic association)
# >= 0.42: Possible match (user review)
# < 0.42: Unknown (unassigned)
CONFIRMED_MATCH_THRESHOLD = 0.52
POSSIBLE_MATCH_THRESHOLD = 0.42
MIN_MARGIN_THRESHOLD = 0.03

# Calibrated detection parameters
DEFAULT_SCORE_THRESHOLD = 0.68
MIN_FACE_DIMENSION = 28
MIN_SHARPNESS_VAR = 2.0
IOU_SUPPRESSION_THRESHOLD = 0.35
IOS_SUPPRESSION_THRESHOLD = 0.50


@dataclass
class DetectedFace:
    box_x: float
    box_y: float
    box_w: float
    box_h: float
    confidence: float
    face_quality: float
    landmarks: List[Tuple[float, float]] = field(default_factory=list)
    embedding: bytes = b""
    embedding_vec: np.ndarray = field(default_factory=lambda: np.zeros(128, dtype=np.float32))
    matched_person_id: Optional[int] = None
    match_confidence: Optional[float] = None
    match_grade: str = "UNKNOWN"  # "CONFIRMED", "POSSIBLE", "UNKNOWN"


def compute_iou_and_ios(
    b1: Tuple[float, float, float, float],
    b2: Tuple[float, float, float, float],
) -> Tuple[float, float]:
    """Computes Intersection-over-Union (IoU) and Intersection-over-Smaller (IoS)."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[0] + b1[2], b2[0] + b2[2])
    y2 = min(b1[1] + b1[3], b2[1] + b2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = b1[2] * b1[3]
    area2 = b2[2] * b2[3]

    if area1 <= 0.0 or area2 <= 0.0:
        return 0.0, 0.0

    union_area = area1 + area2 - inter_area
    iou = inter_area / union_area if union_area > 0.0 else 0.0
    ios = inter_area / min(area1, area2) if min(area1, area2) > 0.0 else 0.0
    return iou, ios


def filter_duplicate_detections(
    faces: List[DetectedFace],
    iou_thresh: float = IOU_SUPPRESSION_THRESHOLD,
    ios_thresh: float = IOS_SUPPRESSION_THRESHOLD,
) -> List[DetectedFace]:
    """
    Suppresses duplicate or overlapping bounding box detections of the same face.
    Sorts by confidence descending and filters out detections overlapping significantly.
    """
    if len(faces) <= 1:
        return faces

    sorted_faces = sorted(faces, key=lambda f: f.confidence, reverse=True)
    kept: List[DetectedFace] = []

    for f in sorted_faces:
        box_f = (f.box_x, f.box_y, f.box_w, f.box_h)
        is_dup = False
        for k in kept:
            box_k = (k.box_x, k.box_y, k.box_w, k.box_h)
            iou, ios = compute_iou_and_ios(box_f, box_k)
            if iou >= iou_thresh or ios >= ios_thresh:
                is_dup = True
                break
        if not is_dup:
            kept.append(f)

    return kept


class FaceService:
    """
    Dedicated local face detection and identity matching engine.
    Ensures zero cloud dependencies and supports CPU fallback.
    """

    def __init__(
        self,
        yunet_path: Optional[Path | str] = None,
        sface_path: Optional[Path | str] = None,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> None:
        self.yunet_path = Path(yunet_path) if yunet_path else DEFAULT_YUNET_PATH
        self.sface_path = Path(sface_path) if sface_path else DEFAULT_SFACE_PATH
        self.score_threshold = score_threshold
        self._cv2 = None
        self._detector = None
        self._recognizer = None
        self._initialized = False

    def is_available(self) -> bool:
        """Returns True if local face models can be loaded and initialized."""
        return self.initialize()

    def initialize(self) -> bool:
        if self._initialized:
            return True

        try:
            import cv2
            self._cv2 = cv2

            if not self.yunet_path.exists() or not self.sface_path.exists():
                logger.warning(
                    "Local face models not found at %s or %s.",
                    self.yunet_path, self.sface_path
                )
                return False

            self._detector = cv2.FaceDetectorYN_create(
                model=str(self.yunet_path.resolve()),
                config="",
                input_size=(320, 320),
                score_threshold=self.score_threshold,
                nms_threshold=0.3,
                top_k=5000,
            )

            self._recognizer = cv2.FaceRecognizerSF_create(
                model=str(self.sface_path.resolve()),
                config="",
            )

            self._initialized = True
            logger.info("FaceService successfully initialized with YuNet + SFace models.")
            return True
        except Exception as e:
            logger.error("Failed to initialize OpenCV YuNet/SFace models: %s", e)
            return False

    def detect_and_embed_faces(
        self,
        image_path: Path | str,
        min_confidence: Optional[float] = None,
    ) -> List[DetectedFace]:
        """
        Detects all valid faces in an image file and extracts 128-dimensional L2-normalized face embeddings.
        - Every image is processed independently.
        - An image with zero detected faces returns an empty list (zero records).
        - Rejects tiny noise, distorted boxes, bad landmark geometries, and blurry crops.
        - Filters duplicate detections using NMS (IoU / IoS).
        """
        p = Path(image_path).resolve()
        if not p.is_file():
            return []

        if not self.initialize():
            logger.warning("FaceService models unavailable. Skipping face detection for %s", p.name)
            return []

        try:
            cv2 = self._cv2
            # Unicode-safe image loader for Windows
            img = None
            try:
                with open(p, "rb") as f:
                    file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            except Exception:
                img = cv2.imread(str(p))

            if img is None:
                return []

            orig_h, orig_w = img.shape[:2]
            if orig_h < MIN_FACE_DIMENSION or orig_w < MIN_FACE_DIMENSION:
                return []

            # Adaptively scale down extremely large images (e.g. >1600px) for speed & consistency
            max_dim = 1600
            scale = 1.0
            det_img = img
            if max(orig_h, orig_w) > max_dim:
                scale = max_dim / max(orig_h, orig_w)
                det_img = cv2.resize(
                    img,
                    (int(orig_w * scale), int(orig_h * scale)),
                    interpolation=cv2.INTER_AREA,
                )

            h, w = det_img.shape[:2]
            self._detector.setInputSize((w, h))
            if min_confidence is not None and min_confidence != self.score_threshold:
                self._detector.setScoreThreshold(min_confidence)

            _, raw_faces = self._detector.detect(det_img)

            # Reset threshold if modified
            if min_confidence is not None and min_confidence != self.score_threshold:
                self._detector.setScoreThreshold(self.score_threshold)

            if raw_faces is None or len(raw_faces) == 0:
                return []

            active_conf_thresh = min_confidence if min_confidence is not None else self.score_threshold
            candidate_faces: List[DetectedFace] = []

            for raw_face in raw_faces:
                conf = float(raw_face[-1])
                if conf < active_conf_thresh:
                    continue

                box = raw_face[0:4]
                bx, by, bw, bh = float(box[0]), float(box[1]), float(box[2]), float(box[3])

                # Rescale coordinates to original image dimensions
                orig_bx = bx / scale if scale != 1.0 else bx
                orig_by = by / scale if scale != 1.0 else by
                orig_bw = bw / scale if scale != 1.0 else bw
                orig_bh = bh / scale if scale != 1.0 else bh

                # 1. Minimum dimension filter
                if orig_bw < MIN_FACE_DIMENSION or orig_bh < MIN_FACE_DIMENSION:
                    continue

                # 2. Aspect ratio filter (human faces are roughly 0.55 <= H/W <= 2.0)
                aspect_ratio = orig_bh / orig_bw if orig_bw > 0 else 0.0
                if aspect_ratio < 0.55 or aspect_ratio > 2.0:
                    continue

                # 3. Relative area filter (reject microscopic artifacts on massive photos)
                rel_area = (orig_bw * orig_bh) / (orig_w * orig_h)
                if rel_area < 0.00015:
                    continue

                # 4. Landmark geometry check
                # YuNet landmarks: re (4,5), le (6,7), nt (8,9), rc (10,11), lc (12,13)
                re_x, re_y = float(raw_face[4]), float(raw_face[5])
                le_x, le_y = float(raw_face[6]), float(raw_face[7])
                nt_x, nt_y = float(raw_face[8]), float(raw_face[9])
                rc_x, rc_y = float(raw_face[10]), float(raw_face[11])
                lc_x, lc_y = float(raw_face[12]), float(raw_face[13])

                # Rescale landmarks
                landmarks = [
                    (round(re_x / scale, 2), round(re_y / scale, 2)),
                    (round(le_x / scale, 2), round(le_y / scale, 2)),
                    (round(nt_x / scale, 2), round(nt_y / scale, 2)),
                    (round(rc_x / scale, 2), round(rc_y / scale, 2)),
                    (round(lc_x / scale, 2), round(lc_y / scale, 2)),
                ]

                eye_dist = np.hypot(le_x - re_x, le_y - re_y)
                if eye_dist < 5.0:
                    continue

                # Vertical order check: nose tip should roughly lie between eyes and mouth
                mean_eye_y = (re_y + le_y) / 2.0
                mean_mouth_y = (rc_y + lc_y) / 2.0
                if not (mean_eye_y - 8.0 <= nt_y <= mean_mouth_y + 12.0):
                    continue

                # 5. Face alignment and feature extraction using SFace
                aligned_face = self._recognizer.alignCrop(det_img, raw_face)
                if aligned_face is None or aligned_face.shape[:2] != (112, 112):
                    continue

                # Sharpness estimation on aligned crop
                gray_aligned = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2GRAY)
                lap_var = float(cv2.Laplacian(gray_aligned, cv2.CV_64F).var())
                if lap_var < MIN_SHARPNESS_VAR:
                    # Severely blurred / unusable face
                    continue

                # Compute normalized embedding
                feature = self._recognizer.feature(aligned_face)
                feature_flat = feature.flatten().astype(np.float32)
                norm = np.linalg.norm(feature_flat)
                if norm < 1e-6:
                    continue
                feature_flat = feature_flat / norm

                # Composite face quality metric [0.0 - 1.0]
                # Balance: confidence (40%), sharpness (35%), resolution (25%)
                s_conf = conf
                s_sharp = min(1.0, lap_var / 120.0)
                s_res = min(1.0, min(orig_bw, orig_bh) / 112.0)
                face_quality = round(0.40 * s_conf + 0.35 * s_sharp + 0.25 * s_res, 3)

                candidate_faces.append(
                    DetectedFace(
                        box_x=round(orig_bx, 2),
                        box_y=round(orig_by, 2),
                        box_w=round(orig_bw, 2),
                        box_h=round(orig_bh, 2),
                        confidence=round(conf, 3),
                        face_quality=face_quality,
                        landmarks=landmarks,
                        embedding=feature_flat.tobytes(),
                        embedding_vec=feature_flat,
                    )
                )

            # Filter duplicate / overlapping detections of the same face
            valid_faces = filter_duplicate_detections(candidate_faces)
            return valid_faces

        except Exception as err:
            logger.warning("YuNet face detection failed on %s: %s", p.name, err)
            return []

    def match_against_known_persons(
        self,
        detected_embedding: np.ndarray,
        known_person_embeddings: List[Tuple[int, np.ndarray, bool]],  # (person_id, embedding, is_reference)
        confirmed_threshold: float = CONFIRMED_MATCH_THRESHOLD,
        possible_threshold: float = POSSIBLE_MATCH_THRESHOLD,
        min_margin: float = MIN_MARGIN_THRESHOLD,
    ) -> Tuple[Optional[int], float, str]:
        """
        Compares detected face embedding against known person reference embeddings using SFace cosine metric.
        Evaluates best similarity per person and requires a margin over the second best candidate to prevent false identity linking.

        Outcomes:
        - 'CONFIRMED': High similarity (>= confirmed_threshold) with required margin.
        - 'POSSIBLE': Moderate similarity (>= possible_threshold) or close competition. Request user review.
        - 'UNKNOWN': Below possible threshold. Left unassigned.

        Returns: (matched_person_id, best_similarity, outcome_grade)
        """
        if not known_person_embeddings or detected_embedding is None:
            return None, 0.0, "UNKNOWN"

        det_norm = np.linalg.norm(detected_embedding)
        if det_norm < 1e-6:
            return None, 0.0, "UNKNOWN"
        det_vec = detected_embedding / det_norm

        # Group similarities by person_id (evaluating multiple reference embeddings per person)
        person_similarities: dict[int, List[float]] = {}
        for item in known_person_embeddings:
            pid = item[0]
            emb = item[1]
            k_norm = np.linalg.norm(emb)
            if k_norm < 1e-6:
                continue
            k_vec = emb / k_norm
            sim = float(np.dot(det_vec, k_vec))
            if pid not in person_similarities:
                person_similarities[pid] = []
            person_similarities[pid].append(sim)

        if not person_similarities:
            return None, 0.0, "UNKNOWN"

        # Calculate best similarity per candidate person
        best_scores: List[Tuple[int, float]] = []
        for pid, sims in person_similarities.items():
            best_scores.append((pid, max(sims)))

        best_scores.sort(key=lambda x: x[1], reverse=True)
        top_pid, top_sim = best_scores[0]
        second_sim = best_scores[1][1] if len(best_scores) > 1 else -1.0
        margin = top_sim - second_sim if second_sim >= 0.0 else 1.0

        if top_sim >= confirmed_threshold and margin >= min_margin:
            grade = "CONFIRMED"
            matched_id = top_pid
        elif top_sim >= possible_threshold:
            grade = "POSSIBLE"
            matched_id = top_pid
        else:
            grade = "UNKNOWN"
            matched_id = None

        return matched_id, round(max(0.0, top_sim), 3), grade

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        n1 = np.linalg.norm(emb1)
        n2 = np.linalg.norm(emb2)
        if n1 < 1e-6 or n2 < 1e-6:
            return 0.0
        return float(np.dot(emb1 / n1, emb2 / n2))

    def extract_face_crop(
        self,
        image_path: Path | str,
        box_x: float,
        box_y: float,
        box_w: float,
        box_h: float,
        margin_ratio: float = 0.20,
        target_size: int = 160,
    ) -> Optional[bytes]:
        """
        Extracts a clean, centered face crop with margin and returns encoded JPEG bytes.
        Allows users to inspect the exact detected face rather than the entire photo.
        """
        p = Path(image_path).resolve()
        if not p.is_file():
            return None

        try:
            from PIL import Image
            with Image.open(p) as img:
                img_w, img_h = img.size

                mx = box_w * margin_ratio
                my = box_h * margin_ratio

                crop_x1 = max(0, int(box_x - mx))
                crop_y1 = max(0, int(box_y - my))
                crop_x2 = min(img_w, int(box_x + box_w + mx))
                crop_y2 = min(img_h, int(box_y + box_h + my))

                if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                    return None

                cropped = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                cropped.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                cropped.convert("RGB").save(buf, format="JPEG", quality=90)
                return buf.getvalue()
        except Exception as err:
            logger.debug("Failed to extract face crop from %s: %s", p.name, err)
            return None
