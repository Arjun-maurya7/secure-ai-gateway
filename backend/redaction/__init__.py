from schemas.detection import Entity


class RedactionEngine:

    def redact(self, text: str, entities: list[Entity]) -> str:
        result = text

        for entity in sorted(entities, key=lambda entity: entity.start, reverse=True):
            replacement = f"[{entity.type}]"

            result = (
                result[:entity.start]
                + replacement
                + result[entity.end:]
            )

        return result