import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

# Matches http/https URL candidates while excluding illegal URI whitespace/delimiters
URL_RAW_PATTERN = re.compile(
    r"https?://[^\s<>\"'{}|\\^`]+",
    re.IGNORECASE
)

# Common sentence-ending punctuation that shouldn't be included in the URL token
TRAILING_PUNCTUATION = ".,;:!?)\"'}]>"

URL_CONTEXT_KEYWORDS = {
    "url", "link", "website", "endpoint", "api", "portal", "http",
    "https", "web", "site", "domain", "address", "uri", "href"
}


class URLDetector(BaseDetector):
    """Detects HTTP and HTTPS URLs.

    Assumptions & Quality Rules:
    - Only valid HTTP and HTTPS schemes are detected (Phase 1 scope).
    - Trailing sentence punctuation (e.g. '.', ',', ')') is cleanly detached
      while preserving the exact character slice in the original text.
    - Values are preserved as they appear in source text with zero normalization.
    - Confidence is context-aware based on surrounding web/API terms and URL complexity.
    """

    def calculate_confidence(self, url: str, text: str, start: int, end: int) -> float:
        score = 0.85

        # URLs with paths, queries, or ports are distinctive technical endpoints
        if any(c in url for c in ["/", "?", "&", ":", "#"]):
            score += 0.05

        if has_context_keywords(text, start, end, URL_CONTEXT_KEYWORDS):
            score += 0.09

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in URL_RAW_PATTERN.finditer(text):
            raw_val = match.group()
            val = raw_val.rstrip(TRAILING_PUNCTUATION)

            if not val or len(val) <= 8:  # Shorter than 'http://a'
                continue

            # Ensure there is a domain/host portion after the scheme
            scheme_end = val.find("://") + 3
            host_part = val[scheme_end:].split("/")[0].split("?")[0].split(":")[0]
            if not host_part or len(host_part) < 2:
                continue

            start = match.start()
            end = start + len(val)
            confidence = self.calculate_confidence(val, text, start, end)

            entities.append(
                Entity(
                    type="URL",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities
