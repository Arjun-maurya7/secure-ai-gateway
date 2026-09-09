from detection.detectors.email import EmailDetector


def test_email_detection():
    detector = EmailDetector()

    text = "My email is rahul@gmail.com."

    entities = detector.detect(text)

    assert len(entities) == 1
    assert entities[0].type == "EMAIL"
    assert entities[0].value == "rahul@gmail.com"