from fastapi import FastAPI
from detection.engine import DetectionEngine
from schemas.request import DetectionRequest
from schemas.detection import DetectionResponse

app = FastAPI()
engine = DetectionEngine()


@app.post("/v1/scan", response_model=DetectionResponse)
def scan(request: DetectionRequest):
    entities = engine.detect(request.text)
    return {
        "entities": entities
    }
    
