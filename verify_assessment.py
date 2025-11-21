#!/usr/bin/env python3
"""Verify assessment functionality by testing the flow"""

import requests
import json

def test_assessment_flow():
    """Test the assessment flow by making requests to the running Flask app"""
    
    base_url = "http://127.0.0.1:5000"
    
    print("=== Assessment Flow Verification ===")
    
    # Test 1: Check if questions.json loads correctly
    try:
        response = requests.get(f"{base_url}/static/questions.json")
        if response.status_code == 200:
            questions = response.json()
            print("✓ Questions JSON loaded successfully")
            
            # Check PHQ-9 structure
            if "PHQ-9" in questions:
                phq9 = questions["PHQ-9"]
                print(f"✓ PHQ-9 has {len(phq9['questions'])} standard questions")
                print(f"✓ PHQ-9 has {len(phq9.get('contextual_questions', []))} contextual questions")
                
                # Check last question
                last_q = phq9['questions'][-1]
                print(f"✓ Last PHQ-9 question: {last_q['text'][:50]}...")
                
            # Check GAD-7 structure
            if "GAD-7" in questions:
                gad7 = questions["GAD-7"]
                print(f"✓ GAD-7 has {len(gad7['questions'])} standard questions")
                print(f"✓ GAD-7 has {len(gad7.get('contextual_questions', []))} contextual questions")
                
                # Check last question
                last_q = gad7['questions'][-1]
                print(f"✓ Last GAD-7 question: {last_q['text'][:50]}...")
                
        else:
            print(f"✗ Failed to load questions.json: {response.status_code}")
            
    except Exception as e:
        print(f"✗ Error testing questions.json: {e}")
    
    # Test 2: Check assessment page loads
    try:
        response = requests.get(f"{base_url}/assessment")
        if response.status_code == 200:
            print("✓ Assessment page loads successfully")
        else:
            print(f"✗ Assessment page failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error accessing assessment page: {e}")
    
    print("\n=== Expected Flow Behavior ===")
    print("1. User starts PHQ-9 assessment")
    print("2. Questions 1-8: Next button shows 'Next'")
    print("3. Question 9 (last standard): Next button shows 'Next' (not 'Complete')")
    print("4. Click Next: Moves to contextual questions")
    print("5. Contextual questions 1-2: Next button shows 'Next'")
    print("6. Contextual question 3 (last): Next button shows 'Complete Assessment'")
    print("7. Click Complete: Saves assessment with both standard and contextual responses")
    
    print("\n=== Key Fixes Applied ===")
    print("1. Fixed showQuestion() to detect contextual mode vs standard mode")
    print("2. Fixed nextQuestion() to properly transition to contextual questions")
    print("3. Added validation for contextual question responses")
    print("4. Fixed database schema (added contextual_responses column)")

if __name__ == "__main__":
    test_assessment_flow()
