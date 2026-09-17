import re


def extract_surrounding_context(text: str, start: int, end: int, window: int = 50) -> str:
    """Extract surrounding text around an entity within a given window size (excluding the entity itself)."""
    window_start = max(0, start - window)
    window_end = min(len(text), end + window)

    before = text[window_start:start].lower()
    after = text[end:window_end].lower()

    return f"{before} {after}"


def has_context_keywords(
    text: str,
    start: int,
    end: int,
    keywords: set[str],
    window: int = 50
) -> bool:
    """Check if any of the given keywords appear in the surrounding context window."""
    surrounding = extract_surrounding_context(text, start, end, window)
    words = set(re.findall(r"\b[a-z0-9_-]+\b", surrounding))
    if words & keywords:
        return True

    # Support phrases or terms with special punctuation (e.g. 'a/c', 'api key', 'account number')
    for kw in keywords:
        if (" " in kw or "/" in kw or "-" in kw) and kw in surrounding:
            return True

    return False
