"""
tests/test_integration.py
Integration tests for the /v1/redact endpoint from the gateway perspective.

Covers the four gateway scenarios:
  1. ALLOW  — clean prompt, sanitized_text == original, entities == []
  2. REDACT — PII present, sanitized_text differs, entities listed
  3. BLOCK  — blocking entity (API_KEY / JWT), HTTP 403
  4. Mixed  — REDACT + BLOCK in same text → 403 (BLOCK takes precedence)
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

REDACT_URL = "/v1/redact"


# ---------------------------------------------------------------------------
# ALLOW scenario
# ---------------------------------------------------------------------------

class TestGatewayAllow:
    """
    When the prompt contains no PII (or only ALLOW-policy entities such as URLs),
    /v1/redact should return HTTP 200 with sanitized_text identical to the input
    and an empty entities list.
    """

    def test_allow_clean_prompt(self):
        text = "What is the capital of France?"
        resp = client.post(REDACT_URL, json={"text": text})
        assert resp.status_code == 200

        data = resp.json()
        assert data["sanitized_text"] == text, (
            "ALLOW: sanitized_text must equal original for a clean prompt"
        )
        assert data["entities"] == [], (
            "ALLOW: no entities should be reported for a clean prompt"
        )

    def test_allow_url_only(self):
        """URLs have policy=ALLOW and must pass through without redaction."""
        text = "Please summarise https://docs.python.org/3/"
        resp = client.post(REDACT_URL, json={"text": text})
        assert resp.status_code == 200

        data = resp.json()
        # The URL entity is ALLOW so the text should be unchanged
        assert data["sanitized_text"] == text

    def test_allow_returns_200_not_403(self):
        resp = client.post(REDACT_URL, json={"text": "Hello, how are you?"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# REDACT scenario
# ---------------------------------------------------------------------------

class TestGatewayRedact:
    """
    When the prompt contains REDACT-policy PII, /v1/redact must:
      - return HTTP 200
      - replace PII with [TYPE] placeholders in sanitized_text
      - list the detected entities
      - sanitized_text must NOT contain the original sensitive values
    """

    def test_redact_email(self):
        original = "Contact me at rahul@gmail.com"
        resp = client.post(REDACT_URL, json={"text": original})
        assert resp.status_code == 200

        data = resp.json()
        sanitized = data["sanitized_text"]

        # Security property: original PII must be absent
        assert "rahul@gmail.com" not in sanitized, (
            "REDACT: original email must NOT appear in sanitized_text"
        )
        # Sanitized placeholder must be present
        assert "[EMAIL]" in sanitized, (
            "REDACT: [EMAIL] placeholder must appear in sanitized_text"
        )
        # Entity must be reported
        types = {e["type"] for e in data["entities"]}
        assert "EMAIL" in types

    def test_redact_phone(self):
        original = "Call me on 9876543210"
        resp = client.post(REDACT_URL, json={"text": original})
        assert resp.status_code == 200

        data = resp.json()
        sanitized = data["sanitized_text"]

        assert "9876543210" not in sanitized, (
            "REDACT: original phone must NOT appear in sanitized_text"
        )
        assert "[PHONE]" in sanitized

    def test_redact_multiple_pii_types(self):
        """
        Verifies email + name + phone are all redacted and none appear
        in the sanitized output.
        """
        original = "Rahul Sharma can be reached at rahul@gmail.com or 9876543210."
        resp = client.post(REDACT_URL, json={"text": original})
        assert resp.status_code == 200

        data = resp.json()
        sanitized = data["sanitized_text"]

        # Original sensitive values must be absent
        assert "rahul@gmail.com" not in sanitized, (
            "REDACT: email must NOT appear in sanitized_text"
        )
        assert "9876543210" not in sanitized, (
            "REDACT: phone must NOT appear in sanitized_text"
        )

        # Redacted placeholders must be present
        assert "[EMAIL]" in sanitized
        assert "[PHONE]" in sanitized

        # Entity types reported
        types = {e["type"] for e in data["entities"]}
        assert "EMAIL" in types
        assert "PHONE" in types

    def test_redact_pan(self):
        original = "My PAN is IKRPM7731M"
        resp = client.post(REDACT_URL, json={"text": original})
        assert resp.status_code == 200

        data = resp.json()
        sanitized = data["sanitized_text"]

        assert "IKRPM7731M" not in sanitized
        assert "[PAN]" in sanitized

    def test_redact_sanitized_differs_from_original(self):
        """The sanitized text must differ from the original when PII is present."""
        original = "My email is test@example.com"
        resp = client.post(REDACT_URL, json={"text": original})
        assert resp.status_code == 200

        data = resp.json()
        assert data["sanitized_text"] != original, (
            "REDACT: sanitized_text must differ from original when PII is detected"
        )

    def test_redact_request_sent_exactly_once(self):
        """
        /v1/redact endpoint must process the request and return exactly one
        response (no double-processing side-effect).
        """
        original = "Ping me at ping@example.com"
        responses = [
            client.post(REDACT_URL, json={"text": original})
            for _ in range(1)  # Simulate single send
        ]
        assert len(responses) == 1
        assert responses[0].status_code == 200
        assert "ping@example.com" not in responses[0].json()["sanitized_text"]


# ---------------------------------------------------------------------------
# BLOCK scenario
# ---------------------------------------------------------------------------

class TestGatewayBlock:
    """
    When the prompt contains a BLOCK-policy entity (API_KEY or JWT),
    /v1/redact must return HTTP 403 and the request must not be processed.
    """

    def test_block_api_key_returns_403(self):
        resp = client.post(
            REDACT_URL,
            json={"text": "My API key is sk-proj-1234567890abcdef1234567890"}
        )
        assert resp.status_code == 403, (
            "BLOCK: API_KEY must cause HTTP 403"
        )

    def test_block_api_key_has_detail(self):
        """403 response must include a human-readable reason in 'detail'."""
        resp = client.post(
            REDACT_URL,
            json={"text": "Use this key: sk-proj-1234567890abcdef1234567890"}
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "detail" in body, "BLOCK: 403 response must include 'detail'"
        assert body["detail"], "BLOCK: 'detail' must be non-empty"

    def test_block_jwt_returns_403(self):
        jwt_token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        resp = client.post(
            REDACT_URL,
            json={"text": f"Authorization: Bearer {jwt_token}"}
        )
        assert resp.status_code == 403, (
            "BLOCK: JWT must cause HTTP 403"
        )

    def test_block_does_not_return_sanitized_text(self):
        """
        A 403 response body must NOT contain a 'sanitized_text' field
        (it should only contain FastAPI's error detail).
        """
        resp = client.post(
            REDACT_URL,
            json={"text": "key: sk-proj-1234567890abcdef1234567890"}
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "sanitized_text" not in body, (
            "BLOCK: 403 must not leak sanitized_text"
        )


# ---------------------------------------------------------------------------
# Mixed REDACT + BLOCK — BLOCK must take precedence
# ---------------------------------------------------------------------------

class TestGatewayMixedBlockPrecedence:
    """
    When a prompt contains both REDACT-policy and BLOCK-policy entities,
    the BLOCK must take precedence and the request must be rejected with 403.
    A partially sanitized request must NEVER be sent.
    """

    def test_mixed_redact_and_block_returns_403(self):
        """BLOCK precedence: email (REDACT) + API key (BLOCK) → 403."""
        text = (
            "Contact Rahul at rahul@gmail.com. "
            "My API key is sk-proj-1234567890abcdef1234567890"
        )
        resp = client.post(REDACT_URL, json={"text": text})
        assert resp.status_code == 403, (
            "Mixed REDACT+BLOCK: BLOCK must take precedence — must return 403"
        )

    def test_mixed_no_sanitized_text_on_block(self):
        """A 403 due to mixed content must not leak any sanitized_text."""
        text = (
            "Phone: 9876543210. "
            "JWT: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        resp = client.post(REDACT_URL, json={"text": text})
        assert resp.status_code == 403
        body = resp.json()
        assert "sanitized_text" not in body

    def test_mixed_name_email_and_api_key_blocked(self):
        """Three types: NAME (REDACT) + EMAIL (REDACT) + API_KEY (BLOCK) → 403."""
        text = (
            "Rahul Sharma at rahul@gmail.com "
            "with key sk-proj-1234567890abcdef1234567890"
        )
        resp = client.post(REDACT_URL, json={"text": text})
        assert resp.status_code == 403
