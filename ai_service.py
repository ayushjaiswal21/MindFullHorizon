# ai_service.py

import os
import json
import ollama
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class MindfulAIService:
    def __init__(self):
        # --- Gemini API Configuration ---
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.gemini_model = None
            print("Warning: GEMINI_API_KEY not found. Gemini features will be disabled.")

        # --- Local Ollama (Mindwell) Configuration ---
        self.ollama_host = os.getenv('OLLAMA_HOST')
        self.local_model_available = False
        if self.ollama_host:
            try:
                ollama.list()
                self.local_model_available = True
                print(f"Successfully connected to local Ollama server at {self.ollama_host}")
            except Exception as e:
                print(f"Warning: Could not connect to local Ollama server. Mindwell features will use fallback. Error: {e}")

    def generate_clinical_note(self, transcript: str, patient_info: dict = None) -> str:
        """
        Generates a clinical note.
        Uses the local 'mindwell' model if available, otherwise falls back to Gemini.
        """
        prompt = f"Generate a comprehensive clinical note from the following therapy session transcript for a patient with context {patient_info}:\n\nTranscript:\n{transcript}"

        if self.local_model_available:
            print("Using local 'mindwell' model for clinical note.")
            try:
                response = ollama.chat(
                    model='ALIENTELLIGENCE/mindwell:latest',
                    messages=[{'role': 'user', 'content': prompt}]
                )
                return response['message']['content']
            except Exception as e:
                print(f"Error with local model: {e}. Falling back to Gemini.")
                return self._gemini_request(prompt, "Error generating clinical note.")
        else:
            print("Using Gemini API for clinical note (fallback).")
            return self._gemini_request(prompt, "AI documentation service is currently unavailable.")

    def generate_assessment_insights(self, assessment_type: str, score: int, responses: dict) -> dict:
        """
        Generates insights for an assessment using the Gemini API.
        """
        prompt = f"""You are a compassionate mental health assistant.
        Provide a concise analysis for a {assessment_type} assessment.
        Score: {score}
        Responses: {json.dumps(responses, indent=2)}
        Provide a JSON response with three keys: "summary", "recommendations" (a list of strings), and "resources" (a list of strings)."""

        if self.gemini_model:
            try:
                response_text = self._gemini_request(prompt, is_json=True)
                # A simple check to ensure the response is likely JSON before parsing
                if '{' in response_text and '}' in response_text:
                    return json.loads(response_text)
                else:
                    # If not JSON, create a structured response from the text
                    return {'summary': response_text, 'recommendations': [], 'resources': []}
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error processing Gemini response for assessment: {e}")
                return self._fallback_assessment_insights(assessment_type, score)
        else:
            return self._fallback_assessment_insights(assessment_type, score)

    def _gemini_request(self, prompt: str, fallback_text: str = "I'm sorry, an error occurred.", is_json: bool = False) -> str:
        if not self.gemini_model:
            return fallback_text

        try:
            response = self.gemini_model.generate_content(prompt)
            # Clean up markdown code block formatting that Gemini sometimes adds
            if is_json:
                return response.text.strip().replace('```json', '').replace('```', '')
            return response.text
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return fallback_text

    def _fallback_assessment_insights(self, assessment_type: str, score: int) -> dict:
        """Fallback if AI is unavailable for assessments."""
        return {
            'summary': f'Your {assessment_type} score is {score}. This suggests you may benefit from additional support.',
            'recommendations': ['Consider discussing these results with a healthcare provider.'],
            'resources': ['Mindfulness exercises']
        }

    def generate_progress_recommendations(self, user_data: dict) -> dict:
        """
        Generates progress recommendations using the Gemini API.
        """
        prompt = f"""You are a supportive mental health guide.
        Based on the user's latest data, provide encouraging and actionable recommendations.
        User Data: {json.dumps(user_data, indent=2)}
        Provide a JSON response with three keys: "summary", "recommendations" (a list of strings), and "priority_actions" (a list of strings).
        The summary should be a brief, positive overview of their progress.
        Recommendations should be gentle suggestions for continued well-being.
        Priority actions should be 1-2 critical next steps if any data is concerning (e.g., high GAD-7 score)."""

        if self.gemini_model:
            try:
                response_text = self._gemini_request(prompt, is_json=True)
                if '{' in response_text and '}' in response_text:
                    return json.loads(response_text)
                else:
                    return {'summary': response_text, 'recommendations': [], 'priority_actions': []}
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error processing Gemini response for progress: {e}")
                return self._fallback_progress_recommendations()
        else:
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
        Generates insights for digital detox data using the Gemini API.
        """
        prompt = f"""You are a digital wellness coach.
        Based on the user's digital detox data, provide an AI score and a suggestion.
        User Data: {json.dumps(detox_data, indent=2)}
        Provide a JSON response with two keys: "ai_score" (a string, e.g., "Good", "Needs Improvement") and "ai_suggestion" (a string).
        The score should reflect a healthy balance of screen time, academic performance, and social interaction.
        The suggestion should be a short, actionable tip to improve their digital wellness."""

        if self.gemini_model:
            try:
                response_text = self._gemini_request(prompt, is_json=True)
                if '{' in response_text and '}' in response_text:
                    return json.loads(response_text)
                else:
                    return {'ai_score': 'N/A', 'ai_suggestion': 'Could not generate insights.'}
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error processing Gemini response for digital detox: {e}")
                return self._fallback_digital_detox_insights()
        else:
            return self._fallback_digital_detox_insights()

    def _fallback_digital_detox_insights(self) -> dict:
        """Fallback if AI is unavailable for digital detox insights."""
        return {
            'ai_score': 'N/A',
            'ai_suggestion': 'AI insights are currently unavailable. Try to balance your screen time with other activities.'
        }

# Global AI service instance
ai_service = MindfulAIService()
