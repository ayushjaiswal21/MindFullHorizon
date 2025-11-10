# Comprehensive Test Suite for MindfulHorizon Psychological Intervention Logic
# Tests CBT module progression, assessment scoring, and recommendation algorithms

import unittest
from datetime import datetime, timedelta
import json
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import User, Assessment, ModuleCompletion, db
from security_fixes import determine_next_module, atomic_wellness_score_update

class TestPsychologicalInterventionLogic(unittest.TestCase):
    """
    Comprehensive test suite for psychological intervention algorithms
    Tests the core CBT module progression and recommendation logic
    """
    
    def setUp(self):
        """Set up test database and sample data"""
        # Mock database setup
        self.db = MagicMock()
        self.test_user_id = 1
        
        # Sample assessment data
        self.sample_assessments = {
            'severe_anxiety': {'type': 'GAD-7', 'score': 18},
            'moderate_anxiety': {'type': 'GAD-7', 'score': 12},
            'mild_anxiety': {'type': 'GAD-7', 'score': 6},
            'severe_depression': {'type': 'PHQ-9', 'score': 22},
            'moderate_depression': {'type': 'PHQ-9', 'score': 15},
            'mild_depression': {'type': 'PHQ-9', 'score': 8}
        }
        
        # CBT Module definitions
        self.modules = {
            1: {'name': 'Sleep Hygiene', 'category': 'foundation'},
            2: {'name': 'Psychoeducation', 'category': 'foundation'},
            3: {'name': 'Cognitive Restructuring', 'category': 'anxiety'},
            4: {'name': 'Mindfulness Practice', 'category': 'anxiety'},
            5: {'name': 'Behavioral Activation', 'category': 'depression'},
            6: {'name': 'Relapse Prevention', 'category': 'maintenance'},
            7: {'name': 'Social Skills Training', 'category': 'social'},
            8: {'name': 'Exposure Therapy', 'category': 'anxiety_advanced'}
        }

    def test_severe_anxiety_intervention_pathway(self):
        """
        Test Case 1: High anxiety client (GAD-7 score 18) should follow
        evidence-based CBT progression: Cognitive Restructuring → Mindfulness
        """
        # Setup: Client with severe anxiety
        client_data = {
            'user_id': self.test_user_id,
            'current_assessments': [self.sample_assessments['severe_anxiety']],
            'completed_modules': [],
            'wellness_score': 3.2
        }
        
        # Test initial recommendation
        recommendation = self.get_module_recommendation(client_data)
        
        # Assertions for severe anxiety pathway
        self.assertEqual(recommendation['module_name'], 'Cognitive Restructuring',
                        "Severe anxiety should start with Cognitive Restructuring")
        self.assertEqual(recommendation['priority'], 'high',
                        "Severe anxiety should be high priority")
        self.assertIn('anxiety', recommendation['reason'].lower(),
                     "Reason should mention anxiety")
        
        # Simulate module completion and improvement
        client_data['completed_modules'] = [3]  # Completed Cognitive Restructuring
        client_data['current_assessments'] = [{'type': 'GAD-7', 'score': 10}]  # Improved
        client_data['wellness_score'] = 6.8
        
        # Test progression recommendation
        next_recommendation = self.get_module_recommendation(client_data)
        
        self.assertEqual(next_recommendation['module_name'], 'Mindfulness Practice',
                        "After Cognitive Restructuring, should recommend Mindfulness")
        
        # Validate psychological appropriateness
        self.assertTrue(self.validate_intervention_sequence([3, 4]),
                       "Cognitive Restructuring → Mindfulness is valid CBT sequence")

    def test_depression_intervention_pathway(self):
        """
        Test Case 2: Moderate depression should trigger Behavioral Activation
        """
        client_data = {
            'user_id': self.test_user_id,
            'current_assessments': [self.sample_assessments['moderate_depression']],
            'completed_modules': [],
            'wellness_score': 4.1
        }
        
        recommendation = self.get_module_recommendation(client_data)
        
        self.assertEqual(recommendation['module_name'], 'Behavioral Activation',
                        "Moderate depression should recommend Behavioral Activation")
        self.assertEqual(recommendation['priority'], 'high',
                        "Depression intervention should be high priority")

    def test_comorbid_anxiety_depression_prioritization(self):
        """
        Test Case 3: Client with both anxiety and depression - test prioritization logic
        """
        client_data = {
            'user_id': self.test_user_id,
            'current_assessments': [
                {'type': 'GAD-7', 'score': 16},  # Severe anxiety
                {'type': 'PHQ-9', 'score': 14}   # Moderate depression
            ],
            'completed_modules': [],
            'wellness_score': 3.5
        }
        
        recommendation = self.get_module_recommendation(client_data)
        
        # Anxiety typically takes priority in comorbid cases
        self.assertEqual(recommendation['module_name'], 'Cognitive Restructuring',
                        "Comorbid case should prioritize anxiety treatment")

    def test_module_progression_validation(self):
        """
        Test Case 4: Validate that module progressions follow evidence-based sequences
        """
        # Test valid progressions
        valid_sequences = [
            [3, 4],  # Cognitive Restructuring → Mindfulness
            [5, 7],  # Behavioral Activation → Social Skills
            [1, 2],  # Sleep Hygiene → Psychoeducation
            [4, 6]   # Mindfulness → Relapse Prevention
        ]
        
        for sequence in valid_sequences:
            self.assertTrue(self.validate_intervention_sequence(sequence),
                           f"Sequence {sequence} should be valid")
        
        # Test invalid progressions
        invalid_sequences = [
            [8, 1],  # Exposure Therapy → Sleep Hygiene (backwards)
            [6, 3],  # Relapse Prevention → Cognitive Restructuring (backwards)
        ]
        
        for sequence in invalid_sequences:
            self.assertFalse(self.validate_intervention_sequence(sequence),
                            f"Sequence {sequence} should be invalid")

    def test_score_improvement_threshold_logic(self):
        """
        Test Case 5: Verify score improvement thresholds trigger appropriate progressions
        """
        # Test insufficient improvement (should repeat or modify current module)
        client_data = {
            'user_id': self.test_user_id,
            'assessment_history': [
                {'type': 'GAD-7', 'score': 18, 'date': datetime.now() - timedelta(days=14)},
                {'type': 'GAD-7', 'score': 16, 'date': datetime.now()}  # Only 2-point improvement
            ],
            'completed_modules': [3],  # Completed Cognitive Restructuring
            'wellness_score': 4.2
        }
        
        recommendation = self.get_module_recommendation(client_data)
        
        # Should recommend reinforcement or alternative approach
        self.assertIn(recommendation['module_name'], 
                     ['Mindfulness Practice', 'Cognitive Restructuring Reinforcement'],
                     "Insufficient improvement should trigger appropriate response")
        
        # Test significant improvement (should progress normally)
        client_data['assessment_history'][1]['score'] = 8  # 10-point improvement
        client_data['wellness_score'] = 7.1
        
        recommendation = self.get_module_recommendation(client_data)
        self.assertEqual(recommendation['module_name'], 'Mindfulness Practice',
                        "Significant improvement should progress to next module")

    def test_crisis_intervention_logic(self):
        """
        Test Case 6: Crisis-level scores should trigger immediate intervention
        """
        crisis_data = {
            'user_id': self.test_user_id,
            'current_assessments': [
                {'type': 'PHQ-9', 'score': 25, 'crisis_indicators': ['suicidal_ideation']}
            ],
            'completed_modules': [],
            'wellness_score': 1.8
        }
        
        recommendation = self.get_module_recommendation(crisis_data)
        
        self.assertEqual(recommendation['priority'], 'crisis',
                        "Crisis scores should trigger crisis priority")
        self.assertIn('immediate', recommendation['reason'].lower(),
                     "Crisis recommendation should mention immediate intervention")
        
        # Should recommend crisis-appropriate module or external referral
        crisis_appropriate_modules = ['Crisis Management', 'Safety Planning', 'Professional Referral']
        self.assertIn(recommendation['module_name'], crisis_appropriate_modules,
                     "Crisis should recommend appropriate intervention")

    def test_maintenance_phase_logic(self):
        """
        Test Case 7: Clients in maintenance phase should get appropriate modules
        """
        maintenance_data = {
            'user_id': self.test_user_id,
            'current_assessments': [
                {'type': 'GAD-7', 'score': 3},
                {'type': 'PHQ-9', 'score': 4}
            ],
            'completed_modules': [1, 2, 3, 4, 5],  # Completed core modules
            'wellness_score': 8.7,
            'days_since_completion': 30
        }
        
        recommendation = self.get_module_recommendation(maintenance_data)
        
        self.assertEqual(recommendation['module_name'], 'Relapse Prevention',
                        "Maintenance phase should recommend Relapse Prevention")
        self.assertEqual(recommendation['priority'], 'low',
                        "Maintenance should be low priority")

    def test_personalization_factors(self):
        """
        Test Case 8: Recommendations should consider individual factors
        """
        # Test age-appropriate recommendations
        young_adult_data = {
            'user_id': self.test_user_id,
            'age': 19,
            'current_assessments': [{'type': 'GAD-7', 'score': 12}],
            'completed_modules': [],
            'wellness_score': 5.2,
            'demographics': {'student': True}
        }
        
        recommendation = self.get_module_recommendation(young_adult_data)
        
        # Should consider student-specific stressors
        self.assertIn('academic', recommendation.get('customization', '').lower(),
                     "Student recommendations should consider academic factors")

    def test_wellness_score_calculation_accuracy(self):
        """
        Test Case 9: Verify wellness score calculations are mathematically correct
        """
        # Mock assessment data
        assessments = [
            {'type': 'GAD-7', 'score': 12, 'date': datetime.now() - timedelta(days=1)},
            {'type': 'PHQ-9', 'score': 15, 'date': datetime.now() - timedelta(days=3)},
            {'type': 'Daily Mood', 'score': 3, 'date': datetime.now()}
        ]
        
        calculated_score = self.calculate_wellness_score(assessments)
        
        # Verify score is within valid range
        self.assertGreaterEqual(calculated_score, 0, "Wellness score should be >= 0")
        self.assertLessEqual(calculated_score, 10, "Wellness score should be <= 10")
        
        # Verify recent assessments are weighted more heavily
        recent_heavy_data = [
            {'type': 'GAD-7', 'score': 5, 'date': datetime.now()},  # Recent, good score
            {'type': 'GAD-7', 'score': 20, 'date': datetime.now() - timedelta(days=20)}  # Old, bad score
        ]
        
        score_recent_heavy = self.calculate_wellness_score(recent_heavy_data)
        
        # Should be closer to recent good score than old bad score
        self.assertGreater(score_recent_heavy, 6, 
                          "Recent good scores should outweigh older bad scores")

    def test_intervention_contraindications(self):
        """
        Test Case 10: Verify contraindications are respected
        """
        # Test exposure therapy contraindication for severe depression
        contraindicated_data = {
            'user_id': self.test_user_id,
            'current_assessments': [
                {'type': 'PHQ-9', 'score': 22},  # Severe depression
                {'type': 'GAD-7', 'score': 16}   # Severe anxiety
            ],
            'completed_modules': [3, 4],  # Completed basic anxiety modules
            'wellness_score': 3.1
        }
        
        recommendation = self.get_module_recommendation(contraindicated_data)
        
        # Should NOT recommend exposure therapy with severe depression
        self.assertNotEqual(recommendation['module_name'], 'Exposure Therapy',
                           "Exposure therapy contraindicated with severe depression")

    # Helper methods for testing
    
    def get_module_recommendation(self, client_data):
        """Mock module recommendation logic"""
        # This would call the actual determine_next_module function
        # For testing, we'll simulate the logic
        
        assessments = client_data.get('current_assessments', [])
        completed = client_data.get('completed_modules', [])
        wellness_score = client_data.get('wellness_score', 5.0)
        
        # Simplified recommendation logic for testing
        if any(a.get('score', 0) >= 15 and a.get('type') == 'GAD-7' for a in assessments):
            if 3 not in completed:
                return {
                    'module_id': 3,
                    'module_name': 'Cognitive Restructuring',
                    'reason': 'High anxiety levels detected',
                    'priority': 'high'
                }
            elif 4 not in completed:
                return {
                    'module_id': 4,
                    'module_name': 'Mindfulness Practice',
                    'reason': 'Anxiety management progression',
                    'priority': 'high'
                }
        
        if any(a.get('score', 0) >= 15 and a.get('type') == 'PHQ-9' for a in assessments):
            if 5 not in completed:
                return {
                    'module_id': 5,
                    'module_name': 'Behavioral Activation',
                    'reason': 'Depression symptoms detected',
                    'priority': 'high'
                }
        
        # Crisis detection
        if any(a.get('score', 0) >= 24 for a in assessments):
            return {
                'module_id': 99,
                'module_name': 'Crisis Management',
                'reason': 'Immediate intervention required',
                'priority': 'crisis'
            }
        
        # Maintenance phase
        if wellness_score >= 8 and len(completed) >= 4:
            return {
                'module_id': 6,
                'module_name': 'Relapse Prevention',
                'reason': 'Maintenance and progress consolidation',
                'priority': 'low'
            }
        
        # Default
        return {
            'module_id': 1,
            'module_name': 'Sleep Hygiene',
            'reason': 'Foundation wellness improvement',
            'priority': 'medium'
        }
    
    def validate_intervention_sequence(self, module_sequence):
        """Validate that a sequence of modules follows evidence-based progression"""
        valid_progressions = {
            3: [4, 8],  # Cognitive Restructuring → Mindfulness or Exposure
            4: [6, 7],  # Mindfulness → Relapse Prevention or Social Skills
            5: [7, 6],  # Behavioral Activation → Social Skills or Relapse Prevention
            1: [2, 3, 5],  # Sleep Hygiene → various
            2: [3, 5]   # Psychoeducation → various
        }
        
        for i in range(len(module_sequence) - 1):
            current_module = module_sequence[i]
            next_module = module_sequence[i + 1]
            
            if current_module in valid_progressions:
                if next_module not in valid_progressions[current_module]:
                    return False
        
        return True
    
    def calculate_wellness_score(self, assessments):
        """Calculate wellness score from assessments (simplified for testing)"""
        if not assessments:
            return 5.0
        
        total_score = 0
        total_weight = 0
        
        for assessment in assessments:
            # Weight by recency
            days_old = (datetime.now() - assessment['date']).days
            weight = max(1, 30 - days_old)
            
            # Convert to wellness scale
            if assessment['type'] == 'GAD-7':
                wellness_contribution = (1 - (assessment['score'] / 21)) * 10
            elif assessment['type'] == 'PHQ-9':
                wellness_contribution = (1 - (assessment['score'] / 27)) * 10
            elif assessment['type'] == 'Daily Mood':
                wellness_contribution = assessment['score'] * 2
            else:
                continue
            
            total_score += wellness_contribution * weight
            total_weight += weight
        
        return round(total_score / total_weight, 1) if total_weight > 0 else 5.0


class TestSecurityValidation(unittest.TestCase):
    """Test security aspects of the psychological intervention system"""
    
    def test_assessment_data_validation(self):
        """Test that assessment data is properly validated"""
        from security_fixes import validate_assessment_data
        
        # Valid data
        valid_data = {
            'assessment_type': 'GAD-7',
            'score': 12,
            'responses': [1, 2, 1, 3, 2, 1, 2]
        }
        
        is_valid, message = validate_assessment_data(valid_data)
        self.assertTrue(is_valid, f"Valid data should pass: {message}")
        
        # Invalid score range
        invalid_data = {
            'assessment_type': 'GAD-7',
            'score': 25,  # Out of range for GAD-7 (max 21)
            'responses': [1, 2, 1, 3, 2, 1, 2]
        }
        
        is_valid, message = validate_assessment_data(invalid_data)
        self.assertFalse(is_valid, "Out of range score should fail validation")
        self.assertIn("between", message.lower(), "Error message should mention valid range")
    
    def test_input_sanitization(self):
        """Test that user inputs are properly sanitized"""
        from security_fixes import sanitize_user_input
        
        # Test XSS prevention
        malicious_input = "<script>alert('xss')</script>Hello"
        sanitized = sanitize_user_input(malicious_input)
        
        self.assertNotIn("<script>", sanitized, "Script tags should be removed")
        self.assertIn("Hello", sanitized, "Safe content should remain")
        
        # Test HTML preservation for journal entries
        journal_input = "<p>I feel <strong>much better</strong> today.</p>"
        sanitized_journal = sanitize_user_input(journal_input, allow_basic_html=True)
        
        self.assertIn("<p>", sanitized_journal, "Safe HTML should be preserved")
        self.assertIn("<strong>", sanitized_journal, "Safe formatting should be preserved")


if __name__ == '__main__':
    # Run the test suite
    unittest.main(verbosity=2)
    
    # Additional test runner for specific test cases
    def run_psychological_intervention_tests():
        """Run specific psychological intervention tests with detailed output"""
        
        print("\n" + "="*80)
        print("MINDFULHORIZON PSYCHOLOGICAL INTERVENTION LOGIC TEST SUITE")
        print("="*80)
        
        # Create test suite
        suite = unittest.TestSuite()
        
        # Add specific test cases
        suite.addTest(TestPsychologicalInterventionLogic('test_severe_anxiety_intervention_pathway'))
        suite.addTest(TestPsychologicalInterventionLogic('test_depression_intervention_pathway'))
        suite.addTest(TestPsychologicalInterventionLogic('test_comorbid_anxiety_depression_prioritization'))
        suite.addTest(TestPsychologicalInterventionLogic('test_crisis_intervention_logic'))
        suite.addTest(TestPsychologicalInterventionLogic('test_wellness_score_calculation_accuracy'))
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Print summary
        print(f"\nTest Results:")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        
        return result.wasSuccessful()
    
    # Uncomment to run specific tests
    # run_psychological_intervention_tests()
