import re

from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.validators.pan import is_valid_pan
from detection.context import has_context_keywords

PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"
)

PAN_CONTEXT_KEYWORDS = {
    "pan", "pancard", "tax", "income", "it", "taxpayer", "permanent",
    "nsdl", "uti", "tds", "account", "no", "number"
}


class PANDetector(BaseDetector):

    def calculate_confidence(self, pan: str, text: str, start: int, end: int) -> float:
        score = 0.80

        # Individual taxpayer PAN (4th character 'P')
        if len(pan) >= 4 and pan[3] == "P":
            score += 0.05

        if has_context_keywords(text, start, end, PAN_CONTEXT_KEYWORDS):
            score += 0.14

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in PAN_PATTERN.finditer(text):
            pan = match.group()

            if not is_valid_pan(pan):
                continue

            start = match.start()
            end = match.end()
            confidence = self.calculate_confidence(pan, text, start, end)

            entities.append(
                Entity(
                    type="PAN",
                    value=pan,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities