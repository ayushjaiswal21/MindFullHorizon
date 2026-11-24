from abc import ABC, abstractmethod

class AIProvider(ABC):
    """Abstract interface for an AI provider."""

    @abstractmethod
    def ask(self, prompt: str, **kwargs) -> str:
        """
        Sends a prompt to the AI and returns the response.

        Args:
            prompt: The prompt to send to the AI.
            **kwargs: Additional provider-specific arguments.

        Returns:
            The AI's response as a string.
        """
        pass

    def configured(self) -> bool:
        """True when the provider has the credentials it needs (checked before the circuit breaker)."""
        return True
