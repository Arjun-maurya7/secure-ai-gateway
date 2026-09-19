import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

# Standard JWT tokens: header starts with 'eyJ' (base64url of '{"') and has 3 dot-separated parts
JWT_STANDARD_PATTERN = re.compile(
    r"\b(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b"
)

# Generic 3-part Base64URL token (requires explicit context to avoid false positives)
JWT_GENERIC_PATTERN = re.compile(
    r"\b([A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,})\b"
)

JWT_CONTEXT_KEYWORDS = {
    "jwt", "token", "bearer", "authorization", "auth", "id_token",
    "access_token", "claims", "header", "signature", "oauth", "sso"
}


class JWTDetector(BaseDetector):
    """Detects structural JSON Web Tokens (JWT) based on three Base64URL-encoded segments.

    Assumptions & Quality Rules:
    - Identifies structural token layout: header.payload.signature.
    - Does NOT cryptographically verify token signature, integrity, or expiration.
    - Distinguishes canonical 'eyJ'-prefixed tokens (standard base64url JSON header)
      from arbitrary dot-separated strings (which require strict JWT context).
    - Confidence reflects structural match precision and surrounding auth/token context.
    """

    def calculate_confidence(self, token_val: str, text: str, start: int, end: int, is_canonical: bool) -> float:
        score = 0.90 if is_canonical else 0.75

        if has_context_keywords(text, start, end, JWT_CONTEXT_KEYWORDS):
            score += 0.08

        return min(round(score, 2), 0.98)

    def detect(self, text: str) -> list[Entity]:
        entities = []
        matched_spans: set[tuple[int, int]] = set()

        # Step 1: Detect canonical JWT tokens (header starting with 'eyJ')
        for match in JWT_STANDARD_PATTERN.finditer(text):
            val = match.group(1)
            start = match.start(1)
            end = match.end(1)

            matched_spans.add((start, end))
            confidence = self.calculate_confidence(val, text, start, end, is_canonical=True)

            entities.append(
                Entity(
                    type="JWT",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        # Step 2: Detect generic 3-part base64 tokens ONLY when backed by JWT context
        for match in JWT_GENERIC_PATTERN.finditer(text):
            val = match.group(1)
            start = match.start(1)
            end = match.end(1)

            if (start, end) in matched_spans:
                continue

            # Context requirement: Avoid treating arbitrary triple-dotted strings as tokens
            if not has_context_keywords(text, start, end, JWT_CONTEXT_KEYWORDS):
                continue

            matched_spans.add((start, end))
            confidence = self.calculate_confidence(val, text, start, end, is_canonical=False)

            entities.append(
                Entity(
                    type="JWT",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities
