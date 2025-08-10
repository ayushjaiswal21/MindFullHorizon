import random

def predict_risk_score(assessment_responses):
    """
    This is a dummy function that simulates an ML model's prediction.
    It returns a random risk score and some placeholder insights.

    In your final project, you would replace this with your
    trained scikit-learn model, which would take the assessment
    responses as input and predict a real risk score.
    """
    # A simple dummy logic: higher responses lead to a higher score
    total_score = sum(int(response) for response in assessment_responses)
    
    # Scale the score to a 0-100 range
    # Assuming 2 questions with max score of 3 each, total max score is 6
    max_possible_score = len(assessment_responses) * 3
    
    if max_possible_score > 0:
        risk_score = int((total_score / max_possible_score) * 100)
    else:
        risk_score = random.randint(0, 100) # Fallback to random if no data

    insights = [
        "Your responses indicated a significant amount of stress.",
        "Your reported sleep difficulties were a major contributing factor.",
        "You mentioned reduced engagement with friends and family."
    ]

    return risk_score, insights
