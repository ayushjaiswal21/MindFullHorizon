-- Insert demo users for MindFull Horizon
-- Run this with: sqlite3 instance/mindful_horizon.db < insert_demo_users.sql

-- Delete existing demo users if they exist
DELETE FROM gamification WHERE user_id IN (
    SELECT id FROM users WHERE email IN ('patient@example.com', 'provider@example.com')
);
DELETE FROM users WHERE email IN ('patient@example.com', 'provider@example.com');

-- Insert demo patient
INSERT INTO users (email, password_hash, name, role, institution, created_at) 
VALUES (
    'patient@example.com',
    'scrypt:32768:8:1$VQxQJQxQJQxQ$5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    'Demo Patient',
    'patient',
    'Demo University',
    datetime('now')
);

-- Insert demo provider  
INSERT INTO users (email, password_hash, name, role, institution, created_at)
VALUES (
    'provider@example.com', 
    'scrypt:32768:8:1$VQxQJQxQJQxQ$5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
    'Demo Provider',
    'provider', 
    'Demo University',
    datetime('now')
);

-- Add gamification for patient (get the user_id from the insert)
INSERT INTO gamification (user_id, points, streak, badges, last_activity)
SELECT id, 50, 3, '["Welcome"]', date('now')
FROM users 
WHERE email = 'patient@example.com' AND role = 'patient';

-- Verify users were created
SELECT 'Demo users created:' as message;
SELECT email, name, role FROM users WHERE email IN ('patient@example.com', 'provider@example.com');