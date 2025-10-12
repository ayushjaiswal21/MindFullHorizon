#!/usr/bin/env python3
"""
Simple Database Cleanup Script for MindFullHorizon
Applies database integrity fixes without complex imports.
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleDatabaseCleanup:
    def __init__(self, db_path):
        self.db_path = db_path
        self.stats = {
            'orphaned_records_deleted': 0,
            'uniqueness_violations_fixed': 0,
            'nullability_violations_fixed': 0,
            'logical_inconsistencies_fixed': 0,
            'errors': []
        }

    def execute_query(self, query, description):
        """Execute a database query safely"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            count = cursor.rowcount
            conn.close()
            logger.info(f"SUCCESS {description}: {count} records affected")
            return count
        except Exception as e:
            error_msg = f"ERROR {description}: {str(e)}"
            logger.error(error_msg)
            self.stats['errors'].append(error_msg)
            return 0

    def cleanup_orphaned_records(self):
        """Clean up all orphaned records"""
        logger.info("Starting orphaned records cleanup...")
        
        cleanup_queries = [
            # Blog system orphaned records
            ("DELETE FROM blog_likes WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned blog likes (invalid users)"),
            ("DELETE FROM blog_likes WHERE post_id NOT IN (SELECT id FROM blog_posts)", "Delete orphaned blog likes (invalid posts)"),
            ("DELETE FROM blog_comments WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned blog comments (invalid users)"),
            ("DELETE FROM blog_comments WHERE post_id NOT IN (SELECT id FROM blog_posts)", "Delete orphaned blog comments (invalid posts)"),
            ("DELETE FROM blog_comments WHERE parent_id IS NOT NULL AND parent_id NOT IN (SELECT id FROM blog_comments)", "Delete orphaned blog comments (invalid parents)"),
            ("DELETE FROM blog_posts WHERE author_id NOT IN (SELECT id FROM users)", "Delete orphaned blog posts"),
            
            # User-related orphaned records
            ("DELETE FROM assessments WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned assessments"),
            ("DELETE FROM digital_detox_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned digital detox logs"),
            ("DELETE FROM rpm_data WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned RPM data"),
            ("DELETE FROM gamification WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned gamification records"),
            ("DELETE FROM mood_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned mood logs"),
            ("DELETE FROM progress_recommendations WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned progress recommendations"),
            
            # Clinical and appointment orphaned records
            ("DELETE FROM clinical_notes WHERE provider_id NOT IN (SELECT id FROM users)", "Delete orphaned clinical notes (invalid providers)"),
            ("DELETE FROM clinical_notes WHERE patient_id NOT IN (SELECT id FROM users)", "Delete orphaned clinical notes (invalid patients)"),
            ("DELETE FROM appointments WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned appointments (invalid users)"),
            ("DELETE FROM appointments WHERE provider_id IS NOT NULL AND provider_id NOT IN (SELECT id FROM users)", "Delete orphaned appointments (invalid providers)"),
            ("DELETE FROM prescriptions WHERE provider_id NOT IN (SELECT id FROM users)", "Delete orphaned prescriptions (invalid providers)"),
            ("DELETE FROM prescriptions WHERE patient_id NOT IN (SELECT id FROM users)", "Delete orphaned prescriptions (invalid patients)"),
            
            # Goals and medication orphaned records
            ("DELETE FROM goals WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned goals"),
            ("DELETE FROM medications WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned medications"),
            ("DELETE FROM medication_logs WHERE medication_id NOT IN (SELECT id FROM medications)", "Delete orphaned medication logs (invalid medications)"),
            ("DELETE FROM medication_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned medication logs (invalid users)"),
            
            # Therapy session orphaned records
            ("DELETE FROM breathing_exercise_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned breathing exercise logs"),
            ("DELETE FROM yoga_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned yoga logs"),
            ("DELETE FROM music_therapy_logs WHERE user_id NOT IN (SELECT id FROM users)", "Delete orphaned music therapy logs"),
            
            # Notification orphaned records
            ("DELETE FROM notifications WHERE sender_id IS NOT NULL AND sender_id NOT IN (SELECT id FROM users)", "Delete orphaned notifications (invalid senders)"),
            ("DELETE FROM notifications WHERE recipient_id NOT IN (SELECT id FROM users)", "Delete orphaned notifications (invalid recipients)"),
        ]
        
        total_deleted = 0
        for query, description in cleanup_queries:
            count = self.execute_query(query, description)
            total_deleted += count
        
        # Update blog insights with NULL for orphaned posts
        self.execute_query(
            "UPDATE blog_insights SET most_popular_post_id = NULL WHERE most_popular_post_id IS NOT NULL AND most_popular_post_id NOT IN (SELECT id FROM blog_posts)",
            "Update orphaned blog insights"
        )
        
        self.stats['orphaned_records_deleted'] = total_deleted
        logger.info(f"Orphaned records cleanup completed: {total_deleted} records deleted")

    def fix_uniqueness_violations(self):
        """Fix uniqueness constraint violations"""
        logger.info("Starting uniqueness constraint violations fix...")
        
        # Fix duplicate emails
        count1 = self.execute_query("""
            UPDATE users 
            SET email = email || '_' || id
            WHERE email IN (
                SELECT email 
                FROM users 
                GROUP BY email 
                HAVING COUNT(*) > 1
            ) 
            AND id NOT IN (
                SELECT MIN(id) 
                FROM users 
                WHERE email IN (
                    SELECT email 
                    FROM users 
                    GROUP BY email 
                    HAVING COUNT(*) > 1
                )
                GROUP BY email
            )
        """, "Fix duplicate email addresses")
        
        # Fix duplicate Google IDs
        count2 = self.execute_query("""
            UPDATE users 
            SET google_id = NULL
            WHERE google_id IN (
                SELECT google_id 
                FROM users 
                WHERE google_id IS NOT NULL
                GROUP BY google_id 
                HAVING COUNT(*) > 1
            ) 
            AND id NOT IN (
                SELECT MIN(id) 
                FROM users 
                WHERE google_id IN (
                    SELECT google_id 
                    FROM users 
                    WHERE google_id IS NOT NULL
                    GROUP BY google_id 
                    HAVING COUNT(*) > 1
                )
                GROUP BY google_id
            )
        """, "Fix duplicate Google IDs")
        
        # Fix duplicate blog likes
        count3 = self.execute_query("""
            DELETE FROM blog_likes 
            WHERE id NOT IN (
                SELECT MAX(id) 
                FROM blog_likes 
                GROUP BY user_id, post_id
            )
        """, "Fix duplicate blog likes")
        
        total_fixed = count1 + count2 + count3
        self.stats['uniqueness_violations_fixed'] = total_fixed
        logger.info(f"Uniqueness violations fix completed: {total_fixed} records fixed")

    def fix_nullability_violations(self):
        """Fix nullability constraint violations"""
        logger.info("Starting nullability constraint violations fix...")
        
        nullability_fixes = [
            # User table fixes
            ("UPDATE users SET name = 'Unknown User' WHERE name IS NULL", "Fix NULL user names"),
            ("DELETE FROM users WHERE email IS NULL", "Delete users with NULL emails"),
            
            # Blog table fixes
            ("UPDATE blog_posts SET title = 'Untitled Post' WHERE title IS NULL", "Fix NULL blog post titles"),
            ("UPDATE blog_posts SET content = 'No content available' WHERE content IS NULL", "Fix NULL blog post content"),
            ("UPDATE blog_comments SET content = 'Comment removed' WHERE content IS NULL", "Fix NULL blog comment content"),
            
            # Assessment and wellness data fixes
            ("UPDATE assessments SET score = 0 WHERE score IS NULL", "Fix NULL assessment scores"),
            ("UPDATE digital_detox_logs SET screen_time_hours = 0 WHERE screen_time_hours IS NULL", "Fix NULL screen time"),
            ("UPDATE mood_logs SET mood_score = 5 WHERE mood_score IS NULL", "Fix NULL mood scores"),
            
            # Appointment fixes
            ("UPDATE appointments SET date = date('now') WHERE date IS NULL", "Fix NULL appointment dates"),
            ("UPDATE appointments SET time = '09:00' WHERE time IS NULL", "Fix NULL appointment times"),
            ("UPDATE appointments SET appointment_type = 'general' WHERE appointment_type IS NULL", "Fix NULL appointment types"),
            
            # Goal fixes
            ("UPDATE goals SET title = 'Untitled Goal' WHERE title IS NULL", "Fix NULL goal titles"),
            ("UPDATE goals SET category = 'general' WHERE category IS NULL", "Fix NULL goal categories"),
            ("UPDATE goals SET start_date = date('now') WHERE start_date IS NULL", "Fix NULL goal start dates"),
            
            # Medication fixes
            ("UPDATE medications SET name = 'Unknown Medication' WHERE name IS NULL", "Fix NULL medication names"),
            
            # Therapy log fixes
            ("UPDATE breathing_exercise_logs SET exercise_name = 'Unknown Exercise' WHERE exercise_name IS NULL", "Fix NULL breathing exercise names"),
            ("UPDATE yoga_logs SET session_name = 'Unknown Session' WHERE session_name IS NULL", "Fix NULL yoga session names"),
            
            # Prescription fixes
            ("UPDATE prescriptions SET medication_name = 'Unknown Medication' WHERE medication_name IS NULL", "Fix NULL prescription medication names"),
            ("UPDATE prescriptions SET dosage = 'As directed' WHERE dosage IS NULL", "Fix NULL prescription dosages"),
            
            # Clinical note fixes
            ("UPDATE clinical_notes SET session_date = datetime('now') WHERE session_date IS NULL", "Fix NULL clinical note session dates"),
            
            # Notification fixes
            ("UPDATE notifications SET type = 'message' WHERE type IS NULL", "Fix NULL notification types"),
            
            # Progress recommendation fixes
            ("UPDATE progress_recommendations SET recommendations = '[]' WHERE recommendations IS NULL", "Fix NULL progress recommendations"),
        ]
        
        total_fixed = 0
        for query, description in nullability_fixes:
            count = self.execute_query(query, description)
            total_fixed += count
        
        self.stats['nullability_violations_fixed'] = total_fixed
        logger.info(f"Nullability violations fix completed: {total_fixed} records fixed")

    def fix_logical_inconsistencies(self):
        """Fix logical inconsistencies"""
        logger.info("Starting logical inconsistencies fix...")
        
        logical_fixes = [
            # Status value fixes
            ("UPDATE appointments SET status = 'pending' WHERE status NOT IN ('pending', 'accepted', 'rejected', 'booked')", "Fix invalid appointment statuses"),
            ("UPDATE goals SET status = 'active' WHERE status NOT IN ('active', 'completed', 'paused')", "Fix invalid goal statuses"),
            ("UPDATE goals SET priority = 'medium' WHERE priority NOT IN ('low', 'medium', 'high')", "Fix invalid goal priorities"),
            ("UPDATE users SET role = 'patient' WHERE role IS NOT NULL AND role NOT IN ('patient', 'provider')", "Fix invalid user roles"),
            
            # Date-related fixes
            ("UPDATE appointments SET status = 'completed' WHERE date < date('now') AND status IN ('pending', 'accepted')", "Fix past appointments"),
            ("UPDATE goals SET target_date = date(start_date, '+30 days') WHERE target_date IS NOT NULL AND target_date < start_date", "Fix invalid goal date ranges"),
            ("UPDATE goals SET completed_date = date('now') WHERE status = 'completed' AND completed_date IS NULL", "Fix completed goals without completion dates"),
            ("UPDATE prescriptions SET expiry_date = datetime(issue_date, '+30 days') WHERE expiry_date IS NOT NULL AND expiry_date < issue_date", "Fix invalid prescription date ranges"),
            ("UPDATE clinical_notes SET session_date = datetime('now', '-1 day') WHERE session_date > datetime('now')", "Fix future clinical note session dates"),
            
            # Value range fixes
            ("UPDATE digital_detox_logs SET screen_time_hours = 0 WHERE screen_time_hours < 0", "Fix negative screen time"),
            ("UPDATE digital_detox_logs SET screen_time_hours = 24 WHERE screen_time_hours > 24", "Fix excessive screen time"),
            ("UPDATE mood_logs SET mood_score = 1 WHERE mood_score < 1", "Fix mood scores below 1"),
            ("UPDATE mood_logs SET mood_score = 10 WHERE mood_score > 10", "Fix mood scores above 10"),
            ("UPDATE breathing_exercise_logs SET duration_minutes = 0 WHERE duration_minutes < 0", "Fix negative breathing exercise duration"),
            ("UPDATE breathing_exercise_logs SET duration_minutes = 480 WHERE duration_minutes > 480", "Fix excessive breathing exercise duration"),
            ("UPDATE yoga_logs SET duration_minutes = 0 WHERE duration_minutes < 0", "Fix negative yoga duration"),
            ("UPDATE yoga_logs SET duration_minutes = 480 WHERE duration_minutes > 480", "Fix excessive yoga duration"),
            ("UPDATE blog_posts SET views = 0 WHERE views < 0", "Fix negative blog view counts"),
            ("UPDATE gamification SET points = 0 WHERE points < 0", "Fix negative gamification points"),
            ("UPDATE gamification SET streak = 0 WHERE streak < 0", "Fix negative gamification streaks"),
            
            # Assessment type fixes
            ("UPDATE assessments SET assessment_type = 'mood' WHERE assessment_type NOT IN ('GAD-7', 'PHQ-9', 'mood', 'Daily Mood')", "Fix invalid assessment types"),
            
            # Music therapy mood fixes
            ("UPDATE music_therapy_logs SET mood = 'calm' WHERE mood NOT IN ('happy', 'sad', 'angry', 'calm', 'anxious', 'focus')", "Fix invalid music therapy moods"),
            
            # Yoga difficulty level fixes
            ("UPDATE yoga_logs SET difficulty_level = 'Beginner' WHERE difficulty_level NOT IN ('Beginner', 'Intermediate', 'Advanced')", "Fix invalid yoga difficulty levels"),
        ]
        
        total_fixed = 0
        for query, description in logical_fixes:
            count = self.execute_query(query, description)
            total_fixed += count
        
        self.stats['logical_inconsistencies_fixed'] = total_fixed
        logger.info(f"Logical inconsistencies fix completed: {total_fixed} records fixed")

    def verify_fixes(self):
        """Verify that all fixes have been applied successfully"""
        logger.info("Verifying fixes...")
        
        verification_queries = [
            ("SELECT COUNT(*) FROM blog_posts WHERE author_id NOT IN (SELECT id FROM users)", "Orphaned blog posts"),
            ("SELECT COUNT(*) FROM blog_likes WHERE user_id NOT IN (SELECT id FROM users) OR post_id NOT IN (SELECT id FROM blog_posts)", "Orphaned blog likes"),
            ("SELECT COUNT(*) FROM assessments WHERE user_id NOT IN (SELECT id FROM users)", "Orphaned assessments"),
            ("SELECT COUNT(*) FROM appointments WHERE user_id NOT IN (SELECT id FROM users)", "Orphaned appointments"),
            ("SELECT COUNT(*) FROM users WHERE email IS NULL", "Users with NULL emails"),
            ("SELECT COUNT(*) FROM users WHERE name IS NULL", "Users with NULL names"),
            ("SELECT COUNT(*) FROM blog_posts WHERE title IS NULL", "Blog posts with NULL titles"),
            ("SELECT COUNT(*) FROM appointments WHERE status NOT IN ('pending', 'accepted', 'rejected', 'booked')", "Invalid appointment statuses"),
            ("SELECT COUNT(*) FROM goals WHERE status NOT IN ('active', 'completed', 'paused')", "Invalid goal statuses"),
            ("SELECT COUNT(*) FROM mood_logs WHERE mood_score < 1 OR mood_score > 10", "Invalid mood scores"),
            ("SELECT COUNT(*) FROM digital_detox_logs WHERE screen_time_hours < 0 OR screen_time_hours > 24", "Invalid screen time values"),
        ]
        
        issues_found = 0
        for query, description in verification_queries:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(query)
                result = cursor.fetchone()[0]
                conn.close()
                
                if result > 0:
                    logger.warning(f"WARNING {description}: {result} issues still found")
                    issues_found += result
                else:
                    logger.info(f"SUCCESS {description}: No issues found")
            except Exception as e:
                logger.error(f"ERROR verifying {description}: {str(e)}")
                issues_found += 1
        
        if issues_found == 0:
            logger.info("All verification checks passed! Database integrity restored.")
        else:
            logger.warning(f"{issues_found} issues still remain. Manual review may be required.")
        
        return issues_found == 0

    def run_cleanup(self):
        """Run the complete database cleanup process"""
        logger.info("Starting comprehensive database cleanup...")
        start_time = datetime.now()
        
        try:
            # Step 1: Clean up orphaned records
            self.cleanup_orphaned_records()
            
            # Step 2: Fix uniqueness violations
            self.fix_uniqueness_violations()
            
            # Step 3: Fix nullability violations
            self.fix_nullability_violations()
            
            # Step 4: Fix logical inconsistencies
            self.fix_logical_inconsistencies()
            
            # Step 5: Verify fixes
            verification_passed = self.verify_fixes()
            
            # Final statistics
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info("=" * 60)
            logger.info("CLEANUP SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Duration: {duration}")
            logger.info(f"Orphaned records deleted: {self.stats['orphaned_records_deleted']}")
            logger.info(f"Uniqueness violations fixed: {self.stats['uniqueness_violations_fixed']}")
            logger.info(f"Nullability violations fixed: {self.stats['nullability_violations_fixed']}")
            logger.info(f"Logical inconsistencies fixed: {self.stats['logical_inconsistencies_fixed']}")
            logger.info(f"Errors encountered: {len(self.stats['errors'])}")
            
            if self.stats['errors']:
                logger.info("\nERRORS:")
                for error in self.stats['errors']:
                    logger.error(f"  - {error}")
            
            if verification_passed:
                logger.info("\nDatabase cleanup completed successfully!")
            else:
                logger.warning("\nDatabase cleanup completed with some issues remaining.")
            
            return verification_passed
            
        except Exception as e:
            logger.error(f"Fatal error during cleanup: {str(e)}")
            return False

def main():
    """Main function to run the database cleanup"""
    print("MindFullHorizon Database Integrity Cleanup")
    print("=" * 50)
    
    # Find database file
    possible_db_files = [
        'instance/mindful_horizon.db',
        'mindful_horizon.db',
        'app.db',
        'instance/app.db',
        'database.db',
        'instance/database.db'
    ]
    
    db_file = None
    for file_path in possible_db_files:
        if os.path.exists(file_path):
            db_file = file_path
            break
    
    if not db_file:
        print("No SQLite database file found in common locations:")
        for path in possible_db_files:
            print(f"  - {path}")
        return
    
    print(f"Found database: {db_file}")
    
    # Run cleanup
    cleanup = SimpleDatabaseCleanup(db_file)
    success = cleanup.run_cleanup()
    
    if success:
        print("\nDatabase cleanup completed successfully!")
        print("Check the 'database_cleanup.log' file for detailed information.")
    else:
        print("\nDatabase cleanup completed with some issues.")
        print("Check the 'database_cleanup.log' file for details and errors.")

if __name__ == "__main__":
    main()
