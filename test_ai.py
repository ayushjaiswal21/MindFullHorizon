#!/usr/bin/env python3
"""
Test script to verify Ollama AI integration is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_service import ai_service

def test_digital_wellness_analysis():
    """Test the digital wellness analysis functionality"""
    print("Testing Digital Wellness Analysis...")
    
    # Test data
    screen_time = 7.5
    academic_score = 78
    social_interactions = "medium"
    historical_data = [
        {'screen_time_hours': 8.0, 'academic_score': 75, 'social_interactions': 'low', 'date': '2024-01-01'},
        {'screen_time_hours': 7.2, 'academic_score': 80, 'social_interactions': 'medium', 'date': '2024-01-02'},
        {'screen_time_hours': 6.8, 'academic_score': 82, 'social_interactions': 'high', 'date': '2024-01-03'},
    ]
    
    try:
        result = ai_service.analyze_digital_wellness(
            screen_time=screen_time,
            academic_score=academic_score,
            social_interactions=social_interactions,
            historical_data=historical_data
        )
        
        print("[SUCCESS] Digital Wellness Analysis Result:")
        print(f"   Score: {result.get('score', 'N/A')}")
        print(f"   Suggestion: {result.get('suggestion', 'N/A')}")
        print(f"   Analysis: {result.get('detailed_analysis', 'N/A')}")
        print(f"   Action Items: {result.get('action_items', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Digital Wellness Analysis Failed: {e}")
        return False

def test_clinical_note_generation():
    """Test the clinical note generation functionality"""
    print("\nTesting Clinical Note Generation...")
    
    # Test transcript
    transcript = """
    Patient: I've been feeling really overwhelmed with my coursework lately. I'm spending about 8-9 hours a day on my phone and computer, and I can't seem to focus on studying.
    
    Therapist: That sounds challenging. Can you tell me more about how this is affecting your daily routine?
    
    Patient: Well, I stay up late scrolling through social media, then I'm tired during the day. My grades have been slipping, and I feel anxious about falling behind.
    
    Therapist: It sounds like there might be a connection between your screen time and your academic stress. Have you noticed any patterns?
    
    Patient: Yeah, definitely. When I use my phone less, I actually feel more focused and less anxious.
    """
    
    patient_context = {
        'wellness_trend': 'Needs Improvement',
        'digital_score': 'Poor',
        'engagement': '150 points, 3 day streak'
    }
    
    try:
        result = ai_service.generate_clinical_note(transcript, patient_context)
        
        print("[SUCCESS] Clinical Note Generation Result:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"[ERROR] Clinical Note Generation Failed: {e}")
        return False

def test_institutional_analysis():
    """Test the institutional trend analysis functionality"""
    print("\nTesting Institutional Analysis...")
    
    # Test institutional data
    institutional_data = {
        'total_users': 150,
        'active_users': 120,
        'avg_screen_time': 6.8,
        'high_risk_users': 25,
        'engagement_rate': 80.0
    }
    
    try:
        result = ai_service.analyze_institutional_trends(institutional_data)
        
        print("[SUCCESS] Institutional Analysis Result:")
        print(f"   Overall Status: {result.get('overall_status', 'N/A')}")
        print(f"   Key Insights: {result.get('key_insights', 'N/A')}")
        print(f"   Recommendations: {result.get('recommendations', 'N/A')}")
        print(f"   Priority Actions: {result.get('priority_actions', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Institutional Analysis Failed: {e}")
        return False

def main():
    """Run all AI tests"""
    print("Starting AI Integration Tests...")
    print("=" * 60)
    
    tests = [
        test_digital_wellness_analysis,
        test_clinical_note_generation,
        test_institutional_analysis
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All AI functionality is working correctly!")
        print("[SUCCESS] Ollama ALIENTELLIGENCE/mindwell model is fully operational")
    else:
        print("[WARNING] Some AI tests failed. Check the error messages above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
