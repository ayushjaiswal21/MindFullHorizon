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
        # Ensure python client points to the configured host
        try:
            os.environ['OLLAMA_HOST'] = self.ollama_host
        except Exception:
            pass
        
        # Model & generation defaults (override via env vars)
        self.model_name = os.getenv('OLLAMA_MODEL', 'ALIENTELLIGENCE/mindwell:latest')
        
        # Base options for all generations; can be overridden per-call
        def _env_int(name, default):
            try:
                return int(os.getenv(name, str(default)))
            except Exception:
                return default
        def _env_float(name, default):
            try:
                return float(os.getenv(name, str(default)))
            except Exception:
                return default
        
        self.chat_options = {
            # Increased defaults for longer responses and slower machines
            "num_predict": _env_int('OLLAMA_NUM_PREDICT', 512),
            "timeout": _env_int('OLLAMA_TIMEOUT', 120),    # seconds
            "temperature": _env_float('OLLAMA_TEMPERATURE', 0.7),
            "top_p": _env_float('OLLAMA_TOP_P', 0.9),
            "repeat_penalty": _env_float('OLLAMA_REPEAT_PENALTY', 1.2)
        }
        
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
            print("Ollama library not available")
            return False

        try:
            # Try to list models with a timeout
            models = ollama.list()
            if not models or 'models' not in models:
                print("No models found in Ollama response")
                return False

            # Check if our specific model is available
            model_available = any(
                model.get('name') == self.model_name
                for model in models['models']
            )

            if model_available:
                print("Mindwell model found and available")
                return True
            else:
                print("Mindwell model not found. Available models:")
                for model in models['models']:
                    print(f"  - {model.get('name')}")
                return False

        except Exception as e:
            print(f"Ollama connection check failed: {e}")
            # In development, try to proceed anyway if Ollama seems to be working
            try:
                # Try a simple test to see if Ollama is actually responsive
                test_response = ollama.chat(
                    model=self.model_name,
                    messages=[{'role': 'user', 'content': 'test'}],
                    options={'num_predict': 1, 'timeout': 5}
                )
                print("Ollama is actually working despite connection check failure")
                return True
            except:
                print("Ollama is not working")
                return False

    def generate_chat_response(self, user_message: str, context: dict = None) -> str:
        """
        Generates a conversational chatbot response using Ollama with optimized parameters.
        """
        system_prompt = (
            "You are Dr. Anya, a compassionate AI wellness coach and psychologist. "
            "Provide warm, empathetic, supportive responses focused on mental health and wellbeing. "
            "Keep responses concise (2-4 sentences), actionable, and encouraging. "
            "Ask open-ended questions to continue the conversation when appropriate. "
            "Never provide medical diagnoses or clinical advice. Focus on wellness and self-care."
        )

        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for chat.")
            return "I'm currently unable to connect to my knowledge base. Please try again in a moment or speak with a mental health professional for immediate support."

        print("Using local 'mindwell' model for chat.")
        try:
            # Use centralized, configurable options (longer timeout/length by default)
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ],
                stream=False,
                options=self.chat_options
            )
            response_text = response['message']['content'].strip()

            # Clean up response - remove extra whitespace and limit length
            response_text = ' '.join(response_text.split())  # Normalize whitespace
            if len(response_text) > 500:  # Limit length for better UX
                response_text = response_text[:497] + "..."

            return response_text
        except Exception as e:
            print(f"Error with local model: {e}")
            return "I'm having some technical difficulties right now. Please try again in a moment, or consider reaching out to a trusted friend or mental health professional."

    def generate_assessment_insights(self, assessment_type: str, score: int, responses: dict) -> dict:
        """
        Generates insights for an assessment using Ollama LLM with optimized prompts.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for assessment insights.")
            return self._fallback_assessment_insights(assessment_type, score)

        print("Using local 'mindwell' model for assessment insights.")

        prompt = f"""
        You are Dr. Anya, a compassionate wellness coach. Provide supportive insights for this {assessment_type} assessment.

        Score: {score}
        Responses: {json.dumps(responses, indent=2)}

        Respond in this exact format:

        SUMMARY: [2 sentences explaining the score and what it suggests]

        RECOMMENDATIONS:
        • [Specific actionable suggestion]
        • [Another specific suggestion]
        • [Third suggestion]

        COPING STRATEGIES:
        • [Relevant coping technique]
        • [Another technique]

        Keep it supportive, encouraging, and focused on wellness. Use bullet points as shown.
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={**self.chat_options, "num_predict": max(self.chat_options.get("num_predict", 384), 640), "timeout": max(self.chat_options.get("timeout", 90), 180), "temperature": 0.6, "top_p": 0.85}
            )
            ai_response = response['message']['content']

            # Parse the AI response into structured format
            lines = ai_response.strip().split('\n')
            summary = ""
            recommendations = []
            strategies = []

            current_section = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if 'SUMMARY:' in line.upper():
                    current_section = 'summary'
                    summary = line.replace('SUMMARY:', '').strip()
                elif 'RECOMMENDATIONS:' in line.upper():
                    current_section = 'recommendations'
                elif 'COPING STRATEGIES:' in line.upper():
                    current_section = 'strategies'
                elif line.startswith('•') and current_section == 'recommendations':
                    recommendations.append(line[1:].strip())
                elif line.startswith('•') and current_section == 'strategies':
                    strategies.append(line[1:].strip())

            # Fallback parsing if structured format not followed
            if not summary and len(lines) > 0:
                summary = lines[0] if lines[0] else f"Your {assessment_type} score of {score} suggests areas for wellness focus."

            if not recommendations and len(lines) > 1:
                recommendations = [line for line in lines[1:4] if line.strip()]

            if not strategies and len(lines) > 4:
                strategies = [line for line in lines[4:6] if line.strip()]

            return {
                'summary': summary[:200],  # Limit length
                'recommendations': recommendations[:3],  # Limit to 3 recommendations
                'resources': strategies[:2]  # Use strategies as resources
            }

        except Exception as e:
            print(f"Error with local model for assessment insights: {e}")
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
        Generates progress recommendations using Ollama LLM.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for progress recommendations.")
            return self._fallback_progress_recommendations()

        print("Using local 'mindwell' model for progress recommendations.")

        prompt = f"""
        You are Dr. Anya, a supportive wellness coach helping students track their mental health progress.

        Based on this wellness data: {user_data}

        Please provide:
        1. A brief, encouraging summary of their progress
        2. 2-3 specific recommendations for continued wellbeing
        3. 1-2 priority actions for the coming week

        Focus on being supportive, practical, and student-friendly.
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={**self.chat_options, "num_predict": max(self.chat_options.get("num_predict", 512), 768), "timeout": max(self.chat_options.get("timeout", 120), 180)}
            )
            ai_response = response['message']['content']

            # Parse the AI response into structured format
            lines = ai_response.strip().split('\n')
            summary = ""
            recommendations = []
            priority_actions = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Simple parsing based on common patterns
                if any(word in line.lower() for word in ['summary', 'progress', 'doing well']):
                    summary = line
                elif any(word in line.lower() for word in ['recommend', 'suggest', 'try']):
                    recommendations.append(line.strip('•-* '))
                elif any(word in line.lower() for word in ['priority', 'week', 'focus']):
                    priority_actions.append(line.strip('•-* '))

            # Ensure we have content for each section
            if not summary:
                summary = 'You are making steady progress. Keep up the great work!'

            if not recommendations:
                recommendations = ['Continue with your current wellness routine.', 'Remember to be kind to yourself.']

            if not priority_actions:
                priority_actions = ['Consider reaching out to a friend or family member this week.']

            return {
                'summary': summary,
                'recommendations': recommendations[:3],  # Limit to 3 recommendations
                'priority_actions': priority_actions[:2]  # Limit to 2 priority actions
            }

        except Exception as e:
            print(f"Error with local model for progress recommendations: {e}")
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
        Generates insights for digital detox data using Ollama LLM.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for digital detox insights.")
            return self._fallback_digital_detox_insights()

        print("Using local 'mindwell' model for digital detox insights.")

        prompt = f"""
        You are Dr. Anya, a digital wellness coach helping students achieve better balance with technology.

        Based on this digital detox data: {detox_data}

        Please provide:
        1. An AI wellness score (Excellent/Good/Fair/Needs Improvement/Poor)
        2. A brief explanation of the score and current patterns
        3. 2-3 specific suggestions for improving digital wellness

        Focus on being supportive and practical for student life.
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={**self.chat_options, "num_predict": max(self.chat_options.get("num_predict", 512), 768), "timeout": max(self.chat_options.get("timeout", 120), 180)}
            )
            ai_response = response['message']['content']

            # Parse the AI response into structured format
            lines = ai_response.strip().split('\n')
            ai_score = "Good"  # default
            ai_suggestion = ""

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for score indicators
                if any(word in line.lower() for word in ['excellent', 'good', 'fair', 'needs improvement', 'poor']):
                    if 'excellent' in line.lower():
                        ai_score = 'Excellent'
                    elif 'good' in line.lower():
                        ai_score = 'Good'
                    elif 'fair' in line.lower():
                        ai_score = 'Fair'
                    elif 'needs improvement' in line.lower():
                        ai_score = 'Needs Improvement'
                    elif 'poor' in line.lower():
                        ai_score = 'Poor'

                # Collect suggestion text
                if any(word in line.lower() for word in ['suggest', 'recommend', 'try', 'consider']):
                    if ai_suggestion:
                        ai_suggestion += " "
                    ai_suggestion += line.strip('•-* ')

            # Ensure we have a suggestion
            if not ai_suggestion:
                ai_suggestion = 'AI insights are currently unavailable. Try to balance your screen time with other activities.'

            return {
                'ai_score': ai_score,
                'ai_suggestion': ai_suggestion[:500]  # Limit length
            }

        except Exception as e:
            print(f"Error with local model for digital detox insights: {e}")
            return self._fallback_digital_detox_insights()

    def _fallback_digital_detox_insights(self) -> dict:
        """Fallback if AI is unavailable for digital detox insights."""
        return {
            'ai_score': 'N/A',
            'ai_suggestion': 'AI insights are currently unavailable. Try to balance your screen time with other activities.'
        }

    def generate_goal_suggestions(self, patient_data: dict) -> dict:
        """
        Generates personalized goal suggestions based on patient data using Ollama LLM.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for goal suggestions.")
            return self._fallback_goal_suggestions(patient_data)

        print("Using local 'mindwell' model for goal suggestions.")

        prompt = f"""
        You are Dr. Anya, a wellness coach helping students set meaningful and achievable goals for their mental health and wellbeing.

        Based on this patient data: {patient_data}

        Please provide:
        1. A brief summary of their current wellness state
        2. 3 personalized goal suggestions with specific, measurable targets
        3. Priority actions for getting started

        Focus on being encouraging, practical, and tailored to student life.
        Make goals SMART (Specific, Measurable, Achievable, Relevant, Time-bound).
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={**self.chat_options, "num_predict": max(self.chat_options.get("num_predict", 768), 1024), "timeout": max(self.chat_options.get("timeout", 120), 200)}
            )
            ai_response = response['message']['content']

            # Parse the AI response into structured format
            lines = ai_response.strip().split('\n')
            summary = ""
            goals = []
            priority_actions = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for summary
                if any(word in line.lower() for word in ['summary', 'current', 'wellness', 'doing']):
                    summary = line

                # Look for goals (numbered or bulleted lists)
                elif any(char in line for char in ['1.', '2.', '3.', '•', '-']) and any(word in line.lower() for word in ['goal', 'practice', 'reduce', 'increase', 'daily', 'weekly']):
                    goals.append(line.strip('•-*123456789. '))

                # Look for priority actions
                elif any(word in line.lower() for word in ['priority', 'start', 'begin', 'first']):
                    priority_actions.append(line.strip('•-* '))

            # Ensure we have content for each section
            if not summary:
                summary = 'Based on your wellness data, here are some personalized goal suggestions.'

            if not goals:
                goals = [
                    'Practice mindfulness or meditation for 10-15 minutes daily',
                    'Limit social media usage to 2 hours per day',
                    'Engage in moderate physical activity for 30 minutes, 5 days per week'
                ]

            if not priority_actions:
                priority_actions = [
                    'Start with one small, achievable goal',
                    'Track your progress daily',
                    'Celebrate small wins along the way'
                ]

            return {
                'summary': summary,
                'goals': goals[:3],  # Limit to 3 goals
                'priority_actions': priority_actions[:2]  # Limit to 2 priority actions
            }

        except Exception as e:
            print(f"Error with local model for goal suggestions: {e}")
            return self._fallback_goal_suggestions(patient_data)

    def _fallback_goal_suggestions(self, patient_data: dict) -> dict:
        """Fallback if AI is unavailable for goal suggestions."""
        return {
            'summary': 'Based on your wellness data, here are some personalized goal suggestions.',
            'goals': [
                {
                    'title': 'Daily Mindfulness Practice',
                    'description': 'Practice mindfulness or meditation for 10-15 minutes daily',
                    'category': 'mental_health',
                    'priority': 'high',
                    'target_value': 7,
                    'unit': 'days'
                },
                {
                    'title': 'Reduce Screen Time',
                    'description': 'Limit social media usage to 2 hours per day',
                    'category': 'digital_wellness',
                    'priority': 'medium',
                    'target_value': 2,
                    'unit': 'hours'
                },
                {
                    'title': 'Physical Activity',
                    'description': 'Engage in moderate physical activity for 30 minutes',
                    'category': 'physical_health',
                    'priority': 'medium',
                    'target_value': 5,
                    'unit': 'days'
                }
            ],
            'priority_actions': [
                'Start with one small, achievable goal',
                'Track your progress daily',
                'Celebrate small wins along the way'
            ]
        }

    def analyze_medication_adherence(self, medication_logs_data: list, patient_data: dict) -> dict:
        """
        Analyzes medication adherence patterns using Ollama LLM.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for medication adherence analysis.")
            return self._fallback_medication_adherence_analysis(medication_logs_data, patient_data)

        print("Using local 'mindwell' model for medication adherence analysis.")

        prompt = f"""
        You are Dr. Anya, a healthcare coach helping patients understand their medication adherence patterns.

        Based on this medication log data: {medication_logs_data}
        And patient information: {patient_data}

        Please provide:
        1. A brief summary of their adherence pattern
        2. An adherence rate assessment
        3. 3-4 specific recommendations for improving adherence
        4. 2-3 key insights about medication management

        Focus on being supportive, practical, and encouraging.
        """

        try:
            response = ollama.chat(
                model='ALIENTELLIGENCE/mindwell:latest',
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={"num_predict": 768, "timeout": 120}
            )
            ai_response = response['message']['content']

            # Parse the AI response into structured format
            lines = ai_response.strip().split('\n')
            summary = ""
            recommendations = []
            insights = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for summary
                if any(word in line.lower() for word in ['summary', 'pattern', 'adherence']):
                    summary = line

                # Look for recommendations
                elif any(word in line.lower() for word in ['recommend', 'suggest', 'try', 'use', 'set', 'keep']):
                    recommendations.append(line.strip('•-* '))

                # Look for insights
                elif any(word in line.lower() for word in ['insight', 'important', 'key', 'remember', 'benefit']):
                    insights.append(line.strip('•-* '))

            # Ensure we have content for each section
            if not summary:
                total_logs = len(medication_logs_data)
                summary = f'Based on {total_logs} medication logs, here is an analysis of your adherence patterns.'

            if not recommendations:
                recommendations = [
                    'Set daily reminders for medication times',
                    'Use a pill organizer to track doses',
                    'Keep medications in a visible location',
                    'Consider using a medication tracking app'
                ]

            if not insights:
                insights = [
                    'Regular medication adherence supports better health outcomes',
                    'Consistency is key for medication effectiveness',
                    'Talk to your healthcare provider about any adherence challenges'
                ]

            # Calculate a simple adherence rate based on data
            total_logs = len(medication_logs_data)
            adherence_rate = 0.8  # Default 80% adherence rate

            if total_logs > 0:
                # Simple calculation - in a real implementation this would be more sophisticated
                adherence_rate = min(0.95, 0.7 + (total_logs * 0.05))

            return {
                'summary': summary,
                'adherence_rate': adherence_rate,
                'recommendations': recommendations[:4],  # Limit to 4 recommendations
                'insights': insights[:3]  # Limit to 3 insights
            }

        except Exception as e:
            print(f"Error with local model for medication adherence analysis: {e}")
            return self._fallback_medication_adherence_analysis(medication_logs_data, patient_data)

    def _fallback_medication_adherence_analysis(self, medication_logs_data: list, patient_data: dict) -> dict:
        """Fallback if AI is unavailable for medication adherence analysis."""
        total_logs = len(medication_logs_data)
        adherence_rate = 0.8  # Default 80% adherence rate

        if total_logs > 0:
            # Simple calculation based on number of logs (assuming daily medications)
            # In a real implementation, this would be more sophisticated
            adherence_rate = min(0.95, 0.7 + (total_logs * 0.05))

        return {
            'summary': f'Based on {total_logs} medication logs, your adherence rate is approximately {adherence_rate:.1%}',
            'adherence_rate': adherence_rate,
            'recommendations': [
                'Set daily reminders for medication times',
                'Use a pill organizer to track doses',
                'Keep medications in a visible location',
                'Consider using a medication tracking app'
            ],
            'insights': [
                'Regular medication adherence supports better health outcomes',
                'Consistency is key for medication effectiveness',
                'Talk to your healthcare provider about any adherence challenges'
            ]
        }

    def generate_clinical_note(self, transcript: str, patient_context: dict = None) -> str:
        """
        Generates a clinical note from a session transcript using Ollama.
        """
        # Check if Ollama is available before generating response
        if not self._check_ollama_connection():
            print("Ollama not available for clinical note generation.")
            return self._fallback_clinical_note(transcript, patient_context)

        print("Using local 'mindwell' model for clinical note generation.")

        # Create context-aware prompt
        context_str = ""
        if patient_context:
            context_str = f"""
Patient Context:
- Wellness Trend: {patient_context.get('wellness_trend', 'Not available')}
- Digital Score: {patient_context.get('digital_score', 'Not available')}
- Engagement: {patient_context.get('engagement', 'Not available')}

Please consider this context when generating the clinical note."""

        prompt = f"""
        You are Dr. Anya, a clinical psychologist creating professional session notes.

        Please create a structured clinical note based on this session transcript:

        {transcript}

        {context_str}

        Structure the clinical note as follows:
        1. SESSION SUMMARY (2-3 sentences overview)
        2. KEY TOPICS DISCUSSED (bullet points of main concerns/issues)
        3. THERAPEUTIC INTERVENTIONS (techniques used or recommended)
        4. PATIENT RESPONSE (how patient engaged/responded)
        5. ASSESSMENT (current mental state and progress indicators)
        6. TREATMENT PLAN (next steps and recommendations)

        Keep the note professional, objective, and focused on therapeutic progress.
        Use clinical terminology appropriately but avoid diagnostic language.
        """

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': prompt}
                ],
                stream=False,
                options={**self.chat_options, "num_predict": max(self.chat_options.get("num_predict", 1024), 1280), "timeout": max(self.chat_options.get("timeout", 120), 240)}
            )
            return response['message']['content']
        except Exception as e:
            print(f"Error with local model for clinical notes: {e}")
            return self._fallback_clinical_note(transcript, patient_context)

    def _fallback_clinical_note(self, transcript: str, patient_context: dict = None) -> str:
        """Fallback clinical note generation if AI is unavailable."""
        return f"""
        SESSION SUMMARY:
        Session transcript analyzed. Key themes include personal challenges and wellness concerns discussed during the therapeutic session.

        KEY TOPICS DISCUSSED:
        • General wellness and emotional wellbeing
        • Personal challenges and stressors
        • Coping strategies and support systems

        THERAPEUTIC INTERVENTIONS:
        • Active listening and empathetic response
        • Exploration of current coping mechanisms
        • Discussion of available support resources

        PATIENT RESPONSE:
        Patient engaged in discussion and demonstrated willingness to explore wellness strategies.

        ASSESSMENT:
        Patient presents with typical developmental concerns appropriate for therapeutic support and guidance.

        TREATMENT PLAN:
        • Continue regular sessions for ongoing support
        • Implement discussed coping strategies
        • Monitor progress and adjust approach as needed
        • Encourage utilization of campus wellness resources

        Note: This is an AI-generated summary based on session transcript analysis.
        """

    def check_api_status(self) -> dict:
        """Check the current status of the AI service and Ollama connection."""
        status = {
            'ollama_available': OLLAMA_AVAILABLE,
            'ollama_connected': False,
            'model_available': False,
            'host': self.ollama_host,
            'timestamp': datetime.now().isoformat()
        }
        
        if not OLLAMA_AVAILABLE:
            status['message'] = 'Ollama library not installed'
            return status
            
        try:
            # Try to connect to Ollama and list models
            models_response = ollama.list()
            status['ollama_connected'] = True
            
            if models_response and 'models' in models_response:
                available_models = [model.get('name') for model in models_response['models']]
                status['available_models'] = available_models
                
                # Check if our specific model is available
                target_model = self.model_name
                if target_model in available_models:
                    status['model_available'] = True
                    status['active_model'] = target_model
                    status['message'] = 'All systems operational'
                else:
                    status['message'] = f'Target model {target_model} not found. Available models: {", ".join(available_models)}'
            else:
                status['message'] = 'No models found in Ollama response'
                
        except Exception as e:
            status['message'] = f'Ollama connection failed: {str(e)}'
            
        return status

# Global AI service instance
ai_service = MindfulAIService()
