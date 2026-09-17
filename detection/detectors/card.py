import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.validators.card import is_valid_card
from detection.context import has_context_keywords

CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[- ]?){3}\d{4}\b"
)

CARD_CONTEXT_KEYWORDS = {
    "card", "credit", "debit", "visa", "mastercard", "amex", "rupay",
    "cvv", "expiry", "exp", "payment", "atm", "cc", "bank"
}


class CardDetector(BaseDetector):

    def calculate_confidence(self, card_number: str, text: str, start: int, end: int) -> float:
        score = 0.75  # Passed Luhn algorithm checksum

        clean_digits = "".join(filter(str.isdigit, card_number))
        # Known major card brand prefixes
        if clean_digits.startswith("4"):  # Visa
            score += 0.10
        elif clean_digits[:2] in {"51", "52", "53", "54", "55"} or (clean_digits[:4].isdigit() and 2221 <= int(clean_digits[:4]) <= 2720):  # Mastercard
            score += 0.10
        elif clean_digits[:2] in {"34", "37"}:  # Amex
            score += 0.10
        elif clean_digits[:2] in {"60", "65"} or clean_digits.startswith("508"):  # RuPay / Discover
            score += 0.10

        if has_context_keywords(text, start, end, CARD_CONTEXT_KEYWORDS):
            score += 0.10

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in CARD_PATTERN.finditer(text):
            card_number = match.group()

            if not is_valid_card(card_number):
                continue

            start = match.start()
            end = match.end()
            confidence = self.calculate_confidence(card_number, text, start, end)

            entities.append(
                Entity(
                    type="CARD",
                    value=card_number,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities