import re
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.validators.ip import is_valid_ipv4
from detection.context import has_context_keywords

# Boundary checking: not preceded by alphanumeric/dot, not followed by digit or dot-digit
IPV4_PATTERN = re.compile(
    r"(?<![A-Za-z0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?!\d)(?!\.\d)"
)

IP_CONTEXT_KEYWORDS = {
    "ip", "ipv4", "address", "host", "server", "dns", "gateway",
    "router", "subnet", "proxy", "client", "network", "destination", "source"
}


class IPDetector(BaseDetector):
    """Detects IPv4 addresses.

    Scope & Assumptions:
    - Scope: Canonical dot-decimal IPv4 addresses (Phase 1 scope; IPv6 is deferred to Phase 2).
    - Octets are strictly validated to fall within 0-255 with no invalid leading zeros via is_valid_ipv4.
    - Boundaries ensure partial versions (e.g. 1.2.3.4.5 or 192.168.1.1000) are not matched.
    - Context-aware confidence awards higher confidence (0.95-0.99) when surrounded by networking terms.
    """

    def calculate_confidence(self, ip_str: str, text: str, start: int, end: int) -> float:
        score = 0.85

        if has_context_keywords(text, start, end, IP_CONTEXT_KEYWORDS):
            score += 0.10

        # Known standard private/loopback prefixes
        if ip_str.startswith(("10.", "192.168.", "127.", "172.")):
            score += 0.04

        return min(round(score, 2), 0.99)

    def detect(self, text: str) -> list[Entity]:
        entities = []

        for match in IPV4_PATTERN.finditer(text):
            val = match.group()

            # Technical validation: must be valid IPv4 octets (0-255)
            if not is_valid_ipv4(val):
                continue

            start = match.start()
            end = match.end()
            confidence = self.calculate_confidence(val, text, start, end)

            entities.append(
                Entity(
                    type="IP",
                    value=val,
                    start=start,
                    end=end,
                    confidence=confidence,
                )
            )

        return entities
