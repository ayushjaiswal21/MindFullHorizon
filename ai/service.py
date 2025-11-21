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

def generate_assessment_insights(assessment_type: str, score: int, responses: list) -> dict:
    """
    Generate AI-powered insights based on assessment results.
    Returns a dictionary with summary, recommendations, and resources.
    """
    try:
        # Create a comprehensive prompt for the AI
        prompt = f"""
        You are a mental health professional analyzing assessment results. Based on the following assessment data:
        
        Assessment Type: {assessment_type}
        Score: {score}
        Responses: {responses}
        
        Please provide a comprehensive analysis in JSON format with the following structure:
        {{
            "summary": "Brief summary of the assessment results and what they indicate",
            "recommendations": [
                "Specific recommendation 1",
                "Specific recommendation 2",
                "Specific recommendation 3"
            ],
            "resources": [
                "Resource 1 with brief description",
                "Resource 2 with brief description",
                "Resource 3 with brief description"
            ]
        }}
        
        Guidelines:
        - For GAD-7: 0-4=minimal, 5-9=mild, 10-14=moderate, 15-21=severe
        - For PHQ-9: 0-4=minimal, 5-9=mild, 10-14=moderate, 15-19=moderately severe, 20-27=severe
        - Be empathetic and supportive
        - Provide actionable recommendations
        - Include relevant mental health resources
        - Keep the summary under 150 words
        - Keep recommendations practical and specific
        - Include crisis resources if severe scores are detected
        
        Return ONLY the JSON response, no additional text.
        """
        
        response = ask(prompt)
        
        # Try to parse the response as JSON
        import json
        try:
            insights = json.loads(response)
            return insights
        except json.JSONDecodeError:
            # If parsing fails, create a basic response
            return {
                "summary": f"Your {assessment_type} assessment indicates a score of {score}. This suggests a need for attention to your mental health.",
                "recommendations": [
                    "Practice regular self-care and stress management techniques",
                    "Consider talking to a mental health professional",
                    "Maintain a healthy lifestyle with proper sleep and exercise"
                ],
                "resources": [
                    "National Suicide Prevention Lifeline: 988",
                    "Crisis Text Line: Text HOME to 741741",
                    "Find a therapist at Psychology Today or similar directories"
                ]
            }
            
    except Exception as e:
        # Return a fallback response if anything goes wrong
        return {
            "summary": f"Your {assessment_type} assessment score is {score}. AI insights are temporarily unavailable.",
            "recommendations": [
                "Continue monitoring your mental health",
                "Reach out to support systems if needed",
                "Consider professional guidance if symptoms persist"
            ],
            "resources": [
                "Emergency: Call 911 or go to nearest emergency room",
                "Crisis Support: 988 Suicide & Crisis Lifeline",
                "Professional Help: Contact local mental health services"
            ]
        }

def generate_progress_recommendations(user_data: dict) -> dict:
    """
    Generate AI-powered progress recommendations based on user data.
    """
    try:
        prompt = f"""
        You are a mental health coach providing personalized recommendations. Based on this user data:
        
        {user_data}
        
        Please provide recommendations in JSON format:
        {{
            "insights": [
                {{"title": "Insight 1", "desc": "Description 1"}},
                {{"title": "Insight 2", "desc": "Description 2"}}
            ],
            "actions": [
                {{"title": "Action 1", "desc": "Description 1", "priority": "high"}},
                {{"title": "Action 2", "desc": "Description 2", "priority": "medium"}}
            ]
        }}
        
        Return ONLY the JSON response.
        """
        
        response = ask(prompt)
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "insights": [
                    {"title": "Keep Going", "desc": "You're making progress on your mental health journey."},
                    {"title": "Stay Consistent", "desc": "Regular check-ins help maintain mental wellness."}
                ],
                "actions": [
                    {"title": "Continue Daily Monitoring", "desc": "Keep tracking your mood and symptoms.", "priority": "medium"},
                    {"title": "Practice Self-Care", "desc": "Make time for activities that support your wellbeing.", "priority": "high"}
                ]
            }
    except Exception as e:
        return {
            "insights": [
                {"title": "Progress Tracking", "desc": "Continue monitoring your mental health journey."},
                {"title": "Wellness Focus", "desc": "Prioritize self-care and healthy habits."}
            ],
            "actions": [
                {"title": "Daily Check-ins", "desc": "Monitor your mood and symptoms regularly.", "priority": "medium"},
                {"title": "Healthy Lifestyle", "desc": "Maintain sleep, exercise, and nutrition balance.", "priority": "high"}
            ]
        }

def generate_digital_detox_insights(detox_data: dict) -> dict:
    """
    Generate AI-powered digital detox insights.
    """
    try:
        prompt = f"""
        You are a digital wellness coach analyzing screen time and digital behavior. Based on this data:
        
        {detox_data}
        
        Provide insights and recommendations in JSON format:
        {{
            "analysis": "Brief analysis of digital habits",
            "recommendations": [
                "Recommendation 1",
                "Recommendation 2"
            ],
            "score": "Digital wellness score out of 100"
        }}
        
        Return ONLY the JSON response.
        """
        
        response = ask(prompt)
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "analysis": "Your digital habits show room for improvement in screen time management.",
                "recommendations": [
                    "Set daily screen time limits",
                    "Take regular breaks from digital devices",
                    "Create tech-free zones in your home"
                ],
                "score": "75"
            }
    except Exception as e:
        return {
            "analysis": "Digital wellness analysis temporarily unavailable.",
            "recommendations": [
                "Monitor your screen time regularly",
                "Balance digital and offline activities",
                "Practice digital mindfulness"
            ],
            "score": "70"
        }

def generate_chat_response(prompt: str) -> str:
    """
    Generate a chat response for the AI chat feature.
    """
    try:
        enhanced_prompt = f"""
        You're a supportive mental health chat assistant. Give brief, empathetic responses (2-3 sentences max). 
        Focus on validation and gentle guidance.
        
        User message: {prompt}
        
        Response:
        """
        return ask(enhanced_prompt)
    except Exception as e:
        return "I'm here to support you. How can I help you today?"
