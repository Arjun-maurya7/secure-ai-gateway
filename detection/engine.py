from detection.detectors.email import EmailDetector
from detection.detectors.phone import PhoneDetector
from detection.detectors.pan import PANDetector
from detection.detectors.ner import NERDetector
from detection.detectors.card import CardDetector
from detection.detectors.account import AccountDetector
from detection.detectors.ip import IPDetector
from detection.detectors.url import URLDetector
from detection.detectors.api_key import APIKeyDetector
from detection.detectors.jwt import JWTDetector


class DetectionEngine:

    def __init__(self):
        self.detectors = [
            EmailDetector(),
            PhoneDetector(),
            PANDetector(),
            NERDetector(),
            CardDetector(),
            AccountDetector(),
            IPDetector(),
            URLDetector(),
            APIKeyDetector(),
            JWTDetector(),
        ]

    def detect(self, text: str):
        entities = []

        for detector in self.detectors:
            entities.extend(detector.detect(text))

        entities.sort(key=lambda entity: entity.start)

        unique_entities = []

        for entity in entities:
            if not any(
                existing.start == entity.start
                and existing.end == entity.end
                for existing in unique_entities
            ):
                unique_entities.append(entity)

        return unique_entities