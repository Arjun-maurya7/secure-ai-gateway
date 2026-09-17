from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_scan_endpoint_success():
    payload = {
        "text": "Please contact Rahul at rahul@gmail.com or 9876543210. PAN: IKRPM7731M"
    }
    response = client.post("/v1/scan", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "entities" in data
    types = {e["type"] for e in data["entities"]}
    assert "EMAIL" in types
    assert "PHONE" in types
    assert "PAN" in types


def test_scan_endpoint_clean_text():
    payload = {
        "text": "General bank policies and operating hours."
    }
    response = client.post("/v1/scan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["entities"] == []


def test_scan_endpoint_validation_missing_text():
    response = client.post("/v1/scan", json={})
    assert response.status_code == 422


def test_scan_endpoint_new_detector_types():
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    payload = {
        "text": (
            f"Account: 123456789012, IP: 192.168.1.1, URL: https://bank.com/api, "
            f"Key: sk-proj-1234567890abcdef1234567890, Token: Bearer {jwt_token}"
        )
    }
    response = client.post("/v1/scan", json=payload)
    assert response.status_code == 200

    data = response.json()
    types = {e["type"] for e in data["entities"]}
    assert {"ACCOUNT", "IP", "URL", "API_KEY", "JWT"}.issubset(types)

def test_redact_endpoint_success():
    response = client.post(
        "/v1/redact",
        json={
            "text": "My email is rahul@gmail.com."
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sanitized_text"] == "My email is [EMAIL]."
    assert len(data["entities"]) == 1
    assert data["entities"][0]["type"] == "EMAIL"
    assert data["entities"][0]["value"] == "rahul@gmail.com"


def test_redact_endpoint_multiple_pii():
    response = client.post(
        "/v1/redact",
        json={
            "text": (
                "Rahul Sharma can be contacted at "
                "rahul@gmail.com or 9876543210."
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sanitized_text"] == (
    "[NAME] can be contacted at "
    "[EMAIL] or [PHONE]."
    )

    detected_types = {
        entity["type"]
        for entity in data["entities"]
    }

    assert "NAME" in detected_types
    assert "EMAIL" in detected_types
    assert "PHONE" in detected_types


def test_redact_endpoint_clean_text():
    text = "This message contains no sensitive information."

    response = client.post(
        "/v1/redact",
        json={"text": text}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sanitized_text"] == text
    assert data["entities"] == []
    
def test_redact_endpoint_blocks_api_key():
    response = client.post(
        "/v1/redact",
        json={
            "text": "My API key is sk-proj-1234567890abcdef1234567890"
        }
    )

    assert response.status_code == 403


def test_redact_endpoint_blocks_jwt():
    jwt_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    response = client.post(
        "/v1/redact",
        json={
            "text": f"Authorization token: {jwt_token}"
        }
    )

    assert response.status_code == 403