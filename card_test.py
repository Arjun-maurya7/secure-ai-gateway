from detection.detectors.card import CardDetector

text = """
Card 1: 4111111111111111
Card 2: 4111-1111-1111-1111
Card 3: 9111 1111 1111 1111
"""

detector = CardDetector()
entities = detector.detect(text)

for entity in entities:
    print(entity)