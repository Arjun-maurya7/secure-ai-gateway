import re
import spacy
from schemas.base import BaseDetector
from schemas.detection import Entity
from detection.context import has_context_keywords

NAME_CONTEXT_KEYWORDS = {
    "mr", "ms", "mrs", "dr", "prof", "shri", "smt", "name",
    "customer", "user", "person", "employee", "officer", "client", "contact"
}

# Words that are commonly capitalised but are never person names.
# This exclusion list prevents false positives from the single-token fallback.
_KNOWN_NON_NAMES = {
    # Days and months
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    # Banking / generic labels that appear near context keywords
    "account", "bank", "branch", "transfer", "payment", "transaction",
    "contact", "name", "address", "email", "phone", "mobile", "number",
    "customer", "client", "user", "officer", "employee", "person",
    "india", "indian", "rupees", "inr", "usd", "amount", "total",
    # Common sentence-start verbs / connectors
    "the", "this", "please", "hello", "dear", "hi", "thanks",
    # PII field labels that spaCy sometimes tags as PERSON
    "pan", "card", "url", "api", "jwt", "ip",
}

# Regex: match text that looks like a numeric/structured token, NOT a name.
_NON_NAME_PATTERNS = [
    re.compile(r"^\d+$"),                        # pure digits (phone/card/PAN)
    re.compile(r"^[A-Z0-9]{5,}$"),              # all-caps alphanumeric (PAN, codes)
    re.compile(r"^\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}$"),  # formatted card
    re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),  # IP address
]


def _is_plausible_person_name(text: str) -> bool:
    """Return True if text could plausibly be a human name.

    Rejects:
    - Pure digit strings (phone numbers, account numbers, card numbers)
    - All-caps alphanumeric tokens (PAN, API keys)
    - Structured numeric patterns (formatted cards, IPs)
    - Known generic labels (even if spaCy tagged them as PERSON)
    """
    if not text or not text.strip():
        return False
    # Each word in a name must have at least one letter
    words = text.split()
    for word in words:
        clean = word.strip(".,;:()-")
        if not clean:
            continue
        # A name word must not be purely numeric
        if clean.isdigit():
            return False
        # A name word must not match known non-name patterns
        for pat in _NON_NAME_PATTERNS:
            if pat.match(clean):
                return False
        # A single-word candidate must not be in the known exclusion list
        if len(words) == 1 and clean.lower() in _KNOWN_NON_NAMES:
            return False
    return True

# Matches a single Title-case word (first letter upper, rest lower).
# Rules out all-caps tokens like PAN, CARD, API.
_SINGLE_NAME_RE = re.compile(r"\b([A-Z][a-z]+)\b")


class NERDetector(BaseDetector):

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def calculate_confidence(self, name: str, text: str, start: int, end: int) -> float:
        score = 0.80

        words = name.split()
        if len(words) >= 2 and all(w[0].isupper() for w in words if w):
            score += 0.10

        if has_context_keywords(text, start, end, NAME_CONTEXT_KEYWORDS):
            score += 0.05

        return min(round(score, 2), 0.99)

    def _fallback_single_token_names(self, text: str, spacy_spans: set) -> list[Entity]:
        """
        Context-aware fallback for single-token person names missed by
        spaCy's en_core_web_sm model.

        A candidate is accepted only when ALL of the following hold:
          1. It is a single Title-case word (uppercase first letter, rest lowercase).
          2. Its lowercase form is NOT in the known-non-names exclusion list.
          3. The surrounding 50-char window contains at least one name-indicator
             keyword (e.g. "contact", "mr", "customer").
          4. Its character span does not overlap any span already found by spaCy
             to avoid double-detection.
        """
        entities = []
        for m in _SINGLE_NAME_RE.finditer(text):
            word = m.group(1)
            start, end = m.start(), m.end()

            # Guard 1: skip known non-names
            if word.lower() in _KNOWN_NON_NAMES:
                continue

            # Guard 2: skip if spaCy already detected an overlapping span
            if any(s <= start < e or s < end <= e for (s, e) in spacy_spans):
                continue

            # Guard 3: require a name-indicator keyword in the nearby context
            if not has_context_keywords(text, start, end, NAME_CONTEXT_KEYWORDS):
                continue

            entities.append(Entity(
                type="NAME",
                value=word,
                start=start,
                end=end,
                confidence=0.80,
            ))

        return entities

    def detect(self, text: str) -> list[Entity]:
        entities = []
        spacy_spans: set = set()

        doc = self.nlp(text)

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                # Post-filter: reject clearly non-name tokens that spaCy
                # incorrectly labels as PERSON (digits, all-caps codes, etc.)
                if not _is_plausible_person_name(ent.text):
                    continue

                confidence = self.calculate_confidence(
                    ent.text, text, ent.start_char, ent.end_char
                )
                entities.append(Entity(
                    type="NAME",
                    value=ent.text,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=confidence,
                ))
                spacy_spans.add((ent.start_char, ent.end_char))

        # Apply fallback for single-token names spaCy's small model may have missed
        fallback = self._fallback_single_token_names(text, spacy_spans)
        entities.extend(fallback)

        return entities