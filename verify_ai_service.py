import asyncio
import logging
from ai.service import (
    ask_with_severity,
    generate_assessment_insights,
    generate_progress_recommendations,
    generate_digital_detox_insights,
    generate_chat_response,
    generate_goal_suggestions,
    analyze_medication_adherence,
    generate_journal_insights,
    analyze_voice_emotion
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_service():
    print("--- Testing AI Service ---")

    # 1. Test Chat Response
    print("\n1. Testing Chat Response...")
    response = await ask_with_severity("I'm feeling a bit anxious today.", "user123")
    print(f"Chat Response: {response}")

    # 2. Test Assessment Insights
    print("\n2. Testing Assessment Insights...")
    score = 15
    responses = {"q1": 3, "q2": 3} # Severe anxiety example
    insights = generate_assessment_insights("GAD-7", score, responses)
    print(f"Assessment Insights: {insights}")

    # 3. Test Journal Insights
    print("\n3. Testing Journal Insights...")
    journal_insights = generate_journal_insights(
        "My Day", 
        "I felt really overwhelmed at work today. Too many deadlines.", 
        "Negative"
    )
    print(f"Journal Insights: {journal_insights}")

    # 4. Test Voice Analysis
    print("\n4. Testing Voice Analysis...")
    voice_analysis = analyze_voice_emotion(
        "I am just so tired of everything.", 
        {"mean_pitch": 120, "mean_energy": 0.02} # Low pitch/energy -> Sad
    )
    print(f"Voice Analysis: {voice_analysis}")

    print("\n--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_ai_service())
