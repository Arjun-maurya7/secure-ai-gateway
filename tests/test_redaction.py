from schemas.detection import Entity
from redaction.engine import RedactionEngine


def test_redact_single_entity():
    engine = RedactionEngine()

    text = "My email is rahul@gmail.com."

    entities = [
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=12,
            end=27,
            confidence=0.99,
        )
    ]

    result = engine.redact(text, entities)

    assert result == "My email is [EMAIL]."


def test_redact_multiple_entities():
    engine = RedactionEngine()

    text = "Email rahul@gmail.com or call 9876543210."

    entities = [
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=6,
            end=21,
            confidence=0.99,
        ),
        Entity(
            type="PHONE",
            value="9876543210",
            start=30,
            end=40,
            confidence=0.98,
        ),
    ]

    result = engine.redact(text, entities)

    assert result == "Email [EMAIL] or call [PHONE]."


def test_redact_clean_text():
    engine = RedactionEngine()

    text = "This is a completely clean message."

    result = engine.redact(text, [])

    assert result == text
    
def test_redact_multiple_same_type_entities():
    engine = RedactionEngine()

    text = "Email rahul@gmail.com and rahul@gmail.com."

    entities = [
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=6,
            end=21,
            confidence=0.99,
        ),
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=26,
            end=41,
            confidence=0.99,
        ),
    ]

    result = engine.redact(text, entities)

    assert result == "Email [EMAIL] and [EMAIL]."


def test_redact_entity_at_start():
    engine = RedactionEngine()

    text = "rahul@gmail.com contacted support."

    entities = [
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=0,
            end=15,
            confidence=0.99,
        )
    ]

    result = engine.redact(text, entities)

    assert result == "[EMAIL] contacted support."


def test_redact_entity_at_end():
    engine = RedactionEngine()

    text = "Contact rahul@gmail.com"

    entities = [
        Entity(
            type="EMAIL",
            value="rahul@gmail.com",
            start=8,
            end=23,
            confidence=0.99,
        )
    ]

    result = engine.redact(text, entities)

    assert result == "Contact [EMAIL]"