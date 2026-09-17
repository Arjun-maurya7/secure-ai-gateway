import re

from schemas.base import BaseDetector
from schemas.detection import Entity


NAME_PATTERN = re.compile(
    r"\b(?:My name is|I am|I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)


class NameDetector(BaseDetector):

    def calculate_confidence(self, name: str, text: str, start: int, end: int) -> float:
        score = 0.85

        words = name.split()
        if len(words) >= 2:
            score += 0.05

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in NAME_PATTERN.finditer(text):
            name = match.group(1)

            start = match.start(1)
            end = match.end(1)
            confidence = self.calculate_confidence(name, text, start, end)

            entities.append(
                Entity(
                    type="NAME",
                    value=name,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities