from detection.detectors.email import EmailDetector


def test_email_detection():

    text = "Contact Rahul at rahul@example.com"

    detector = EmailDetector()

    results = detector.detect(text)

    assert len(results) == 1

    entity = results[0]

    assert entity.type == "EMAIL"
    assert entity.value == "rahul@example.com"
    assert entity.start == 17
    assert entity.end == 34