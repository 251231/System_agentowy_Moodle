from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Kontrakt dla wszystkich agentów działających na rozpakowanym katalogu MBZ."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def process(self, workspace_path: str) -> tuple[bool, str]:
        """
        Przetwarza pliki w workspace_path.
        Zwraca (sukces: bool, log: str).
        """
        ...
