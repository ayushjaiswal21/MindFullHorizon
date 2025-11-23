import os
import json
import re
import logging
import asyncio
from ai.gemini_impl import ask_gemini_system_user
from severity import heuristic_severity

logger = logging.getLogger(__name__)

def ask(prompt: str, system_prompt: str = "You are a helpful AI assistant.", **kwargs) -> str:
    """
    A simple wrapper to call the configured AI client.
    """
    try:
        return ask_gemini_system_user(system_prompt, prompt, max_tokens=1024, temperature=0.7)
    except Exception as e:
        logger.exception("AI service 'ask' failed")
        raise e

async def ask_with_severity(user_text: str, user_id=None, prefer_llm=True):
    # 1) quick heuristic
    score = heuristic_severity(user_text)

    # 2) load system prompt from file for maintainability
    try:
        # Corrected path to be relative to project root
        with open('ai_prompts/psychologist_system.txt','r', encoding='utf-8') as f:
            system_prompt = f.read()
    except Exception:
        system_prompt = ("You are Dr. Anya, an empathetic psychologist. "
                         "Respond concisely. "
                         "Output ONLY JSON: "
                         '{"reply": "string", "severity": int(0-10), "reason": "string<=12words", ' 
                         '"recommended_action": "none"|"recommend_appointment"|"emergency_hotline"}.')

    raw = None
    try:
        # call gemini wrapper with reduced tokens for chat
        raw = ask_gemini_system_user(system_prompt, user_text, max_tokens=300, temperature=0.2)
    except Exception:
        logger.exception("Gemini call failed inside ask_with_severity")

    parsed = None
    recommended_action = 'none'
    reason = ''
    if raw:
        # attempt to find first JSON object inside the returned text
        # The model should return valid JSON, but this is a good fallback
        clean_raw = raw.strip().replace('```json', '').replace('```', '')
        m = re.search(r'\{[\s\S]*\}', clean_raw)
        json_str = m.group(0) if m else clean_raw.strip()
        
        # Try to fix truncated JSON by adding missing closing parts
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed, attempting to fix truncated response: {json_str[:100]}...")
            # Try to fix common truncation issues
            if json_str.count('{') > json_str.count('}'):
                json_str += '}'
            if json_str.count('"') % 2 != 0:
                json_str += '"'
            try:
                parsed = json.loads(json_str)
            except Exception:
                logger.exception(f"Failed parsing LLM JSON response even after fixes: {json_str}")
                parsed = None

    if parsed:
        reply_text = parsed.get('reply','I hear you. Can you say more?')
        llm_sev = int(parsed.get('severity', score))
        score = max(score, min(10, llm_sev))
        recommended_action = parsed.get('recommended_action','none')
        reason = parsed.get('reason','')
    else:
        # fallback short reply
        reply_text = "I hear you — that sounds really hard. Can you tell me what happened before this?"
        if score >= 9:
            recommended_action = 'emergency_hotline'
            reason = 'explicit self-harm language or plan'
        elif score >= 7:
            recommended_action = 'recommend_appointment'
            reason = 'high distress signals'
        else:
            recommended_action = 'none'
            reason = 'heuristic check'

    escalate = score >= 7
    return {
        'reply': reply_text,
        'severity': int(score),
        'escalate': bool(escalate),
        'recommended_action': recommended_action,
        'reason': reason
    }

def generate_assessment_insights(assessment_type: str, score: int, responses: list) -> dict:
    """
    Generate AI-powered insights based on assessment results.
    Returns a dictionary with summary, recommendations, and resources.
    """
    try:
        # Concise prompt for token efficiency
        prompt = f"""
        Type: {assessment_type}, Score: {score}, Responses: {responses}
        
        Return JSON:
        {{
            "summary": "Brief summary (<100 words)",
            "recommendations": ["Rec 1", "Rec 2", "Rec 3"],
            "resources": ["Res 1", "Res 2", "Res 3"]
        }}
        
        Context: GAD-7/PHQ-9 scoring. Be empathetic, actionable.
        """
        
        system_prompt = "You are a mental health professional."
        response = ask(prompt, system_prompt=system_prompt, max_tokens=600)
        
        # Try to parse the response as JSON
        clean_response = response.strip().replace('```json', '').replace('```', '')
        try:
            insights = json.loads(clean_response)
            return insights
        except json.JSONDecodeError:
            logger.error(f"Failed to parse assessment insights JSON: {response}")
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
        logger.exception("Error generating assessment insights")
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
        Data: {user_data}
        
        Return JSON:
        {{
            "insights": [{{"title": "T1", "desc": "D1"}}],
            "actions": [{{"title": "A1", "desc": "D1", "priority": "high"}}]
        }}
        """
        
        system_prompt = "You are a mental health coach."
        response = ask(prompt, system_prompt=system_prompt, max_tokens=500)
        
        clean_response = response.strip().replace('```json', '').replace('```', '')
        try:
            return json.loads(clean_response)
        except json.JSONDecodeError:
             logger.error(f"Failed to parse progress recommendations JSON: {response}")
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
        logger.exception("Error generating progress recommendations")
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
        Data: {detox_data}
        
        Return JSON:
        {{
            "analysis": "Brief analysis",
            "recommendations": ["Rec 1", "Rec 2"],
            "score": "Score/100 (string)"
        }}
        """
        
        system_prompt = "You are a digital wellness coach."
        response = ask(prompt, system_prompt=system_prompt, max_tokens=400)
        
        clean_response = response.strip().replace('```json', '').replace('```', '')
        try:
            return json.loads(clean_response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse digital detox insights JSON: {response}")
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
        logger.exception("Error generating digital detox insights")
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
        enhanced_prompt = f"User: {prompt}\nResponse:"
        system_prompt = "Supportive mental health assistant. Brief, empathetic (2-3 sentences)."
        
        return ask(enhanced_prompt, system_prompt=system_prompt, max_tokens=150)
    except Exception as e:
        logger.exception("Error generating chat response")
        return "I'm here to support you. How can I help you today?"

def generate_goal_suggestions(patient_data: dict) -> list:
    """
    Generate AI-powered goal suggestions based on patient data.
    """
    try:
        prompt = f"""
        Data: {patient_data}
        
        Suggest 3 goals. Return JSON array: [{{"title": "T", "description": "D"}}]
        """
        
        system_prompt = "Wellness coach."
        response = ask(prompt, system_prompt=system_prompt, max_tokens=300)
        
        clean_response = response.strip().replace('```json', '').replace('```', '')
        try:
            return json.loads(clean_response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse goal suggestions JSON: {response}")
            return []
    except Exception as e:
        logger.exception("Error generating goal suggestions")
        return []

def analyze_medication_adherence(medication_logs: list, patient_data: dict) -> dict:
    """
    Analyze medication adherence and provide insights.
    """
    try:
        prompt = f"""
        Logs: {medication_logs}
        Data: {patient_data}
        
        Return JSON:
        {{
            "adherence_score": 85,
            "insight": "Brief insight",
            "recommendation": "Brief rec"
        }}
        """
        
        system_prompt = "Medical assistant."
        response = ask(prompt, system_prompt=system_prompt, max_tokens=300)
        
        clean_response = response.strip().replace('```json', '').replace('```', '')
        try:
            return json.loads(clean_response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse medication adherence JSON: {response}")
            return {
                "adherence_score": 0,
                "insight": "Unable to analyze adherence at this time.",
                "recommendation": "Continue tracking your medication."
            }
    except Exception as e:
        logger.exception("Error analyzing medication adherence")
        return {
            "adherence_score": 0,
            "insight": "Unable to analyze adherence at this time.",
            "recommendation": "Continue tracking your medication."
        }

def generate_journal_insights(title: str, content: str, sentiment: str) -> str:
    """
    Generate AI-powered insights for a journal entry.
    """
    try:
        prompt = f"""
        Title: {title}
        Content: {content}
        Sentiment: {sentiment}
        
        Provide a supportive response with:
        1. Insights (2-3 sentences)
        2. Suggestions (3 bullet points)
        3. Coping Strategies (2-3 items)
        4. Encouragement (1 sentence)
        
        Format: Plain text with headers. Keep it under 800 chars.
        """
        
        system_prompt = "You are Dr. Anya, a compassionate wellness coach."
        return ask(prompt, system_prompt=system_prompt, max_tokens=400)
    except Exception as e:
        logger.exception("Error generating journal insights")
        return "Thank you for sharing. Consider discussing these feelings with a professional."

def analyze_voice_emotion(transcribed_text: str, audio_features: dict) -> str:
    """
    Analyze voice recording for emotion and insights.
    """
    try:
        prompt = f"""
        Text: {transcribed_text}
        Audio Features: {audio_features}
        
        Analyze emotion. Return format:
        EMOTION: [emotion]
        CONFIDENCE: [high/med/low]
        INSIGHTS: [brief explanation]
        SUGGESTIONS: [2 brief suggestions]
        """
        
        system_prompt = "You are an AI analyzing voice for emotion."
        return ask(prompt, system_prompt=system_prompt, max_tokens=300)
    except Exception as e:
        logger.exception("Error analyzing voice emotion")
        return "Neutral: Analysis unavailable."