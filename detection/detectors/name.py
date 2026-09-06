import re

from schemas.base import BaseDetector
from schemas.detection import Entity


NAME_PATTERN = re.compile(
    r"\b(?:My name is|I am|I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)


class NameDetector(BaseDetector):

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in NAME_PATTERN.finditer(text):
            name = match.group(1)

            start = match.start(1)
            end = match.end(1)

            entities.append(
                Entity(
                    type="NAME",
                    value=name,
                    start=start,
                    end=end,
                    confidence=0.90
                )
            )

        return entities