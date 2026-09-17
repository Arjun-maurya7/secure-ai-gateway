from fastapi import FastAPI, HTTPException
from detection.engine import DetectionEngine
from schemas.request import DetectionRequest
from schemas.detection import DetectionResponse
from redaction.engine import RedactionEngine
from schemas.redaction import RedactionResponse
from policy.engine import PolicyEngine

app = FastAPI()
engine = DetectionEngine()
redaction_engine = RedactionEngine()
policy_engine = PolicyEngine()

@app.post("/v1/scan", response_model=DetectionResponse)
def scan(request: DetectionRequest):
    entities = engine.detect(request.text)
    return {
        "entities": entities
    }
    
@app.post("/v1/redact", response_model=RedactionResponse)
def redact(request: DetectionRequest):
    entities = engine.detect(request.text)

    redacted_entities = []

    for entity in entities:
        action = policy_engine.get_action(entity.type)

        if action.value == "BLOCK":
            raise HTTPException(
                status_code=403,
                detail=f"Request blocked because it contains {entity.type}"
            )

        if action.value == "REDACT":
            redacted_entities.append(entity)

    sanitized_text = redaction_engine.redact(
        request.text,
        redacted_entities
    )

    return {
        "sanitized_text": sanitized_text,
        "entities": entities
    }