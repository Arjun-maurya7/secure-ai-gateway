import spacy
from schemas.base import BaseDetector
from schemas.detection import Entity


class NERDetector(BaseDetector):

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def detect(self, text: str) -> list[Entity]:
        entities = []

        doc = self.nlp(text)

        for ent in doc.ents:
            if ent.label_ == "PERSON":
                entities.append(
                    Entity(
                        type="NAME",
                        value=ent.text,
                        start=ent.start_char,
                        end=ent.end_char,
                        confidence=0.90,
                    )
                )

        return entities