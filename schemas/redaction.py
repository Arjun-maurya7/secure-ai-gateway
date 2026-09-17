from pydantic import BaseModel

from schemas.detection import Entity


class RedactionResponse(BaseModel):
    sanitized_text: str
    entities: list[Entity]