from pydantic import BaseModel, Field

class Entity(BaseModel):
    type: str
    value: str
    start: int
    end: int
    confidence: float = Field(ge=0.0, le=1.0)

class DetectionResponse(BaseModel):
    entities: list[Entity]