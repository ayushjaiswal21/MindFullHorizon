import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class OllamaAIService:
    """Service class for integrating with Ollama ALIENTELLIGENCE/mindwell model"""
    
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.model_name = "ALIENTELLIGENCE/mindwell"
    
    def _make_request(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """Make a request to the Ollama API"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                print(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            return None
    
    def analyze_digital_wellness(self, screen_time: float, academic_score: int, 
                               social_interactions: str, historical_data: List[Dict] = None) -> Dict:
        """Analyze digital wellness data and provide insights"""
        
        system_prompt = """You are a specialized AI assistant for psychological wellness analysis. 
        Analyze digital behavior patterns and provide personalized recommendations for college students.
        Focus on the relationship between screen time, academic performance, and social interactions.
        Provide a wellness score (Excellent/Good/Needs Improvement) and specific, actionable suggestions."""
        
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
        
        prompt = f"""
        Analyze this college student's digital wellness data:
        
        Current Day:
        - Screen time: {screen_time} hours
        - Academic performance: {academic_score}/100
        - Social interactions: {social_interactions}
        
        {history_context}
        
        Please provide:
        1. A wellness score (Excellent/Good/Needs Improvement)
        2. 2-3 specific, actionable recommendations
        3. Brief explanation of the relationship between these metrics
        
        Format your response as JSON:
        {{
            "score": "Excellent/Good/Needs Improvement",
            "suggestion": "Main recommendation text",
            "detailed_analysis": "Brief analysis of patterns and relationships",
            "action_items": ["specific action 1", "specific action 2"]
        }}
        """
        
        response = self._make_request(prompt, system_prompt)
        
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
        """Generate clinical documentation from session transcript"""
        
        system_prompt = """You are a clinical documentation assistant specializing in mental health.
        Generate professional, structured clinical notes from therapy session transcripts.
        Follow standard clinical documentation practices and maintain patient confidentiality."""
        
        patient_context = ""
        if patient_info:
            patient_context = f"""
            Patient Context:
            - Recent wellness trends: {patient_info.get('wellness_trend', 'Not available')}
            - Digital wellness score: {patient_info.get('digital_score', 'Not available')}
            - Engagement level: {patient_info.get('engagement', 'Not available')}
            """
        
        prompt = f"""
        Generate a clinical note from this therapy session transcript:
        
        {patient_context}
        
        Transcript:
        {transcript}
        
        Please provide a structured clinical note including:
        1. Session summary
        2. Patient presentation and mood
        3. Key topics discussed
        4. Interventions used
        5. Patient response
        6. Plan for next session
        7. Risk assessment (if applicable)
        
        Keep the note professional, concise, and focused on clinical relevance.
        """
        
        response = self._make_request(prompt, system_prompt)
        return response if response else self._fallback_clinical_note(transcript)
    
    def analyze_institutional_trends(self, institution_data: Dict) -> Dict:
        """Analyze institutional-level wellness trends"""
        
        system_prompt = """You are an institutional wellness analyst. Analyze aggregated mental health data 
        for educational institutions and provide insights for administrators and counseling services."""
        
        prompt = f"""
        Analyze this institutional wellness data:
        
        Institution Metrics:
        - Total students: {institution_data.get('total_users', 0)}
        - Active users: {institution_data.get('active_users', 0)}
        - Average screen time: {institution_data.get('avg_screen_time', 0)} hours
        - High-risk students: {institution_data.get('high_risk_users', 0)}
        - Engagement rate: {institution_data.get('engagement_rate', 0)}%
        
        Provide:
        1. Overall wellness assessment
        2. Key areas of concern
        3. Recommended interventions
        4. Resource allocation suggestions
        
        Format as JSON:
        {{
            "overall_status": "Excellent/Good/Concerning",
            "key_insights": ["insight 1", "insight 2"],
            "recommendations": ["recommendation 1", "recommendation 2"],
            "priority_actions": ["action 1", "action 2"]
        }}
        """
        
        response = self._make_request(prompt, system_prompt)
        
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
        
        # Fallback analysis
        return self._fallback_institutional_analysis(institution_data)
    
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
        
        Session Summary:
        Patient attended scheduled session. Session transcript available for review.
        
        Key Points:
        - Session conducted as planned
        - Patient engagement noted
        - Further analysis recommended
        
        Plan:
        - Continue regular sessions
        - Monitor progress
        - Follow up as needed
        
        Note: Full AI analysis temporarily unavailable. Manual review of transcript recommended.
        
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

# Global AI service instance
ai_service = OllamaAIService()
