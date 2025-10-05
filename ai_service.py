import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Info: Ollama library not installed. Local AI features will be disabled.")

load_dotenv()

class MindfulAIService:
    def __init__(self):
        # --- Local Ollama (Mindwell) Configuration ---
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.local_model_available = False
        if OLLAMA_AVAILABLE:
            try:
                # Test connection to Ollama server
                ollama.list()
                self.local_model_available = True
                print(f"Successfully connected to local Ollama server at {self.ollama_host}")
            except Exception as e:
                print(f"Warning: Could not connect to local Ollama server. Error: {e}")
                print("Note: Make sure Ollama is running with: ollama serve")
        else:
            print("Warning: Ollama library not available. Chat functionality will be disabled.")

    def _check_ollama_connection(self) -> bool:
        """Check if Ollama is currently available and responding."""
        if not OLLAMA_AVAILABLE:
            return False

        try:
            ollama.list()
            return True
        except Exception:
            return False

    def generate_chat_response(self, user_message: str, context: dict = None) -> str:
        """
        Generates a conversational chatbot response using Ollama only.
        """
        system_prompt = (
            "You are Dr. Anya, a compassionate AI psychologist. "
            "Greet the user warmly, answer their questions, and provide supportive, empathetic, and helpful responses. "
            "Do not give medical advice or diagnoses. If the user says 'hi', respond with a friendly greeting and ask how you can help. "
            "If the user shares a concern, ask open-ended questions and encourage them to talk more. "
            "Keep responses concise but meaningful."
        )

        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for chat.")
            return "AI chat service is currently unavailable. Please ensure Ollama is running with the mindwell model."

        print("Using local 'mindwell' model for chat.")
        try:
            response = ollama.chat(
                model='ALIENTELLIGENCE/mindwell:latest',
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ],
                stream=False,
                options={"num_predict": 512, "timeout": 120}
            )
            return response['message']['content']
        except Exception as e:
            print(f"Error with local model: {e}")
            return "I'm sorry, I'm having trouble connecting to my knowledge base right now. Please try again in a moment."

    def generate_assessment_insights(self, assessment_type: str, score: int, responses: dict) -> dict:
        """
        Generates insights for an assessment using fallback responses only.
        """
        return self._fallback_assessment_insights(assessment_type, score)

    def _fallback_assessment_insights(self, assessment_type: str, score: int) -> dict:
        """Fallback if AI is unavailable for assessments."""
        return {
            'summary': f'Your {assessment_type} score is {score}. This suggests you may benefit from additional support.',
            'recommendations': ['Consider discussing these results with a healthcare provider.'],
            'resources': ['Mindfulness exercises']
        }

    def generate_progress_recommendations(self, user_data: dict) -> dict:
        """
        Generates progress recommendations using fallback responses only.
        """
        return self._fallback_progress_recommendations()

    def _fallback_progress_recommendations(self) -> dict:
        """Fallback if AI is unavailable for progress recommendations."""
        return {
            'summary': 'You are making steady progress. Keep up the great work!',
            'recommendations': ['Continue with your current wellness routine.', 'Remember to be kind to yourself.'],
            'priority_actions': ['Consider reaching out to a friend or family member this week.']
        }

    def generate_digital_detox_insights(self, detox_data: dict) -> dict:
        """
        Generates insights for digital detox data using fallback responses only.
        """
        return self._fallback_digital_detox_insights()

    def _fallback_digital_detox_insights(self) -> dict:
        """Fallback if AI is unavailable for digital detox insights."""
        return {
            'ai_score': 'N/A',
            'ai_suggestion': 'AI insights are currently unavailable. Try to balance your screen time with other activities.'
        }

    def check_api_status(self) -> Dict:
        """Check API status for compatibility with existing code"""
        return {
            "status": "ollama_only",
            "message": "Using Ollama only for AI services",
            "details": {
                "local_model_available": self.local_model_available,
                "ollama_host": self.ollama_host
            }
        }

# Global AI service instance
ai_service = MindfulAIService()
