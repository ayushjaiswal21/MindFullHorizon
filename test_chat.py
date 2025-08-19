#!/usr/bin/env python3
"""
Test script for optimized AI chat functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_service import ai_service

def test_chat_responses():
    """Test various chat scenarios"""
    
    print("🤖 Testing Optimized AI Chat Responses")
    print("=" * 50)
    
    # Test cases
    test_messages = [
        "I'm feeling anxious about my exams",
        "I can't sleep and I'm stressed",
        "Everything feels overwhelming",
        "I'm having a good day today",
        "How can I manage my screen time better?"
    ]
    
    user_context = {
        'wellness_score': 'Good',
        'engagement_level': 'Active'
    }
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. User: {message}")
        
        try:
            result = ai_service.generate_chat_response(message, user_context)
            
            status = "🤖 AI" if result['is_ai_powered'] else "💬 Fallback"
            print(f"   {status}: {result['response']}")
            
            if result.get('needs_followup'):
                print("   ⚠️  Needs follow-up")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test crisis detection
    print(f"\n🚨 Testing Crisis Detection")
    print("-" * 30)
    
    crisis_message = "I feel hopeless and want to hurt myself"
    print(f"User: {crisis_message}")
    
    try:
        result = ai_service.generate_chat_response(crisis_message, user_context)
        print(f"🚨 Crisis Response: {result['response']}")
        print(f"   Follow-up needed: {result.get('needs_followup', False)}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_chat_responses()
