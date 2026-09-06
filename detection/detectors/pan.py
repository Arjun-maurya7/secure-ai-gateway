import re

from schemas.base import BaseDetector
from schemas.detection import Entity


PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"
)


class PANDetector(BaseDetector):

    def detect(self, text: str) -> list[Entity]:

        entities = []

        for match in PAN_PATTERN.finditer(text):

            entities.append(
                Entity(
                    type="PAN",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.99,
                )
            )

        return entities