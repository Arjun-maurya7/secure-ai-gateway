import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

ACCOUNT_PATTERN = re.compile(
    r"(?<!\d)(?:\d[- ]?){8,17}\d(?!\d)"
)

ACCOUNT_STRONG_KEYWORDS = {
    "account", "acct", "a/c", "acc", "account number", "acct no", "a/c no",
    "bank account", "savings account", "current account", "checking account"
}

ACCOUNT_GENERAL_KEYWORDS = {
    "bank", "savings", "current", "checking", "beneficiary", "deposit",
    "wire", "remittance", "iban", "bban", "routing", "ledger", "credit to"
}


class AccountDetector(BaseDetector):
    """Detects banking account numbers (typically 9-18 digits).

    Assumptions & Quality Rules:
    - Arbitrary digit sequences are not classified as account numbers unless
      supported by contextual account/banking keywords to avoid high false-positive rates
      on timestamps, tracking numbers, or order IDs.
    - Repeated single digits (e.g. 0000000000) are treated as dummy fillers and rejected.
    - Confidence is dynamic: strong account keywords yield high confidence (0.90-0.95),
      while general banking context yields moderate confidence (0.80-0.85).
    """

    def calculate_confidence(self, account_val: str, text: str, start: int, end: int) -> float:
        score = 0.70

        if has_context_keywords(text, start, end, ACCOUNT_STRONG_KEYWORDS):
            score += 0.20
        elif has_context_keywords(text, start, end, ACCOUNT_GENERAL_KEYWORDS):
            score += 0.10

        # Formatted account numbers indicate intentional structure
        if "-" in account_val or " " in account_val:
            score += 0.05

        return min(round(score, 2), 0.95)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in ACCOUNT_PATTERN.finditer(text):
            val = match.group()
            clean_digits = "".join(filter(str.isdigit, val))

            # Length validation: bank accounts are 9 to 18 digits
            if not (9 <= len(clean_digits) <= 18):
                continue

            # Reject dummy repeating digits (e.g. 0000000000)
            if len(set(clean_digits)) <= 1:
                continue

            start = match.start()
            end = match.end()

            # Precision rule: Require contextual evidence to avoid matching arbitrary numbers
            if not (
                has_context_keywords(text, start, end, ACCOUNT_STRONG_KEYWORDS)
                or has_context_keywords(text, start, end, ACCOUNT_GENERAL_KEYWORDS)
            ):
                continue

            confidence = self.calculate_confidence(val, text, start, end)

            entities.append(
                Entity(
                    type="ACCOUNT",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities
