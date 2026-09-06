from detection.detectors.email import EmailDetector
from detection.detectors.phone import PhoneDetector
from detection.detectors.name import NameDetector
from detection.detectors.pan import PANDetector

class DetectionEngine:

    def __init__(self):
        self.detectors = [
            EmailDetector(),
            PhoneDetector(),
            NameDetector(),
            PANDetector(),
        ]

    def detect(self, text: str):
        entities = []
        for detector in self.detectors:
            entities.extend(detector.detect(text))
            
        entities.sort(key=lambda entity: entity.start)
        return entities