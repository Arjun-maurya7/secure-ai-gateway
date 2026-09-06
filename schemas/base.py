from abc import ABC, abstractmethod

from .detection import Entity

class BaseDetector(ABC):

    @abstractmethod
    def detect(self, text: str) -> list[Entity]:
        pass