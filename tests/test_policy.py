from policy.engine import PolicyEngine
from schemas.policy import PolicyAction


def test_policy_email_redact():
    engine = PolicyEngine()

    assert engine.get_action("EMAIL") == PolicyAction.REDACT


def test_policy_card_redact():
    engine = PolicyEngine()

    assert engine.get_action("CARD") == PolicyAction.REDACT


def test_policy_url_allow():
    engine = PolicyEngine()

    assert engine.get_action("URL") == PolicyAction.ALLOW


def test_policy_api_key_block():
    engine = PolicyEngine()

    assert engine.get_action("API_KEY") == PolicyAction.BLOCK


def test_policy_jwt_block():
    engine = PolicyEngine()

    assert engine.get_action("JWT") == PolicyAction.BLOCK


def test_policy_unknown_type_defaults_to_redact():
    engine = PolicyEngine()

    assert engine.get_action("UNKNOWN") == PolicyAction.REDACT