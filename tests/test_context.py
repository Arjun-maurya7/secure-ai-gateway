from detection.context import extract_surrounding_context, has_context_keywords


def test_extract_surrounding_context():
    text = "Please call my phone number 9876543210 for details."
    # 9876543210 is at index 28 to 38
    start = 28
    end = 38
    context = extract_surrounding_context(text, start, end, window=20)

    assert "phone number" in context
    assert "for details" in context
    assert "9876543210" not in context


def test_has_context_keywords_found():
    text = "My phone number is 9876543210."
    keywords = {"phone", "mobile", "call"}
    assert has_context_keywords(text, 19, 29, keywords) is True


def test_has_context_keywords_not_found():
    text = "The transaction reference is 9876543210."
    keywords = {"phone", "mobile", "call"}
    assert has_context_keywords(text, 29, 39, keywords) is False
