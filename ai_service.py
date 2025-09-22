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
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.local_model_available = False
        
        # Only try to connect if DISABLE_LOCAL_AI is not set
        if not os.getenv('DISABLE_LOCAL_AI'):
            try:
                # Set a short timeout for the connection attempt
                import requests
                response = requests.get(f"{self.ollama_host}/api/tags", timeout=2)
                if response.status_code == 200:
                    self.local_model_available = True
                    print("Successfully connected to local Ollama server")
            except Exception as e:
                print("Info: Local AI services not available. Using cloud fallback.")


    def generate_chat_response(self, user_message: str, context: dict = None) -> str:
        """
        Generates a conversational chatbot response using available AI services.
        Falls back to simpler responses if no AI services are available.
        """
        system_prompt = (
            "You are Dr. Anya, a compassionate AI psychologist. "
            "Greet the user warmly, answer their questions, and provide supportive, empathetic, and helpful responses. "
            "Do not give medical advice or diagnoses. If the user says 'hi', respond with a friendly greeting and ask how you can help. "
            "If the user shares a concern, ask open-ended questions and encourage them to talk more. "
            "Keep responses concise but meaningful."
        )
        
        # If no AI services are available, use basic responses
        if not self.local_model_available and not self.gemini_model:
            return self._get_basic_response(user_message)
            
        prompt = f"{system_prompt}\n\nUser: {user_message}"
        
    def _get_basic_response(self, user_message: str) -> str:
        """Provide basic responses when AI services are unavailable."""
        message = user_message.lower().strip()
        
        # Basic response patterns
        if any(greeting in message for greeting in ['hi', 'hello', 'hey']):
            return "Hello! I'm Dr. Anya. While our AI services are currently limited, I'm here to chat. How are you feeling today?"
        
        if 'help' in message or '?' in message:
            return ("I'm currently operating in basic mode, but I'm still here to listen. "
                   "Would you like to tell me more about what's on your mind?")
        
        if any(word in message for word in ['sad', 'depressed', 'anxious', 'worried']):
            return ("I hear that you're going through a difficult time. While I'm operating in basic mode, "
                   "remember that it's okay to seek help. Would you like information about professional support services?")
        
        # Default response
        return ("I'm listening and I care about what you're saying. While I'm operating in basic mode right now, "
               "I'm here to chat. Would you like to tell me more?")

        if self.local_model_available:
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
                print(f"Error with local model: {e}. Falling back to Gemini.")
                return self._gemini_request(prompt, "Error generating chat response.")
        else:
            print("Using Gemini API for chat (fallback).")
            return self._gemini_request(prompt, "AI chat service is currently unavailable.")

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
        prompt = f"""You are a compassionate and empathetic psychologist. Your name is Dr. Anya. Start the conversation with a warm and welcoming message. Ask open-ended questions to encourage the user to share their thoughts and feelings. Your goal is to provide a safe and supportive space for the user to reflect. Do not give medical advice. User's message: {user_message}

User's context: {json.dumps(context, indent=2)}"""

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
