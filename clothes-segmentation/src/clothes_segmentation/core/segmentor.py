import sys
import cv2
import numpy as np
import torch
import supervision as sv
from pathlib import Path
from PIL import Image


class ClothesSegmentor:

    CLASSES = [
        'hat', 'sunglasses', 'shirt', 'blouse', 'jacket',
        'sweater', 'blazer', 'cardigan', 'handbag', 'skirt',
        'pants', 'dress', 'shoes', 'boots', 'slippers'
    ]
    BOX_THRESHOLD = 0.10
    TEXT_THRESHOLD = 0.10

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self._setup_paths()
        self._load_models()

    def _setup_paths(self):
        self.checkpoints_dir = self.project_root / "checkpoints"
        self.gd_repo = self.project_root / "external" / "GroundingDINO"
        self.sam2_repo = self.project_root / "external" / "segment-anything-2"
        sys.path.insert(0, str(self.gd_repo))
        sys.path.insert(0, str(self.sam2_repo))

    def _load_models(self):
        from groundingdino.util.inference import Model
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        gd_config = self.gd_repo / "groundingdino" / "config" / "GroundingDINO_SwinT_OGC.py"
        gd_checkpoint = self.checkpoints_dir / "groundingdino_swint_ogc.pth"
        self.gd_model = Model(
            model_config_path=str(gd_config),
            model_checkpoint_path=str(gd_checkpoint),
            device="cpu"
        )

        sam2_checkpoint = self.checkpoints_dir / "sam2_hiera_tiny.pt"
        config_path = self.sam2_repo / "sam2" / "configs" / "sam2" / "sam2_hiera_t.yaml"
        sam2_model = build_sam2(
            str(config_path), str(sam2_checkpoint),
            device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
            apply_postprocessing=False
        )
        self.sam2_predictor = SAM2ImagePredictor(sam2_model)

    @staticmethod
    def _is_inside(box1, box2):
        x1, y1, x2, y2 = box1
        x1i, y1i, x2i, y2i = box2
        return x1 >= x1i and y1 >= y1i and x2 <= x2i and y2 <= y2i

    def segment(self, image_bytes: bytes) -> dict:
        import io
        img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        height, width, _ = original_image.shape
        image_area = height * width

        detections = self.gd_model.predict_with_classes(
            image=original_image,
            classes=self.CLASSES,
            box_threshold=self.BOX_THRESHOLD,
            text_threshold=self.TEXT_THRESHOLD
        )

        area_filtered = detections[(detections.area / image_area) < 0.29]

        filtered_boxes, filtered_confidences, filtered_class_ids = [], [], []
        for i, box1 in enumerate(area_filtered.xyxy):
            is_inside = False
            for j, box2 in enumerate(area_filtered.xyxy):
                if i != j and self._is_inside(box1, box2):
                    is_inside = True
                    break
            if not is_inside:
                filtered_boxes.append(box1)
                filtered_confidences.append(area_filtered.confidence[i])
                filtered_class_ids.append(area_filtered.class_id[i])

        final_detections = sv.Detections(
            xyxy=np.array(filtered_boxes) if filtered_boxes else np.empty((0, 4)),
            confidence=np.array(filtered_confidences),
            class_id=np.array(filtered_class_ids),
        )

        if len(final_detections) == 0:
            return {"detected": False, "objects": [], "mask_image": None}

        result_masks = []
        for box in final_detections.xyxy:
            self.sam2_predictor.set_image(cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB))
            masks, scores, _ = self.sam2_predictor.predict(
                point_coords=None,
                point_labels=None,
                box=box[None, :],
                multimask_output=True
            )
            result_masks.append(masks[np.argmax(scores)])

        final_detections.mask = np.array(result_masks)

        mask_annotator = sv.MaskAnnotator()
        box_annotator = sv.BoxAnnotator()
        labels = [
            f"{self.CLASSES[c]} {conf:.2f}"
            for c, conf in zip(final_detections.class_id, final_detections.confidence)
        ]
        annotated = mask_annotator.annotate(scene=original_image.copy(), detections=final_detections)
        annotated = box_annotator.annotate(scene=annotated, detections=final_detections)
        for xyxy, label in zip(final_detections.xyxy, labels):
            x, y = int(xyxy[0]), int(xyxy[1])
            cv2.putText(annotated, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        detected_objects = [
            {
                "class_name": self.CLASSES[cls_id],
                "confidence": float(conf),
                "bbox": [int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])]
            }
            for cls_id, conf, xyxy in zip(
                final_detections.class_id,
                final_detections.confidence,
                final_detections.xyxy
            )
        ]

        import base64
        _, buffer = cv2.imencode(".jpg", annotated)
        mask_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        return {
            "detected": True,
            "objects": detected_objects,
            "mask_image": mask_b64
        }
