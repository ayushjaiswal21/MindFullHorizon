import os
import google.generativeai as genai
from .interface import AIProvider

class GeminiStubClient(AIProvider):
    """A local stub for the Gemini client that returns placeholder text."""

    def ask(self, prompt: str, **kwargs) -> str:
        """
        Returns a deterministic response for testing purposes.
        
        TODO: Replace this with a real Gemini API call.
        """
        print(f"--- Gemini Stub: Received prompt: {prompt[:80]}... ---")
        return f"This is a stubbed response for the prompt: '{prompt}'"

class GeminiClient(AIProvider):
    """A real Gemini client that interacts with the Gemini API."""

    def __init__(self):
        # TODO: Initialize the actual Gemini client here.
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.client = genai.GenerativeModel("gemini-pro") # Using gemini-pro as a general purpose model

    def ask(self, prompt: str, **kwargs) -> str:
        """
        TODO: Implement the actual API call to Gemini.
        """
        response = self.client.generate_content(prompt, **kwargs)
        return response.text
