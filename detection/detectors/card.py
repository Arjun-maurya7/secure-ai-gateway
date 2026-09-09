import re
from schemas.base import BaseDetector
from schemas.detection import Entity


CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[- ]?){3}\d{4}\b"
)


class CardDetector(BaseDetector):

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in CARD_PATTERN.finditer(text):
            entities.append(
                Entity(
                    type="CARD",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                )
            )

        return entities