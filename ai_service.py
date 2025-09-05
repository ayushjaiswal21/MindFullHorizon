import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

try:
    from openai import OpenAI, APIError, RateLimitError, APITimeoutError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI library not available. AI features will be limited.")

try:
    load_dotenv(encoding='utf-8-sig')
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")
    print("Continuing with default configuration...")

class CloseRouterAIService:
    """Service class for integrating with CloseRouter API using the OpenAI SDK."""

    def __init__(self, api_key: str = None, base_url: str = "https://api.closerouter.com/v1"):
        self.base_url = base_url
        self.api_key = api_key or os.getenv('CLOSEROUTER_API_KEY')
        self.external_enabled = (os.getenv('AI_EXTERNAL_CALLS_ENABLED', 'true').lower() == 'true')
        self.client = None

        # Check if OpenAI is available
        if not OPENAI_AVAILABLE:
            print("Warning: OpenAI library not available. Using fallback mode.")
            self.external_enabled = False
            return

        if self.api_key and self.external_enabled:
            try:
                self.client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout=30.0  # Reduced timeout
                )
                print(f"AI service initialized with CloseRouter API at {self.base_url}")
            except Exception as e:
                print(f"Warning: Failed to initialize AI client: {e}")
                self.client = None
                self.external_enabled = False
        else:
            print("Warning: AI service disabled - no API key or external calls disabled.")

        # Updated model selection with more basic models that are likely to be available
        self.models = {
            'primary': os.getenv('AI_MODEL_PRIMARY', 'gpt-3.5-turbo'),
            'fast': os.getenv('AI_MODEL_FAST', 'gpt-3.5-turbo'),
            'reasoning': os.getenv('AI_MODEL_REASONING', 'gpt-3.5-turbo'),
            'clinical': os.getenv('AI_MODEL_CLINICAL', 'gpt-3.5-turbo'),
            'analytics': os.getenv('AI_MODEL_ANALYTICS', 'gpt-3.5-turbo'),
            'vision': os.getenv('AI_MODEL_VISION', 'gpt-3.5-turbo'),
            'search': os.getenv('AI_MODEL_SEARCH', 'gpt-3.5-turbo')
        }

        # Simplified fallback chains with basic models
        self.model_fallbacks = {
            'primary': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613', 'gpt-3.5-turbo-0301'],
            'fast': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613'],
            'reasoning': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613'],
            'clinical': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613'],
            'analytics': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613'],
            'vision': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613'],
            'search': ['gpt-3.5-turbo', 'gpt-3.5-turbo-0613']
        }

    def _make_request(self, messages: List[Dict], model: str = None, temperature: float = 0.7, max_tokens: int = 512) -> Optional[str]:
        if not self.external_enabled or not self.client:
            print("AI external calls are disabled or client not initialized.")
            return None

        selected_model = model or self.models['fast']
        use_case_key = next((k for k, v in self.models.items() if v == selected_model), 'fast')
        candidates = [selected_model] + [m for m in self.model_fallbacks.get(use_case_key, []) if m != selected_model]

        last_error = None
        for candidate in candidates:
            try:
                response = self.client.chat.completions.create(
                    model=candidate,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
                print(f"AI model selected: {candidate}")
                return response.choices[0].message.content.strip()
            except (RateLimitError, APITimeoutError) as e:
                last_error = f"CloseRouter API temporary error for {candidate}: {e.__class__.__name__}. Retrying..."
                print(last_error)
                # Implement exponential backoff for rate limits
                time.sleep(1.0)  # Wait longer for rate limit or timeout
                continue
            except APIError as e:
                # Handles 500, 404, 401 etc.
                last_error = f"CloseRouter API error for {candidate}: {e.status_code} - {e.response.text}"
                print(last_error)
                
                # Handle rate limiting with proper headers
                if e.status_code == 429:
                    retry_after = e.response.headers.get('Retry-After', 60)
                    print(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(int(retry_after))
                    continue
                
                # Stop retrying on critical errors like invalid key or model not found
                if e.status_code in [401, 404]:
                    print(f"Critical error {e.status_code}: {e.response.text}")
                    break
                
                # Retry on server errors (but limit retries)
                if e.status_code in [500, 502, 503]:
                    print(f"Server error {e.status_code}, retrying...")
                    time.sleep(0.5)
                    continue
                    
                break # Break for other client-side errors
            except Exception as e:
                last_error = f"An unexpected error occurred with {candidate}: {e}"
                print(last_error)
                break # Stop on unknown errors

        print(last_error or "CloseRouter API unknown error after all retries.")
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
    
    def generate_enhanced_clinical_analysis(self, transcript: str, patient_data: Dict = None) -> Dict:
        """Generate enhanced clinical analysis with multiple AI models for comprehensive insights"""
        
        if not self.external_enabled or not self.client:
            return self._fallback_enhanced_analysis(transcript, patient_data)
        
        try:
            # Use Claude for clinical note generation
            clinical_note = self.generate_clinical_note(transcript, patient_data)
            
            # Use GPT-4o for sentiment analysis
            sentiment_messages = [
                {
                    "role": "system",
                    "content": "You are a mental health sentiment analysis expert. Analyze the emotional tone and key themes in therapy sessions."
                },
                {
                    "role": "user",
                    "content": f"Analyze the sentiment and key themes in this therapy session: {transcript[:1000]}..."
                }
            ]
            
            sentiment_analysis = self._make_request(
                sentiment_messages, 
                model=self.models['analytics'], 
                temperature=0.3, 
                max_tokens=300
            )
            
            # Use reasoning model for risk assessment
            risk_messages = [
                {
                    "role": "system",
                    "content": "You are a mental health risk assessment specialist. Identify potential risk factors and urgency levels."
                },
                {
                    "role": "user",
                    "content": f"Assess risk factors in this session: {transcript[:800]}..."
                }
            ]
            
            risk_assessment = self._make_request(
                risk_messages,
                model=self.models['reasoning'],
                temperature=0.2,
                max_tokens=200
            )
            
            return {
                "clinical_note": clinical_note,
                "sentiment_analysis": sentiment_analysis or "Analysis unavailable",
                "risk_assessment": risk_assessment or "Assessment unavailable",
                "ai_models_used": ["claude-3-5-sonnet-20241022", "gpt-4o", "o3-mini"],
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error in enhanced clinical analysis: {e}")
            return self._fallback_enhanced_analysis(transcript, patient_data)
    
    def _fallback_enhanced_analysis(self, transcript: str, patient_data: Dict = None) -> Dict:
        """Fallback for enhanced clinical analysis when AI is unavailable"""
        return {
            "clinical_note": self._fallback_clinical_note(transcript),
            "sentiment_analysis": "Enhanced analysis temporarily unavailable",
            "risk_assessment": "Risk assessment temporarily unavailable",
            "ai_models_used": ["fallback"],
            "analysis_timestamp": datetime.now().isoformat()
        }
    
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
            "external_enabled": self.external_enabled,
            "provider": "CloseRouter",
            "available_models": len(self.models),
            "fallback_chains": len(self.model_fallbacks)
        }
    
    def check_api_status(self) -> Dict:
        """Check API status and rate limits"""
        if not self.external_enabled or not self.client:
            return {
                "status": "disabled",
                "message": "AI service is disabled or not initialized"
            }
        
        try:
            # Make a minimal test request
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                temperature=0
            )
            
            # Check rate limit headers
            rate_limit_info = {
                "limit": response.headers.get('X-RateLimit-Limit', 'Unknown'),
                "remaining": response.headers.get('X-RateLimit-Remaining', 'Unknown'),
                "reset": response.headers.get('X-RateLimit-Reset', 'Unknown')
            }
            
            return {
                "status": "healthy",
                "message": "API is responding normally",
                "rate_limits": rate_limit_info,
                "test_response": response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"API test failed: {str(e)}",
                "error_type": type(e).__name__
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
            wellness = user_context.get('wellness_score', 'unknown')
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
        
        # Default fallback response in case of any errors
        fallback_response = {
            'summary': f'Your {assessment_type} assessment has been recorded with a score of {score}.',
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
        
        if not self.client or not self.external_enabled:
            return fallback_response
            
        try:
            response = self._make_request(messages, model=model, temperature=0.5, max_tokens=200)
            if response and isinstance(response, str):
                return {
                    'summary': response.strip(),
                    'recommendations': fallback_response['recommendations'],
                    'resources': fallback_response['resources']
                }
            return fallback_response
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
# Global AI service instance - initialize with error handling for deployment
try:
    ai_service = CloseRouterAIService()
    print("AI service initialized successfully")
except Exception as e:
    print(f"Warning: AI service initialization failed: {e}")
    # Create a minimal fallback service
    class FallbackAIService:
        def __init__(self):
            self.external_enabled = False
            self.client = None
        
        def analyze_digital_wellness(self, *args, **kwargs):
            return {
                'score': 'Good',
                'suggestion': 'Continue monitoring your digital wellness habits.',
                'detailed_analysis': 'AI analysis temporarily unavailable. Please continue logging your data.',
                'action_items': ['Continue logging your data', 'Consult with your healthcare provider']
            }
        
        def generate_clinical_note(self, *args, **kwargs):
            return "AI documentation service is currently unavailable. Please manually document the session."
        
        def analyze_institutional_trends(self, *args, **kwargs):
            return {
                'overall_status': 'Good',
                'key_insights': ['Continue monitoring patient data'],
                'recommendations': ['Maintain current wellness programs'],
                'priority_actions': ['Review data manually']
            }
        
        def generate_chat_response(self, *args, **kwargs):
            return {
                'response': 'I am currently experiencing technical difficulties. Please try again later or contact support.',
                'is_ai_powered': False,
                'needs_followup': True
            }
        
        def generate_progress_recommendations(self, *args, **kwargs):
            return {
                'actions': [
                    {'title': 'Continue Monitoring', 'desc': 'Keep tracking your progress', 'priority': 'medium'}
                ],
                'insights': [
                    {'title': 'System Maintenance', 'desc': 'AI insights temporarily unavailable'}
                ]
            }
        
        def generate_assessment_insights(self, *args, **kwargs):
            return {
                'summary': 'Assessment recorded successfully. AI analysis temporarily unavailable.',
                'recommendations': ['Continue with your current routine', 'Consult with healthcare provider'],
                'resources': ['Local mental health resources', 'Crisis hotlines if needed']
            }
        
        def generate_enhanced_clinical_analysis(self, *args, **kwargs):
            return {
                "clinical_note": "AI documentation service is currently unavailable. Please manually document the session.",
                "sentiment_analysis": "Enhanced analysis temporarily unavailable",
                "risk_assessment": "Risk assessment temporarily unavailable",
                "ai_models_used": ["fallback"],
                "analysis_timestamp": datetime.now().isoformat()
            }
        
        def get_model_info(self):
            return {
                "current_models": {},
                "api_status": "Fallback Mode",
                "base_url": "N/A",
                "external_enabled": False,
                "provider": "Fallback",
                "available_models": 0,
                "fallback_chains": 0
            }
        
        def check_api_status(self):
            return {
                "status": "fallback",
                "message": "AI service is in fallback mode"
            }
    
    ai_service = FallbackAIService()