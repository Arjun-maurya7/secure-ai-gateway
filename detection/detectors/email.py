import re

from schemas.base import BaseDetector
from schemas.detection import Entity


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


class EmailDetector(BaseDetector):

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in EMAIL_PATTERN.finditer(text):
            entities.append(
                Entity(
                    type="EMAIL",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.99,
                )
            )

        return entities