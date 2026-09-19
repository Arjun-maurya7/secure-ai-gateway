import re

from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

PHONE_PATTERN = re.compile(
    r"(?<!\d)[6-9]\d{9}(?!\d)"
)

PHONE_CONTEXT_KEYWORDS = {
    "phone", "mobile", "call", "cell", "tel", "contact", "ph", "sms",
    "whatsapp", "dial", "reach", "telephone", "helpline", "no", "number"
}


class PhoneDetector(BaseDetector):

    def calculate_confidence(self, phone: str, text: str, start: int, end: int) -> float:
        score = 0.70

        if has_context_keywords(text, start, end, PHONE_CONTEXT_KEYWORDS):
            score += 0.28

        prefix_window = text[max(0, start - 5):start].strip()
        if prefix_window.endswith(("+91", "0", "+91-", "91-")):
            score += 0.01

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in PHONE_PATTERN.finditer(text):
            value = match.group()
            start = match.start()
            end = match.end()
            confidence = self.calculate_confidence(value, text, start, end)

            entities.append(
                Entity(
                    type="PHONE",
                    value=value,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities