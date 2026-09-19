from detection.detectors.email import EmailDetector
from detection.detectors.phone import PhoneDetector
from detection.detectors.pan import PANDetector
from detection.detectors.card import CardDetector
from detection.detectors.ner import NERDetector
from detection.detectors.account import AccountDetector
from detection.detectors.ip import IPDetector
from detection.detectors.url import URLDetector
from detection.detectors.api_key import APIKeyDetector
from detection.detectors.jwt import JWTDetector
from detection.engine import DetectionEngine


# ==========================================
# Email Detector Tests
# ==========================================

def test_email_detection():
    detector = EmailDetector()
    text = "My email is rahul@gmail.com."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "EMAIL"
    assert entities[0].value == "rahul@gmail.com"
    assert entities[0].start == 12
    assert entities[0].end == 27
    assert entities[0].confidence == 0.99


def test_email_detection_multiple():
    detector = EmailDetector()
    text = "Contact support@example.com or admin@bank.org for help."
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].value == "support@example.com"
    assert entities[1].value == "admin@bank.org"


def test_email_detection_no_email():
    detector = EmailDetector()
    text = "This is just some normal text with no email."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_email_confidence_context():
    detector = EmailDetector()
    with_context = detector.detect("My email is rahul@gmail.com.")
    without_context = detector.detect("Address rahul@internal.xyz sent")

    assert with_context[0].confidence == 0.99
    assert without_context[0].confidence == 0.80
    assert with_context[0].confidence > without_context[0].confidence


# ==========================================
# Phone Detector Tests
# ==========================================

def test_phone_detection():
    detector = PhoneDetector()
    text = "My phone number is 9876543210."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "PHONE"
    assert entities[0].value == "9876543210"
    assert entities[0].start == 19
    assert entities[0].end == 29
    assert entities[0].confidence == 0.98


def test_phone_detection_multiple():
    detector = PhoneDetector()
    text = "Call 9876543210 or 8765432109 immediately."
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].value == "9876543210"
    assert entities[1].value == "8765432109"


def test_phone_detection_invalid():
    detector = PhoneDetector()
    # 5 digits, digits starting with 1-5, and 12 digits
    text = "Codes: 12345, 2345678901, and 98765432101234"
    entities = detector.detect(text)
    assert len(entities) == 0

def test_phone_detection_context():
    detector = PhoneDetector()

    text_no_context = "The transaction reference is 9876543210."
    entities_no_context = detector.detect(text_no_context)

    assert len(entities_no_context) == 1
    assert entities_no_context[0].type == "PHONE"
    assert entities_no_context[0].value == "9876543210"
    assert entities_no_context[0].confidence == 0.70

    text_with_context = "My phone number is 9876543210."
    entities_with_context = detector.detect(text_with_context)
    assert entities_with_context[0].confidence == 0.98
    assert entities_with_context[0].confidence > entities_no_context[0].confidence


# ==========================================
# PAN Detector Tests
# ==========================================

def test_pan_detection():
    detector = PANDetector()
    text = "My pan no. is IKRPM7731M"
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "PAN"
    assert entities[0].value == "IKRPM7731M"
    assert entities[0].confidence == 0.99


def test_pan_confidence_context():
    detector = PANDetector()
    with_context = detector.detect("My pan no. is IKRPM7731M")
    without_context = detector.detect("Internal record IKRPM7731M processed")

    assert with_context[0].confidence == 0.99
    assert without_context[0].confidence == 0.85
    assert with_context[0].confidence > without_context[0].confidence


def test_pan_detection_invalid():
    detector = PANDetector()
    text = "Invalid PANs: 12345ABCDE, ABCDE123, and abcde1234f"
    entities = detector.detect(text)
    assert len(entities) == 0


def test_pan_detection_invalid_candidate():
    detector = PANDetector()
    # Matches candidate regex [A-Z]{5}[0-9]{4}[A-Z], but 4th char is not one of [ABCFGHLJPT]
    text = "Candidate ABCDE1234F (4th char D) and ZZZZZ9999Z (4th char Z) must be rejected."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_pan_detection_mixed_valid_and_invalid_candidates():
    detector = PANDetector()
    # IKRPM7731M has valid 4th char 'P'; ABCDE1234F has invalid 4th char 'D'
    text = "My real PAN is IKRPM7731M but not candidate ABCDE1234F."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "PAN"
    assert entities[0].value == "IKRPM7731M"


# ==========================================
# Card Detector Tests
# ==========================================

def test_card_detection_continuous():
    detector = CardDetector()
    text = "My card is 4111111111111111"
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "CARD"
    assert entities[0].value == "4111111111111111"
    assert entities[0].confidence == 0.95


def test_card_confidence_context():
    detector = CardDetector()
    with_context = detector.detect("My card is 4111111111111111")
    without_context = detector.detect("Sequence 4111111111111111 stored")

    assert with_context[0].confidence == 0.95
    assert without_context[0].confidence == 0.85
    assert with_context[0].confidence > without_context[0].confidence


def test_card_detection_formatted():
    detector = CardDetector()
    text = "Dashed: 4111-1111-1111-1111 and Spaced: 5555 5555 5555 4444"

    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].value == "4111-1111-1111-1111"
    assert entities[1].value == "5555 5555 5555 4444"


def test_card_detection_invalid():
    detector = CardDetector()
    text = "Partial card: 4111 2222 and 123456"
    entities = detector.detect(text)
    assert len(entities) == 0


def test_card_detection_invalid_candidate_luhn():
    detector = CardDetector()
    # 16-digit candidates matching regex but failing Luhn checksum
    text = "Invalid card candidates: 4111111111111112, 4111-1111-1111-1112, and 4111 1111 1111 1112"
    entities = detector.detect(text)
    assert len(entities) == 0


def test_card_detection_mixed_valid_and_invalid_candidates():
    detector = CardDetector()
    # 4111-1111-1111-1111 is Luhn-valid; 4111-1111-1111-1112 is Luhn-invalid
    text = "Valid card is 4111-1111-1111-1111 while candidate 4111-1111-1111-1112 is rejected."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "CARD"
    assert entities[0].value == "4111-1111-1111-1111"



# ==========================================
# NER Detector (spaCy) Tests
# ==========================================

def test_ner_detector_person():
    detector = NERDetector()
    text = "Barack Obama visited London last week."

    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "NAME"
    assert entities[0].value == "Barack Obama"
    assert entities[0].start == 0
    assert entities[0].end == 12
    assert entities[0].confidence == 0.90


def test_ner_detector_no_person():
    detector = NERDetector()
    text = "The weather forecast predicts light rain tomorrow afternoon."
    entities = detector.detect(text)
    assert len(entities) == 0


# ==========================================
# Detection Engine Integration Tests
# ==========================================

def test_detection_engine_multi_pii():
    engine = DetectionEngine()
    text = "Rahul Sharma (email: rahul@gmail.com, phone: 9876543210) has PAN IKRPM7731M and card 4111-1111-1111-1111."
    entities = engine.detect(text)

    detected_types = {e.type for e in entities}
    assert "EMAIL" in detected_types
    assert "PHONE" in detected_types
    assert "PAN" in detected_types
    assert "CARD" in detected_types


def test_detection_engine_sorting_and_deduplication():
    engine = DetectionEngine()
    text = "Call 9876543210 or email test@example.com."
    entities = engine.detect(text)

    # Validate ascending sort order by start position
    for i in range(len(entities) - 1):
        assert entities[i].start <= entities[i + 1].start

    # Validate no duplicate spans with identical start and end
    spans = [(e.start, e.end) for e in entities]
    assert len(spans) == len(set(spans))


def test_detection_engine_clean_text():
    engine = DetectionEngine()
    text = "This text contains no personal or sensitive banking information."
    entities = engine.detect(text)
    assert len(entities) == 0


# ==========================================
# Account Detector Tests
# ==========================================

def test_account_detection_valid_with_context():
    detector = AccountDetector()
    text = "Please transfer the funds to account 123456789012 immediately."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "ACCOUNT"
    assert entities[0].value == "123456789012"
    assert entities[0].start == 37
    assert entities[0].end == 49
    assert entities[0].confidence >= 0.90


def test_account_detection_formatted():
    detector = AccountDetector()
    text = "Bank a/c number is 1234-5678-9012 for the vendor."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "ACCOUNT"
    assert entities[0].value == "1234-5678-9012"


def test_account_detection_multiple():
    detector = AccountDetector()
    text = "Primary account: 111122223333, secondary a/c: 444455556666."
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].value == "111122223333"
    assert entities[1].value == "444455556666"


def test_account_detection_no_context_rejected():
    detector = AccountDetector()
    # High-precision rule: Do not treat arbitrary digit sequences as accounts
    text = "Tracking reference 123456789012 was assigned to the package."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_account_detection_dummy_repeating_digits_rejected():
    detector = AccountDetector()
    text = "Account number 000000000000 is invalid."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_account_detection_length_limits():
    detector = AccountDetector()
    # Too short (< 9) or too long (> 18)
    text = "Account: 12345 and Account: 12345678901234567890"
    entities = detector.detect(text)
    assert len(entities) == 0


def test_account_detection_confidence_levels():
    detector = AccountDetector()
    strong_ctx = detector.detect("Account number: 123456789012")
    general_ctx = detector.detect("Bank deposit to 123456789012")

    assert len(strong_ctx) == 1 and len(general_ctx) == 1
    assert strong_ctx[0].confidence > general_ctx[0].confidence


# ==========================================
# IP Detector Tests
# ==========================================

def test_ip_detection_valid():
    detector = IPDetector()
    text = "Connected to server at 192.168.1.100 on port 8080."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "IP"
    assert entities[0].value == "192.168.1.100"
    assert entities[0].start == 23
    assert entities[0].end == 36
    assert entities[0].confidence >= 0.95


def test_ip_detection_multiple():
    detector = IPDetector()
    text = "Primary DNS is 8.8.8.8 and backup gateway is 10.0.0.1."
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].value == "8.8.8.8"
    assert entities[1].value == "10.0.0.1"


def test_ip_detection_invalid_octets():
    detector = IPDetector()
    text = "Invalid IP addresses: 999.999.999.999, 192.168.1.256, and 300.1.1.1"
    entities = detector.detect(text)
    assert len(entities) == 0


def test_ip_detection_partial_numbers_boundary():
    detector = IPDetector()
    # Partial versions and numbers with > 3 digits per octet must not match
    text = "Software v1.2.3.4.5 and subnet 192.168.1.1000 should not trigger false positives."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_ip_detection_clean_text():
    detector = IPDetector()
    text = "The system version is 2.0 with update 3."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_ip_detection_confidence_context():
    detector = IPDetector()
    with_context = detector.detect("Server IP address is 192.168.1.1.")
    without_context = detector.detect("Values 52.12.34.56 observed.")

    assert with_context[0].confidence > without_context[0].confidence


# ==========================================
# URL Detector Tests
# ==========================================

def test_url_detection_https_and_http():
    detector = URLDetector()
    text = "Visit https://bank.com/portal and http://localhost:8000/docs for setup."
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].type == "URL"
    assert entities[0].value == "https://bank.com/portal"
    assert entities[1].type == "URL"
    assert entities[1].value == "http://localhost:8000/docs"


def test_url_detection_preserves_exact_positions():
    detector = URLDetector()
    text = "Endpoint is https://api.bank.com/v1/scan?tenant=demo#auth."
    entities = detector.detect(text)

    assert len(entities) == 1
    val = entities[0].value
    assert val == "https://api.bank.com/v1/scan?tenant=demo#auth"
    assert text[entities[0].start:entities[0].end] == val


def test_url_detection_trailing_punctuation_detached():
    detector = URLDetector()
    text = "See documentation at (https://example.com/api/docs)."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].value == "https://example.com/api/docs"
    assert not entities[0].value.endswith(")")
    assert not entities[0].value.endswith(".")


def test_url_detection_clean_text():
    detector = URLDetector()
    text = "This is a regular message mentioning no web links."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_url_detection_confidence_context():
    detector = URLDetector()
    with_context = detector.detect("Access the API portal website at https://bank.com/v1/scan.")
    without_context = detector.detect("Found https://uncommon-domain at runtime.")

    assert with_context[0].confidence >= without_context[0].confidence


# ==========================================
# API Key Detector Tests
# ==========================================

def test_api_key_detection_known_prefixes():
    detector = APIKeyDetector()
    text = "OpenAI: sk-proj-1234567890abcdef1234567890, GitHub: ghp_1234567890abcdefghijklmnopqrstuvwxyz, AWS: AKIAIOSFODNN7EXAMPLE"
    entities = detector.detect(text)

    assert len(entities) == 3
    for e in entities:
        assert e.type == "API_KEY"
    assert any("sk-proj-" in e.value for e in entities)
    assert any("ghp_" in e.value for e in entities)
    assert any("AKIA" in e.value for e in entities)


def test_api_key_detection_slack_and_stripe():
    detector = APIKeyDetector()
    text = "Slack token: xoxb-EXAMPLE000000-EXAMPLE000000-EXAMPLEtokenvalue000 and Stripe key: pk_test_EXAMPLESTRIPE1234567890xx"
    entities = detector.detect(text)

    assert len(entities) == 2
    assert entities[0].type == "API_KEY"
    assert entities[1].type == "API_KEY"


def test_api_key_detection_context_assigned():
    detector = APIKeyDetector()
    text = "Set api_key = 'abcdef1234567890abcdef1234567890' in the environment."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "API_KEY"
    assert entities[0].value == "abcdef1234567890abcdef1234567890"


def test_api_key_detection_no_match_arbitrary_string():
    detector = APIKeyDetector()
    # High-precision rule: Arbitrary hashes or long words must not be treated as API keys
    text = "The commit sha was e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_api_key_detection_clean_text():
    detector = APIKeyDetector()
    text = "Regular banking transaction report."
    entities = detector.detect(text)
    assert len(entities) == 0


# ==========================================
# JWT Detector Tests
# ==========================================

def test_jwt_detection_standard():
    detector = JWTDetector()
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"Authorization header contains Bearer {jwt_token}."
    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "JWT"
    assert entities[0].value == jwt_token
    assert entities[0].confidence >= 0.90
    assert text[entities[0].start:entities[0].end] == jwt_token


def test_jwt_detection_no_match_malformed():
    detector = JWTDetector()
    # Missing 3rd section (signature)
    text = "Token candidate eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0 is incomplete."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_jwt_detection_clean_text():
    detector = JWTDetector()
    text = "This text has no base64 tokens whatsoever."
    entities = detector.detect(text)
    assert len(entities) == 0


def test_jwt_detection_context_confidence():
    detector = JWTDetector()
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    with_context = detector.detect(f"Authorization: Bearer {jwt_token}")
    without_context = detector.detect(f"Payload was {jwt_token}")

    assert with_context[0].confidence > without_context[0].confidence


def test_detection_engine_all_ten_pii_types():
    engine = DetectionEngine()
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    text = (
        f"Customer Rahul Sharma (email: rahul@gmail.com, phone: 9876543210) "
        f"holds PAN IKRPM7731M, card 4111-1111-1111-1111, and bank account 123456789012. "
        f"User accessed portal https://secure.bank.com from IP 192.168.1.50 "
        f"using OpenAI key sk-proj-1234567890abcdef1234567890 and Bearer {jwt_token}."
    )

    entities = engine.detect(text)
    detected_types = {e.type for e in entities}

    expected_types = {
        "NAME", "EMAIL", "PHONE", "PAN", "CARD",
        "ACCOUNT", "URL", "IP", "API_KEY", "JWT"
    }

    assert expected_types.issubset(detected_types)

    # Verify ascending sort order by start position
    for i in range(len(entities) - 1):
        assert entities[i].start <= entities[i + 1].start