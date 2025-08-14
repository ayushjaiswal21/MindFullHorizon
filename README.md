# MindFull Horizon - Enhanced Mental Health Web Application

A comprehensive Flask-based web application for mental health management with **advanced AI integration**, **real-time monitoring**, and **dynamic user experience**. Features separate dashboards for patients and healthcare providers with gamification, remote patient monitoring, AI-powered documentation, and telehealth capabilities.

## 🆕 Latest Enhancements (v2.0)


### AI Integration & User Experience
- **Explicit AI Interaction Cues**: Visual loading spinners and "Analyzing with Mindwell..." messages during AI processing
- **AI Debug Mode**: Optional display of raw JSON output from AI analysis for demonstration purposes
- **Real-time RPM Data**: Live updates of heart rate, sleep, steps, and mood score every 10 seconds
- **AJAX Form Submissions**: Instant UI updates without page reloads for better user experience
- **Enhanced Gamification Feedback**: Animated pop-ups and banners for points, streaks, and badge achievements
- **Interactive Chat**: Real-time chat with typing indicators and automated AI-powered responses
- **Advanced Data Visualization**: Chart.js integration replacing basic canvas charts
- **Comprehensive Logging**: Detailed logging system for debugging and monitoring
- **Enhanced CSS Animations**: Smooth transitions, typing indicators, and real-time data animations

## Features

### Patient-Facing Features
- **🎮 Enhanced Gamification System**: Points, streaks, and badges with animated feedback and real-time updates
- **📊 Real-time Remote Patient Monitoring (RPM)**: Live health data tracking with 10-second updates and automated alerts
- **💬 Interactive Communication Tools**: 
  - Enhanced chat with typing indicators and AI-powered responses
  - Telehealth session interface with mock interactivity
  - Real-time message processing and feedback
- **📅 Self-Scheduling**: Interactive appointment booking system
- **📱 Dynamic Dashboard**: Mobile-friendly interface with real-time data visualization and Chart.js integration
- **🧠 AI-Powered Digital Detox**: 
  - AJAX form submissions with loading indicators
  - Real-time AI analysis with visual feedback
  - Correlation charts showing screen time vs academic performance
  - Instant gamification rewards and badge notifications

### Provider-Facing Features
- **👥 Enhanced Caseload Management**: Comprehensive patient list with risk assessment and real-time status tracking
- **🤖 Advanced AI-Powered Documentation**: 
  - Automated clinical note generation with processing time display
  - Raw AI output visualization for transparency
  - Real-time analysis feedback and logging
- **📈 Business Intelligence Dashboard**: Practice analytics with Chart.js visualizations and performance metrics
- **🔗 Interoperability Support**: Integration with major EHR systems and healthcare networks
- **💊 Digital Therapeutics (DTx)**: Evidence-based digital intervention modules
- **📋 Real-time Analytics**: Live data updates and correlation analysis for better patient insights

## Technology Stack

- **Backend**: Flask (Python) with comprehensive logging
- **Frontend**: HTML5, Tailwind CSS, Enhanced JavaScript with AJAX
- **Data Visualization**: Chart.js for interactive charts and graphs
- **AI Integration**: Ollama ALIENTELLIGENCE/mindwell model with real-time processing
- **Authentication**: Flask sessions with role-based access control
- **Data Storage**: SQLAlchemy with SQLite (production-ready database integration)
- **Styling**: Tailwind CSS with custom components and enhanced animations
- **Icons**: Font Awesome 6.5.2
- **Real-time Features**: JavaScript intervals for live data updates
- **Enhanced UX**: Custom CSS animations, typing indicators, and loading states

## Project Structure

```
MindFullHorizon/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # Project documentation
├── templates/            # Jinja2 HTML templates
│   ├── base.html         # Base template with navigation
│   ├── index.html        # Landing page
│   ├── login.html        # Authentication page
│   ├── patient_dashboard.html    # Patient dashboard
│   ├── provider_dashboard.html   # Provider dashboard
│   ├── chat.html         # Chat interface
│   ├── schedule.html     # Appointment scheduling
│   ├── ai_documentation.html    # AI note generation
│   └── telehealth.html   # Video session interface
└── static/              # Static assets
    ├── css/
    │   ├── styles.css   # Original custom styles
    │   └── enhanced.css # New enhanced styles with animations
    └── js/
        └── scripts.js   # Enhanced JavaScript with AJAX and real-time features
        └── scripts.js   # Client-side functionality
```

## Installation & Setup

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd MindFullHorizon
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   - Open your browser and navigate to `http://127.0.0.1:5000`
   - Use the demo credentials provided in the login interface

## Demo Credentials

### Patient Login
- **Email**: patient@example.com
- **Password**: password
- **Role**: Patient

### Provider Login
- **Email**: provider@example.com
- **Password**: password
- **Role**: Provider

## Key Components Explained

### Authentication System
- Role-based access control with decorators
- Session management for secure user state
- Separate login flows for patients and providers

### Patient Dashboard
- **Gamification**: Dynamic point system with streak tracking and badge awards
- **RPM Monitoring**: Simulated health data with alert thresholds
- **Quick Actions**: Direct access to communication and scheduling tools

### Provider Dashboard
- **Caseload Table**: Sortable patient list with risk indicators
- **BI Analytics**: Practice performance metrics and engagement statistics
- **AI Documentation**: Natural language processing for clinical notes

### Data Management
- Mock data structures simulate real database functionality
- Easy migration path to PostgreSQL, MySQL, or MongoDB
- HIPAA-compliant data handling patterns

### Security Features
- CSRF protection through Flask's built-in security
- Session-based authentication
- Role-based route protection
- Input validation and sanitization

## Customization

### Adding New Features
1. Create new routes in `app.py`
2. Add corresponding HTML templates in `templates/`
3. Update navigation in `base.html`
4. Add any required JavaScript to `static/js/scripts.js`

### Database Integration
Replace the in-memory dictionaries with your preferred database:
```python
# Example with SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'your-database-url'
db = SQLAlchemy(app)
```

### Styling Customization
- Modify `static/css/styles.css` for custom styles
- Update Tailwind classes in templates for layout changes
- Add new animations and transitions as needed

## Production Deployment

### Environment Variables
```bash
export FLASK_ENV=production
export SECRET_KEY=your-secure-secret-key
export DATABASE_URL=your-database-connection-string
```

### Security Considerations
- Change the default secret key
- Implement proper database with encryption
- Add HTTPS/SSL certificates
- Set up proper logging and monitoring
- Implement rate limiting
- Add CSRF tokens to all forms

### Recommended Hosting
- **Heroku**: Easy deployment with PostgreSQL add-on
- **AWS**: EC2 with RDS for scalability
- **DigitalOcean**: App Platform for simplicity
- **Google Cloud**: Cloud Run for containerized deployment

## API Integration

The application is designed to easily integrate with:
- **EHR Systems**: Epic, Cerner, Allscripts
- **Telehealth Platforms**: Zoom Healthcare, Doxy.me, WebRTC
- **Payment Processing**: Stripe, Square
- **Analytics**: Google Analytics, Mixpanel
- **Communication**: Twilio, SendGrid

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For technical support or questions about implementation:
- Create an issue in the repository
- Contact the development team
- Check the documentation for common solutions

## Future Enhancements

- Real-time notifications with WebSocket
- Mobile app development with React Native
- Advanced AI/ML models for predictive analytics
- Integration with wearable devices
- Multi-language support
- Advanced reporting and analytics dashboard
