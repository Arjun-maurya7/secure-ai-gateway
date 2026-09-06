import re

from schemas.base import BaseDetector
from schemas.detection import Entity

PHONE_PATTERN = re.compile(
    r"(?<!\d)[6-9]\d{9}(?!\d)"
)


class PhoneDetector(BaseDetector):

    def detect(self, text: str) -> list[Entity]:

        entities = []

        for match in PHONE_PATTERN.finditer(text):

            entities.append(
                Entity(
                    type="PHONE",
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.98,
                )
            )

        return entities