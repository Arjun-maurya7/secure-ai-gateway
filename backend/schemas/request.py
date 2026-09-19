from pydantic import BaseModel


class DetectionRequest(BaseModel):
    text: str