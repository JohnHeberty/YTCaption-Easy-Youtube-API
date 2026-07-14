"""InsightFace embedding extraction for IP-Adapter FaceID.

Extracts 512-d face identity embeddings from the original image.
These embeddings are passed to SE8 to guide IP-Adapter FaceID
conditioning, preserving the person's identity during inpainting.
"""
from __future__ import annotations

import numpy as np

from common.log_utils import get_logger

logger = get_logger(__name__)

_insightface_app = None


def _get_insightface_app():
    """Lazy-load InsightFace FaceAnalysis (buffalo_l model)."""
    global _insightface_app
    if _insightface_app is not None:
        return _insightface_app
    try:
        import insightface
        _insightface_app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        _insightface_app.prepare(ctx_id=0, det_size=(640, 640))
        logger.info("InsightFace buffalo_l loaded successfully")
    except ImportError:
        logger.warning("insightface not installed — FaceID unavailable")
        return None
    except Exception as exc:
        logger.warning("InsightFace load failed: %s", exc)
        return None
    return _insightface_app


def extract_faceid_embedding(
    orig_img: np.ndarray,
    person_binary: np.ndarray | None = None,
) -> list[list[float]] | None:
    """Extract the primary face embedding from an image.

    Args:
        orig_img: BGR image (uint8 numpy array).
        person_binary: Optional person mask. If provided, only faces
            inside the person region are considered.

    Returns:
        Nested list [[512 floats]] suitable for SE8 FaceID payload,
        or None if no face detected / InsightFace unavailable.
    """
    app = _get_insightface_app()
    if app is None:
        return None

    try:
        faces = app.get(orig_img)
    except Exception as exc:
        logger.warning("InsightFace detection failed: %s", exc)
        return None

    if not faces:
        logger.warning("InsightFace: no faces detected")
        return None

    # If person mask provided, prefer face inside person region
    if person_binary is not None and len(faces) > 1:
        h, w = person_binary.shape[:2]
        best_face = None
        best_area = 0
        for face in faces:
            bx1, by1, bx2, by2 = face.bbox.astype(int)
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w, bx2), min(h, by2)
            face_region = person_binary[by1:by2, bx1:bx2]
            if face_region.size > 0:
                overlap = (face_region > 127).sum()
                if overlap > best_area:
                    best_area = overlap
                    best_face = face
        if best_face is not None:
            faces = [best_face]

    # Pick largest face (by bbox area)
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    # normed_embedding is 512-d float32
    embedding = face.normed_embedding
    if embedding is None:
        logger.warning("InsightFace: no embedding for best face")
        return None

    # Convert to pure Python floats for JSON serialization
    return [[float(v) for v in embedding.astype(np.float32)]]


def extract_face_bbox(
    orig_img: np.ndarray,
    person_binary: np.ndarray | None = None,
) -> tuple[int, int, int, int] | None:
    """Extract the primary face bounding box (x1, y1, x2, y2).

    Used for face crop reference in IP-Adapter if needed.
    """
    app = _get_insightface_app()
    if app is None:
        return None

    try:
        faces = app.get(orig_img)
    except Exception as e:
        logger.debug("Face extraction failed: %s", e)
        return None

    if not faces:
        return None

    if person_binary is not None and len(faces) > 1:
        h, w = person_binary.shape[:2]
        best_face = None
        best_area = 0
        for face in faces:
            bx1, by1, bx2, by2 = face.bbox.astype(int)
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w, bx2), min(h, by2)
            face_region = person_binary[by1:by2, bx1:bx2]
            if face_region.size > 0:
                overlap = (face_region > 127).sum()
                if overlap > best_area:
                    best_area = overlap
                    best_face = face
        if best_face is not None:
            faces = [best_face]

    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return tuple(face.bbox.astype(int))


def extract_all_faceid_embeddings(
    orig_img: np.ndarray,
    person_binary: np.ndarray | None = None,
) -> list[tuple[list[list[float]], tuple[int, int, int, int]]]:
    """Extract FaceID embeddings for ALL detected faces.

    Returns list of (embedding, bbox) tuples, sorted by face area descending.
    Each embedding is [[float, ...]] (512-d). Bbox is (x1, y1, x2, y2).
    """
    app = _get_insightface_app()
    if app is None:
        return []

    try:
        faces = app.get(orig_img)
    except Exception as e:
        logger.debug("FaceID extraction failed: %s", e)
        return []

    if not faces:
        return []

    results = []
    for face in sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True):
        embedding = face.normed_embedding
        if embedding is not None:
            emb = [[float(v) for v in embedding.astype(np.float32)]]
            bbox = tuple(face.bbox.astype(int))
            results.append((emb, bbox))

    return results
