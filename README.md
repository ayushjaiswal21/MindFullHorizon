# MindFull Horizon - Mental Health Web Application

A comprehensive Flask-based web application for mental health management, featuring separate dashboards for patients and healthcare providers with advanced features like gamification, remote patient monitoring, AI-powered documentation, and telehealth capabilities.

## Features

### Patient-Facing Features
- **Gamification System**: Points, streaks, and badges to encourage engagement
- **Remote Patient Monitoring (RPM)**: Real-time health data tracking with automated alerts
- **Communication Tools**: Integrated chat support and telehealth session interface
- **Self-Scheduling**: Interactive appointment booking system
- **Responsive Dashboard**: Mobile-friendly interface with real-time data visualization

### Provider-Facing Features
- **Caseload Management**: Comprehensive patient list with risk assessment and status tracking
- **AI-Powered Documentation**: Automated clinical note generation from session transcripts
- **Business Intelligence Dashboard**: Practice analytics and performance metrics
- **Interoperability Support**: Integration with major EHR systems and healthcare networks
- **Digital Therapeutics (DTx)**: Evidence-based digital intervention modules

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Authentication**: Flask sessions with role-based access control
- **Data Storage**: In-memory dictionaries (easily replaceable with database)
- **Styling**: Tailwind CSS with custom components
- **Icons**: Font Awesome 6.5.2

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
    │   └── styles.css   # Custom styles and animations
    └── js/
        └── scripts.js   # Client-side functionality
```

## Installation & Setup

1. **Clone or download the project**
   ```bash
   cd MindFullHorizon
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   - Open your browser and navigate to `http://localhost:5000`

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
