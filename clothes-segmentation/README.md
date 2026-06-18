# Clothes Segmentation API

Grounded-SAM-2 clothing segmentation API built with FastAPI. Detects and segments 15 clothing classes from images using GroundingDINO (detection) + SAM2 tiny (segmentation).

## Quick Start

### Prerequisites
- Python 3.12.7
- Checkpoints in `checkpoints/` (~1.7 GB total):
  - `groundingdino_swint_ogc.pth` (661.8 MB)
  - `sam2_hiera_tiny.pt` (148.7 MB)
  - `sam2_hiera_large.pt` (856.4 MB)

### Install
```powershell
pip install -r requirements.txt
```

### Start Server
```powershell
$env:PYTHONPATH="src"; python -m clothes_segmentation.api.server
```

Or use the batch script:
```powershell
.\scripts\start_api.bat
```

Server starts on `http://0.0.0.0:8001` (~30s model loading time).

### Test
```powershell
python tests/test_api.py
```

## API Endpoints

### POST /segment
Upload an image for clothing segmentation.

**Request:** `multipart/form-data` with `file` field (JPG/PNG)

**Response:**
```json
{
  "message": "Detected N clothing items",
  "objects": [
    {
      "class_name": "shirt",
      "confidence": 0.85,
      "bbox": [x1, y1, x2, y2]
    }
  ],
  "mask_image": "data:image/jpeg;base64,/9j/..."
}
```

**Example:**
```python
import requests
files = {"file": open("photo.jpg", "rb")}
r = requests.post("http://localhost:8001/segment", files=files)
print(r.json())
```

### GET /health
Check server status.

**Response:**
```json
{"status": "ok", "model_loaded": true}
```

## Detected Classes
hat, sunglasses, shirt, blouse, jacket, sweater, blazer, cardigan, handbag, skirt, pants, dress, shoes, boots, slippers

## Project Structure
```
src/clothes_segmentation/   # Main package
├── api/server.py           # FastAPI server
├── core/segmentor.py       # GroundingDINO + SAM2 pipeline
└── schemas/models.py       # Pydantic models

external/                   # External repos (GroundingDINO, SAM2)
checkpoints/                # Model weights (~1.7 GB)
scripts/                    # Startup scripts
tests/                      # Test suite + images
```

## Notes
- CPU-only inference (no GPU required)
- numpy<2 required (h5py compatibility)
- Model loading takes ~30s on startup
- Inference time varies by image size (CPU mode)
