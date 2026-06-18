import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from clothes_segmentation.core.segmentor import ClothesSegmentor
from clothes_segmentation.schemas.models import SegmentResponse, HealthResponse

app = FastAPI(title="Clothes Segmentation API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
segmentor: ClothesSegmentor = None
executor = ThreadPoolExecutor(max_workers=2)


@app.on_event("startup")
async def startup():
    global segmentor
    print("Loading Grounded-SAM-2 models...")
    t0 = time.time()
    segmentor = ClothesSegmentor(project_root=PROJECT_ROOT)
    print(f"Models loaded in {time.time() - t0:.1f}s")


@app.post("/segment")
async def segment_clothes(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return {"error": "Only JPG and PNG images accepted"}

    contents = await file.read()
    loop = __import__("asyncio").get_running_loop()
    result = await loop.run_in_executor(executor, segmentor.segment, contents)

    if not result["detected"]:
        return {"message": "No clothing items detected", "objects": []}

    return {
        "message": f"Detected {len(result['objects'])} clothing items",
        "objects": result["objects"],
        "mask_image": result.get("mask_image")
    }


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": segmentor is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=1, loop="asyncio")
