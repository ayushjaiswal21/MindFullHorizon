import os
from .gemini_impl import GeminiStubClient, GeminiClient

# Use the stub client if GEMINI_API_KEY is not set
if os.environ.get("GEMINI_API_KEY"):
    client = GeminiClient()
else:
    client = GeminiStubClient()

def ask(prompt: str, **kwargs) -> str:
    """
    A simple wrapper to call the configured AI client.
    """
    return client.ask(prompt, **kwargs)
