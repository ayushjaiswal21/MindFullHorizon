# MindFull Horizon - Dynamic Mental Health Assessment System

A comprehensive Flask-based web application implementing the **Mindful Horizon Framework** for dynamic psychological health assessment of college students. This system provides real-time monitoring, AI-powered analysis, and gamified engagement through separate dashboards for patients and healthcare providers.

## 🎯 Project Overview

MindFull Horizon is a revolutionary mental health platform that moves beyond static assessments to provide dynamic, real-time psychological health monitoring. Built specifically for college students, it integrates multi-modal data analysis including self-reported metrics, physiological monitoring, and digital behavior patterns.

### Core Philosophy
- **Proactive vs Reactive Care**: Early detection of psychological distress through continuous monitoring
- **Gamified Engagement**: Interactive feedback loops to maintain student participation
- **AI-Driven Insights**: Automated analysis using the Gemini API
- **Data-Driven Decisions**: Integration of screen time, academic performance, and social interaction data

## 🚀 Key Features

### Patient Dashboard - Gamified Mental Wellness
- **🎮 Gamification System**: Points, streak tracking, and achievement badges
- **📊 Remote Patient Monitoring (RPM)**: Real-time health metrics with automated alerts
- **💬 AI-Powered Chat Interface**: Interactive communication with simulated bot responses
- **📅 Self-Scheduling System**: Intuitive appointment booking with date/time selection
- **🔗 Telehealth Integration**: WebRTC video session interface for remote consultations
- **📱 Digital Detox Tools**: Screen time analysis with academic performance correlation
- **💊 Medication Tracking**: Daily medication logging with adherence insights
- **🧘 Wellness Activities**: Breathing exercises and yoga session tracking
- **🎯 Goal Setting**: Personalized goal management with progress tracking

### Provider Dashboard - Clinical Excellence
- **👥 Caseload Management**: Comprehensive patient tracking with risk level assessment
- **🤖 AI-Powered Documentation**: Automated clinical note generation from session transcripts
- **📈 Business Intelligence**: Practice analytics with engagement metrics and performance indicators
- **📋 Prescription Management**: Digital prescription sending and tracking
- **📈 Wellness Reports**: Comprehensive patient progress reports with AI insights

## 🏗️ System Architecture

The MindFull Horizon system is built on a robust, scalable architecture designed for healthcare environments:

### Backend Infrastructure
- **Flask Application Server**: RESTful API with role-based authentication
- **SQLAlchemy ORM**: Database abstraction layer for easy migration
- **Session Management**: Secure user state handling with decorators
- **AI Integration**: Google Gemini API integration
- **Logging System**: Comprehensive audit trails and debugging support

### Frontend Experience
- **Responsive Design**: Mobile-first approach using Tailwind CSS
- **Real-time Updates**: JavaScript intervals for live data synchronization
- **Interactive Visualizations**: Chart.js for dynamic data representation
- **Progressive Enhancement**: AJAX forms with graceful fallbacks

## 💻 Technology Stack

### Core Technologies
- **Backend Framework**: Flask (Python 3.8+)
- **Database ORM**: SQLAlchemy with PostgreSQL (production)
- **Frontend**: HTML5, Tailwind CSS 3.x, Vanilla JavaScript, Chart.js 4.x
- **AI/ML**: Google Gemini API
- **Authentication**: Flask-Session with role-based access control
- **Real-time Communication**: Flask-SocketIO for WebRTC telehealth

## Project Structure

```
MindFullHorizon/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── ai_service.py          # AI service for mental health analysis
├── models.py              # SQLAlchemy models
├── init_db.py             # Database initialization script
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── patient_dashboard.html
│   ├── provider_dashboard.html
│   └── ... (and many more)
└── static/                # Static assets
    ├── css/
    │   ├── styles.css
    │   └── enhanced.css
    └── js/
        └── scripts.js
```

## 🚀 Cloud Deployment Guide (Render.com)

1.  **Create a Render account** and connect your GitHub repository.
2.  **Create a new Web Service** and a new **PostgreSQL Database**.
3.  **Configure the Web Service**:
    *   **Runtime**: `Python 3.13`
    *   **Build Command**: `pip install -r requirements.txt && python init_db.py`
    *   **Start Command**: `gunicorn app:app`
4.  **Add Environment Variables**:
    *   `FLASK_APP`: `app.py`
    *   `FLASK_ENV`: `production`
    *   `SECRET_KEY`: (generate a new one)
    *   `GEMINI_API_KEY`: (your Google Gemini API key)
    *   `DATABASE_URL`: (from the PostgreSQL database service)

## 🔧 Troubleshooting

-   **Database Connection Errors**: Ensure `DATABASE_URL` is correctly set and the database is running.
-   **AI Service Unavailable**: Verify `GEMINI_API_KEY` is set correctly.
-   **Build Failures**: Check `requirements.txt` for compatibility and Python version.