import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

# 1. Recognizable provider-prefixed API key formats (High specificity)
KNOWN_PREFIX_PATTERNS = [
    ("OPENAI_PROJ", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b")),
    ("OPENAI_ADMIN", re.compile(r"\bsk-admin-[A-Za-z0-9_-]{20,}\b")),
    ("OPENAI_STANDARD", re.compile(r"\bsk-[A-Za-z0-9]{20,48}\b")),
    ("GITHUB", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("SLACK", re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")),
    ("STRIPE", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}\b")),
]

# 2. Generic context-assigned API key pattern (requires explicit assignment syntax)
CONTEXT_ASSIGNED_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,64})['\"]?"
)

API_KEY_CONTEXT_KEYWORDS = {
    "api", "key", "token", "secret", "auth", "authorization",
    "bearer", "credential", "password", "apikey", "access"
}


class APIKeyDetector(BaseDetector):
    """Detects API keys and secrets using conservative, highly specific patterns.

    Assumptions & Quality Rules:
    - Avoids generic alphanumeric matching that causes false-positive disasters.
    - Matches recognizable vendor-standard prefixes (OpenAI, GitHub, AWS, Stripe, Slack).
    - Supports generic keys only when accompanied by explicit assignment syntax
      (e.g., api_key = "..." or secret_key: "...").
    - Confidence distinguishes verified provider formats (0.90-0.98) from generic keys (0.80-0.88).
    """

    def calculate_confidence(self, key_val: str, text: str, start: int, end: int, is_known_prefix: bool) -> float:
        score = 0.90 if is_known_prefix else 0.80

        if has_context_keywords(text, start, end, API_KEY_CONTEXT_KEYWORDS):
            score += 0.08

        return min(round(score, 2), 0.98)

    def detect(self, text: str) -> list[Entity]:
        entities = []
        matched_spans: set[tuple[int, int]] = set()

        # Step 1: Detect known vendor-specific API key formats
        for _provider, pattern in KNOWN_PREFIX_PATTERNS:
            for match in pattern.finditer(text):
                val = match.group()
                start = match.start()
                end = match.end()

                # Guard against overlapping spans
                if (start, end) in matched_spans:
                    continue

                matched_spans.add((start, end))
                confidence = self.calculate_confidence(val, text, start, end, is_known_prefix=True)

                entities.append(
                    Entity(
                        type="API_KEY",
                        value=val,
                        start=start,
                        end=end,
                        confidence=confidence,
                    )
                )

        # Step 2: Detect context-assigned keys (e.g. api_key: "...")
        for match in CONTEXT_ASSIGNED_PATTERN.finditer(text):
            val = match.group(1)
            start = match.start(1)
            end = match.end(1)

            if (start, end) in matched_spans:
                continue

            matched_spans.add((start, end))
            confidence = self.calculate_confidence(val, text, start, end, is_known_prefix=False)

            entities.append(
                Entity(
                    type="API_KEY",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities
