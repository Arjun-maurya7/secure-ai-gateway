class RedactionEngine:

    def redact(self, text: str, entities) -> str:
        for entity in sorted(entities, key=lambda entity: entity.start, reverse=True):
            replacement = f"[{entity.type}]"

            text = text[:entity.start] + replacement + text[entity.end:]

        return text