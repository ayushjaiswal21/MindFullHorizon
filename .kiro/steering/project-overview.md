---
inclusion: always
---

# Mindful Horizon - Mental Health Platform

## Project Overview
Mindful Horizon is a comprehensive mental health platform built with Flask that provides:

- **Patient Dashboard**: Mood tracking, journal entries, voice logs, wellness reports
- **Provider Dashboard**: Patient management, appointment scheduling, analytics
- **AI-Powered Features**: Psychological assessments, chat support, personalized recommendations
- **Wellness Tools**: Breathing exercises, yoga videos, music therapy, digital detox
- **Gamification**: Achievement system and progress tracking
- **Telehealth**: Video consultations and appointment management

## Tech Stack
- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **AI Integration**: Gemini API for psychological assessments and chat
- **Frontend**: HTML/CSS/JavaScript with responsive design
- **Authentication**: Flask-Login with role-based access (patient/provider)
- **File Uploads**: Secure file handling for voice logs and documents

## Key Architecture Patterns
- **Modular Routes**: Organized in `/routes` directory by feature
- **AI Service Layer**: Abstracted AI implementations in `/ai` directory
- **Database Models**: Centralized in `models.py` with proper relationships
- **Security**: Decorators for authentication and role-based access control
- **Asset Management**: CSS/JS bundling with Flask-Assets

## Development Guidelines
- Follow Flask best practices for route organization
- Use SQLAlchemy for all database operations
- Implement proper error handling and logging
- Maintain responsive design principles
- Ensure HIPAA-compliant data handling for health information
- Test AI integrations thoroughly before deployment

## File Structure Notes
- `/templates`: Jinja2 templates with base template inheritance
- `/static`: CSS, JS, images, and uploaded files
- `/ai`: AI service implementations and interfaces
- `/utils`: Shared utilities and database helpers
- `/migrations`: Alembic database migration files