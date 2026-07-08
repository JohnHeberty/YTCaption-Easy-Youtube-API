"""Geometry and annotation helpers for segmentation."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
import supervision as sv


def is_inside(box1: Any, box2: Any) -> bool:
    """Check if box1 is completely inside box2."""
    x1, y1, x2, y2 = box1
    x1i, y1i, x2i, y2i = box2
    return x1 >= x1i and y1 >= y1i and x2 <= x2i and y2 <= y2i


def annotate_detections(
    original_image: np.ndarray,
    final_detections: sv.Detections,
    detector: str,
    classes: list[str],
) -> np.ndarray:
    """Build annotated image with masks and labels."""
    from app.services.segformer_detector import CLOTHING_IDS

    mask_annotator = sv.MaskAnnotator()
    box_annotator = sv.BoxAnnotator()
    labels = []
    for cls_id, conf in zip(final_detections.class_id, final_detections.confidence):
        if detector in ("yolo11", "ensemble") and cls_id == 0:
            labels.append(f"person {conf:.2f}")
        elif detector in ("segformer",) or (detector == "ensemble" and cls_id in CLOTHING_IDS):
            from app.services.segformer_detector import LABELS as SEGLABELS
            label = SEGLABELS[cls_id] if cls_id < len(SEGLABELS) else f"class_{cls_id}"
            labels.append(f"{label} {conf:.2f}")
        elif cls_id < len(classes):
            labels.append(f"{classes[cls_id]} {conf:.2f}")
        else:
            labels.append(f"class_{cls_id} {conf:.2f}")
    annotated = mask_annotator.annotate(scene=original_image.copy(), detections=final_detections)
    annotated = box_annotator.annotate(scene=annotated, detections=final_detections)
    for xyxy, label in zip(final_detections.xyxy, labels):
        x, y = int(xyxy[0]), int(xyxy[1])
        cv2.putText(annotated, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return annotated


def build_detected_objects(
    final_detections: sv.Detections,
    detector: str,
    classes: list[str],
    image_area: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build detected_objects list and binary masks from detections."""
    import base64

    from app.services.segformer_detector import CLOTHING_IDS

    areas = final_detections.area if len(final_detections) > 0 else np.array([])
    detected_objects: list[dict[str, Any]] = []
    binary_masks: list[str] = []

    for i, (cls_id, conf, xyxy) in enumerate(zip(
        final_detections.class_id, final_detections.confidence, final_detections.xyxy,
    )):
        if detector == "segformer" or (detector == "ensemble" and cls_id in CLOTHING_IDS):
            from app.services.segformer_detector import LABELS as SEGLABELS
            class_name = SEGLABELS[cls_id] if cls_id < len(SEGLABELS) else f"class_{cls_id}"
        elif cls_id < len(classes):
            class_name = classes[cls_id]
        else:
            class_name = f"class_{cls_id}"
        detected_objects.append({
            "class_name": class_name,
            "confidence": round(float(conf), 4),
            "bbox": [int(b) for b in xyxy],
            "area_pct": round(float(areas[i] / image_area) * 100, 2),
        })

    if final_detections.mask is not None:
        for mask_arr in final_detections.mask:
            mask_uint8 = (mask_arr.astype(np.uint8)) * 255
            _, mask_buffer = cv2.imencode(".png", mask_uint8)
            binary_masks.append(f"data:image/png;base64,{base64.b64encode(mask_buffer).decode('utf-8')}")

    return detected_objects, binary_masks


def filter_detections(
    detections: sv.Detections,
    detector: str,
    max_area_pct: float,
    image_area: int,
    max_objects: int,
    has_masks: bool,
) -> sv.Detections:
    """Filter detections by area, nesting, and cap to max_objects."""
    from app.services.segformer_detector import CLOTHING_IDS

    area_filtered = detections[(detections.area / image_area) < max_area_pct]

    filtered_boxes: list[Any] = []
    filtered_confidences: list[Any] = []
    filtered_class_ids: list[Any] = []
    filtered_masks: list[Any] = []
    has_mask_data = area_filtered.mask is not None

    if (detector == "segformer" or (detector == "ensemble" and has_mask_data and
            len(area_filtered) > 0 and area_filtered.class_id[0] in CLOTHING_IDS)) and has_mask_data:
        for i in range(len(area_filtered)):
            filtered_boxes.append(area_filtered.xyxy[i])
            filtered_confidences.append(area_filtered.confidence[i])
            filtered_class_ids.append(area_filtered.class_id[i])
            filtered_masks.append(area_filtered.mask[i])
    else:
        for i, box1 in enumerate(area_filtered.xyxy):
            inside = False
            for j, box2 in enumerate(area_filtered.xyxy):
                if i != j and is_inside(box1, box2):
                    inside = True
                    break
            if not inside:
                filtered_boxes.append(box1)
                filtered_confidences.append(area_filtered.confidence[i])
                filtered_class_ids.append(area_filtered.class_id[i])
                if has_mask_data:
                    filtered_masks.append(area_filtered.mask[i])

    final = sv.Detections(
        xyxy=np.array(filtered_boxes) if filtered_boxes else np.empty((0, 4)),
        confidence=np.array(filtered_confidences),
        class_id=np.array(filtered_class_ids),
        mask=np.array(filtered_masks) if filtered_masks else None,
    )
    if len(final) > max_objects:
        top_idx = np.argsort(-final.confidence)[:max_objects]
        final = final[top_idx]
    return final
