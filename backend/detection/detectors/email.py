import re

from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

COMMON_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "proton.me", "protonmail.com", "aol.com", "zoho.com", "mail.com",
}

EMAIL_CONTEXT_KEYWORDS = {
    "email", "mail", "e-mail", "contact", "reach", "send", "write", "to"
}


class EmailDetector(BaseDetector):

    def calculate_confidence(self, email: str, text: str, start: int, end: int) -> float:
        score = 0.80

        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain in COMMON_EMAIL_DOMAINS or domain.endswith((".com", ".org", ".edu", ".gov", ".in", ".co.in", ".net")):
            score += 0.10

        if has_context_keywords(text, start, end, EMAIL_CONTEXT_KEYWORDS):
            score += 0.09

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in EMAIL_PATTERN.finditer(text):
            value = match.group()
            start = match.start()
            end = match.end()
            confidence = self.calculate_confidence(value, text, start, end)

            entities.append(
                Entity(
                    type="EMAIL",
                    value=value,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities