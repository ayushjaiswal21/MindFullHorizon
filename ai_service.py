import requests
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class CloseRouterAIService:
    """Service class for integrating with CloseRouter API"""

    def __init__(self, api_key: str = None, base_url: str = "https://api.closerouter.com/v1"):
        self.base_url = base_url
        self.api_key = api_key or os.getenv('CLOSEROUTER_API_KEY')
        self.external_enabled = (os.getenv('AI_EXTERNAL_CALLS_ENABLED', 'true').lower() == 'true')

        # Optimized model selection
        self.models = {
            'primary': os.getenv('AI_MODEL_PRIMARY', 'gpt-4o'),
            'fast': os.getenv('AI_MODEL_FAST', 'gpt-4o-mini'),
            'reasoning': os.getenv('AI_MODEL_REASONING', 'o3-mini'),
            'clinical': os.getenv('AI_MODEL_CLINICAL', 'claude-3-5-sonnet-20240620'),
            'analytics': os.getenv('AI_MODEL_ANALYTICS', 'gpt-4o')
        }

        self.model_fallbacks = {
            'primary': ['gpt-4o', 'gpt-4-turbo'],
            'fast': ['gpt-4o-mini', 'gpt-3.5-turbo'],
            'reasoning': ['o3-mini', 'gpt-4-turbo'],
            'clinical': ['claude-3-5-sonnet-20240620', 'gpt-4.1-mini'],
            'analytics': ['gpt-4o', 'gpt-4-turbo']
        }

        if not self.api_key:
            print("Warning: No CloseRouter API key found.")

    def _make_request(self, messages: List[Dict], model: str = None, temperature: float = 0.7, max_tokens: int = 512) -> Optional[str]:
        if not self.external_enabled:
            print("AI external calls are disabled.")
            return None
        if not self.api_key:
            print("Error: No API key for CloseRouter.")
            return None

        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            selected_model = model or self.models['fast']
            use_case_key = next((k for k, v in self.models.items() if v == selected_model), 'fast')
            candidates = [selected_model] + [m for m in self.model_fallbacks.get(use_case_key, []) if m != selected_model]

            # --- Corrected API Endpoint as per Documentation ---
            url = f"{self.base_url}/chat/completions"

            last_error = None
            for candidate in candidates:
                # --- Model is sent in the payload ---
                payload = {
                    "model": candidate,
                    "messages": messages,
                    "stream": False,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }

                response = requests.post(url, headers=headers, json=payload, timeout=60)

                if response.status_code == 200:
                    result = response.json()
                    print(f"AI model selected: {candidate}")
                    return result['choices'][0]['message']['content'].strip()

                last_error = f"CloseRouter API error for {candidate}: {response.status_code} - {response.text}"
                print(last_error)

                if response.status_code in [404, 429, 500, 503]:
                    time.sleep(0.25)
                    continue
                else:
                    break

            print(last_error or "CloseRouter API unknown error")
            return None

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to CloseRouter: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None
            
    # --- The rest of your file remains the same ---
    def analyze_digital_wellness(self, screen_time: float, academic_score: int, 
                               social_interactions: str, historical_data: List[Dict] = None) -> Dict:
        """Analyze digital wellness data and provide insights using Claude 3.5 Sonnet"""
        
        # Prepare historical context
        history_context = ""
        if historical_data:
            recent_data = historical_data[-7:]  # Last 7 days
            avg_screen_time = sum(d.get('screen_time_hours', 0) for d in recent_data) / len(recent_data)
            avg_academic = sum(d.get('academic_score', 0) for d in recent_data if d.get('academic_score')) / max(1, len([d for d in recent_data if d.get('academic_score')]))
            
            history_context = f"""
            Historical Context (Last 7 days):
            - Average screen time: {avg_screen_time:.1f} hours
            - Average academic score: {avg_academic:.1f}
            - Trend: {'Improving' if screen_time < avg_screen_time else 'Concerning' if screen_time > avg_screen_time + 1 else 'Stable'}
            """
        
        messages = [
            {
                "role": "system",
                "content": """You are a specialized AI assistant for psychological wellness analysis in college students. 
                Analyze digital behavior patterns and provide personalized recommendations focusing on the relationship between screen time, academic performance, and social interactions.
                
                Provide a wellness score (Excellent/Good/Needs Improvement) and specific, actionable suggestions.
                Always respond with valid JSON format."""
            },
            {
                "role": "user",
                "content": f"""Analyze this student's digital wellness data and provide a JSON response.

Current Data:
- Screen time: {screen_time} hours
- Academic score: {academic_score}/100
- Social interactions: {social_interactions}

{history_context}

Please provide your analysis in this exact JSON format:
{{
    "score": "Excellent|Good|Needs Improvement",
    "suggestion": "Brief actionable suggestion",
    "detailed_analysis": "Detailed psychological analysis",
    "action_items": ["specific action 1", "specific action 2", "specific action 3"]
}}"""
            }
        ]
        
        # Keep token usage tight for this endpoint
        response = self._make_request(messages, model=self.models['primary'], temperature=0.3, max_tokens=400)
        
        if response:
            try:
                # Try to parse JSON response
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return self._parse_text_response(response, screen_time)
        
        # Fallback analysis if AI is unavailable
        return self._fallback_analysis(screen_time, academic_score, social_interactions)
    
    def generate_clinical_note(self, transcript: str, patient_info: Dict = None) -> str:
        """Generate clinical documentation from session transcript using Claude 3.5 Sonnet"""
        
        patient_context = ""
        if patient_info:
            patient_context = f"""
            Patient Context:
            - Recent wellness trends: {patient_info.get('wellness_trend', 'Not available')}
            - Digital wellness score: {patient_info.get('digital_score', 'Not available')}
            - Engagement level: {patient_info.get('engagement', 'Not available')}
            """
        
        messages = [
            {
                "role": "system",
                "content": """You are a mental health clinical documentation assistant. Generate professional, structured, concise clinical notes from therapy session transcripts. 

Include these sections:
- SESSION SUMMARY
- PATIENT PRESENTATION/MOOD
- KEY TOPICS DISCUSSED
- INTERVENTIONS USED
- PATIENT RESPONSE
- ASSESSMENT
- PLAN
- RISK ASSESSMENT (if applicable)

Use professional clinical language appropriate for medical records."""
            },
            {
                "role": "user",
                "content": f"""Generate a comprehensive clinical note from the following therapy session transcript.

{patient_context}

Session Transcript:
{transcript}

Please provide a well-structured clinical note following standard documentation practices."""
            }
        ]
        
        # Cap tokens for efficiency while allowing structured note
        response = self._make_request(messages, model=self.models['clinical'], temperature=0.4, max_tokens=1500)
        return response if response else self._fallback_clinical_note(transcript)
    
    def analyze_institutional_trends(self, institution_data: Dict) -> Dict:
        """Analyze institutional-level wellness trends using GPT-4o for analytics"""
        
        messages = [
            {
                "role": "system",
                "content": """You are an institutional wellness analyst specializing in educational mental health data. 
                Analyze aggregated data for educational institutions and provide actionable insights for administrators and counseling services.
                
                Always respond with valid JSON format."""
            },
            {
                "role": "user",
                "content": f"""Analyze the following institutional wellness data and provide insights.

Institutional Metrics:
- Total students: {institution_data.get('total_users', 0)}
- Active users: {institution_data.get('active_users', 0)}
- Average screen time: {institution_data.get('avg_screen_time', 0)} hours
- High-risk students: {institution_data.get('high_risk_users', 0)}
- Engagement rate: {institution_data.get('engagement_rate', 0)}%

Please provide your analysis in this exact JSON format:
{{
    "overall_status": "Excellent|Good|Concerning|Critical",
    "key_insights": ["insight 1", "insight 2", "insight 3"],
    "recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"],
    "priority_actions": ["action 1", "action 2", "action 3"]
}}"""
            }
        ]
        
        response = self._make_request(messages, model=self.models['analytics'], temperature=0.2, max_tokens=600)
        
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
        
        # Fallback analysis
        return self._fallback_institutional_analysis(institution_data)
    
    def get_model_info(self) -> Dict:
        """Get information about currently configured models"""
        return {
            "current_models": self.models,
            "api_status": "Connected" if self.api_key else "No API Key",
            "base_url": self.base_url,
            "external_enabled": self.external_enabled
        }
    
    def set_model(self, use_case: str, model_id: str) -> bool:
        """Update model for specific use case"""
        if use_case in self.models:
            self.models[use_case] = model_id
            return True
        return False
    
    def _parse_text_response(self, response: str, screen_time: float) -> Dict:
        """Parse non-JSON AI response"""
        # Simple parsing logic for text responses
        if "excellent" in response.lower():
            score = "Excellent"
        elif "good" in response.lower():
            score = "Good"
        else:
            score = "Needs Improvement"
        
        return {
            "score": score,
            "suggestion": response[:200] + "..." if len(response) > 200 else response,
            "detailed_analysis": "AI analysis provided",
            "action_items": ["Follow AI recommendations", "Monitor progress"]
        }
    
    def _fallback_analysis(self, screen_time: float, academic_score: int, social_interactions: str) -> Dict:
        """Fallback analysis when AI is unavailable"""
        if screen_time <= 4 and academic_score >= 85:
            score = "Excellent"
            suggestion = "Great balance! Continue maintaining healthy digital habits."
        elif screen_time <= 6 and academic_score >= 75:
            score = "Good"
            suggestion = "Good progress. Consider reducing screen time slightly for better focus."
        else:
            score = "Needs Improvement"
            suggestion = "Consider setting app limits and taking regular breaks from screens."
        
        return {
            "score": score,
            "suggestion": suggestion,
            "detailed_analysis": f"Based on {screen_time}h screen time and {academic_score}% academic performance",
            "action_items": ["Set daily screen time limits", "Schedule device-free study time"]
        }
    
    def _fallback_clinical_note(self, transcript: str) -> str:
        """Fallback clinical note generation"""
        return f"""
        CLINICAL NOTE - {datetime.now().strftime('%Y-%m-%d')}
        
        SESSION SUMMARY:
        Patient attended scheduled session. Session transcript available for review.
        
        KEY POINTS:
        - Session conducted as planned
        - Patient engagement noted
        - Further analysis recommended
        
        PLAN:
        - Continue regular sessions
        - Monitor progress
        - Follow up as needed
        
        NOTE: Full AI analysis temporarily unavailable. Manual review of transcript recommended.
        
        Transcript Length: {len(transcript)} characters
        """
    
    def _fallback_institutional_analysis(self, data: Dict) -> Dict:
        """Fallback institutional analysis"""
        total = data.get('total_users', 0)
        high_risk = data.get('high_risk_users', 0)
        engagement = data.get('engagement_rate', 0)
        
        if high_risk / max(total, 1) > 0.3:
            status = "Concerning"
        elif engagement > 70:
            status = "Good"
        else:
            status = "Needs Attention"
        
        return {
            "overall_status": status,
            "key_insights": [f"Engagement rate: {engagement}%", f"High-risk users: {high_risk}"],
            "recommendations": ["Increase outreach programs", "Enhance digital wellness education"],
            "priority_actions": ["Review high-risk cases", "Improve engagement strategies"]
        }
    
    def generate_chat_response(self, user_message: str, user_context: Dict = None) -> Dict:
        """Generate empathetic chat response with optimized token usage"""
        
        # Crisis keywords detection
        crisis_keywords = ['suicide', 'kill myself', 'end it all', 'hurt myself', 'die', 'hopeless']
        if any(keyword in user_message.lower() for keyword in crisis_keywords):
            return {
                "response": "I'm concerned about you. Please reach out for immediate help: National Suicide Prevention Lifeline: 988 or Crisis Text Line: Text HOME to 741741. You matter.",
                "is_ai_powered": True,
                "needs_followup": True
            }
        
        # Build minimal context
        context = ""
        if user_context:
            wellness = user_context.get('wellness_.env', 'unknown')
            engagement = user_context.get('engagement_level', 'unknown')
            context = f"User wellness: {wellness}, engagement: {engagement}."
        
        messages = [
            {
                "role": "system", 
                "content": "You're a supportive mental health chat assistant. Give brief, empathetic responses (2-3 sentences max). Focus on validation and gentle guidance."
            },
            {
                "role": "user",
                "content": f"{context} User says: '{user_message}'"
            }
        ]
        
        response = self._make_request(messages, model=self.models['fast'], temperature=0.6, max_tokens=150)
        
        if response:
            return {
                "response": response,
                "is_ai_powered": True,
                "needs_followup": False
            }
        
        # Fallback responses
        fallback_responses = [
            "I hear you. Your feelings are valid. Would you like to talk more about what's on your mind?",
            "Thank you for sharing. It takes courage to reach out. How can I best support you right now?",
            "I'm here to listen. What you're experiencing matters, and you're not alone in this.",
            "That sounds challenging. Remember, it's okay to take things one step at a time."
        ]
        
        import random
        return {
            "response": random.choice(fallback_responses),
            "is_ai_powered": False,
            "needs_followup": True
        }

    def generate_progress_recommendations(self, user_data: Dict) -> Dict:
        """Generate personalized mental health recommendations with minimal token usage"""
        
        # Extract key metrics
        gad7_score = user_data.get('gad7_score', 'N/A')
        phq9_score = user_data.get('phq9_score', 'N/A')
        wellness_score = user_data.get('wellness_score', 'N/A')
        goals_completed = user_data.get('completed_goals', 0)
        total_goals = user_data.get('total_goals', 0)
        last_assessment = user_data.get('days_since_assessment', 'N/A')
        
        messages = [
            {
                "role": "system",
                "content": "Mental health assistant. Generate 3 brief action recommendations and 3 insights for college student wellness. Focus on anxiety, depression, and goal achievement. Be concise."
            },
            {
                "role": "user", 
                "content": f"Student data: GAD-7:{gad7_score}, PHQ-9:{phq9_score}, Wellness:{wellness_score}, Goals:{goals_completed}/{total_goals}, Last assessment:{last_assessment} days. Generate JSON: {{\"actions\":[{{\"title\":\"...\",\"desc\":\"...\",\"priority\":\"high/medium/low\"}}], \"insights\":[{{\"title\":\"...\",\"desc\":\"...\"}}]}}"
            }
        ]
        
        response = self._make_request(messages, model=self.models['fast'], temperature=0.3, max_tokens=350)
        
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
        
        # Fallback recommendations
        return self._fallback_progress_recommendations(user_data)
    
    def _fallback_progress_recommendations(self, user_data: Dict) -> Dict:
        """Fallback recommendations when AI is unavailable"""
        gad7 = user_data.get('gad7_score')
        phq9 = user_data.get('phq9_score')
        goals_completed = user_data.get('completed_goals', 0)
        
        actions = [
            {"title": "Complete Assessment", "desc": "Take your monthly mental health assessment", "priority": "high"},
            {"title": "Practice Mindfulness", "desc": "Try 10 minutes of daily meditation", "priority": "medium"},
            {"title": "Set New Goals", "desc": "Add achievable wellness goals", "priority": "medium"}
        ]
        
        insights = [
            {"title": "Goal Progress", "desc": f"You've completed {goals_completed} goals. Keep building momentum!"},
            {"title": "Regular Check-ins", "desc": "Consistent self-assessment helps track your mental health journey"},
            {"title": "Small Steps", "desc": "Focus on small, daily habits that support your wellbeing"}
        ]
        
        if gad7 and isinstance(gad7, (int, float)) and gad7 > 10:
            actions[0] = {"title": "Anxiety Support", "desc": "Consider speaking with a counselor about anxiety management", "priority": "high"}
            insights[0] = {"title": "Anxiety Management", "desc": "Your recent scores suggest focusing on stress reduction techniques"}
        
        return {"actions": actions, "insights": insights}

    def generate_assessment_insights(self, assessment_type: str, score: int, responses: dict) -> dict:
        """Generate AI-powered insights for assessment results.
        
        Args:
            assessment_type: Type of assessment (e.g., 'GAD-7', 'PHQ-9')
            score: Assessment score
            responses: Dictionary of question-answer pairs
            
        Returns:
            dict: Contains 'summary', 'recommendations', and 'resources' keys
        """
        # Use the clinical model for more sensitive analysis
        model = self.models['clinical']
        
        # Build the prompt
        prompt = f"""You are a compassionate mental health assistant. Provide a concise (2-3 sentences) analysis of these {assessment_type} results:
        
        Score: {score}
        
        Responses: {json.dumps(responses, indent=2)}
        
        Focus on:
        1. Brief interpretation of score
        2. One key insight
        3. One actionable suggestion
        
        Keep it supportive and non-alarming. Use simple language."""
        
        messages = [
            {"role": "system", "content": "You are a supportive mental health professional. Provide clear, empathetic, and actionable insights about assessment results."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self._make_request(messages, model=model, temperature=0.5, max_tokens=200)
            if response:
                return {
                    'summary': response.strip(),
                    'recommendations': [
                        'Consider discussing these results with a healthcare provider',
                        'Practice self-care activities that help you relax'
                    ],
                    'resources': [
                        'Mindfulness exercises',
                        'Breathing techniques',
                        'Local mental health support groups'
                    ]
                }
        except Exception as e:
            print(f"Error generating assessment insights: {e}")
        
        # Fallback response if AI call fails
        return {
            'summary': f"Your {assessment_type} score is {score}. This suggests you may benefit from additional support.",
            'recommendations': [
                'Consider discussing these results with a healthcare provider',
                'Practice self-care activities that help you relax'
            ],
            'resources': [
                'Mindfulness exercises',
                'Breathing techniques',
                'Local mental health support groups'
            ]
        }
# Global AI service instance
ai_service = CloseRouterAIService()