---
inclusion: always
---

# Development Standards for Mindful Horizon

## Code Quality Standards
- **Python Style**: Follow PEP 8 guidelines
- **Flask Patterns**: Use blueprints for route organization
- **Error Handling**: Always implement try-catch blocks for database operations
- **Logging**: Use proper logging levels (DEBUG, INFO, WARNING, ERROR)
- **Security**: Validate all user inputs and sanitize data

## Database Guidelines
- **Migrations**: Always create Alembic migrations for schema changes
- **Relationships**: Use proper SQLAlchemy relationships with lazy loading
- **Queries**: Optimize queries to prevent N+1 problems
- **Transactions**: Use database transactions for multi-step operations

## Frontend Standards
- **Responsive Design**: Mobile-first approach
- **Accessibility**: WCAG 2.1 AA compliance for healthcare accessibility
- **Performance**: Minimize JavaScript bundle sizes
- **Security**: Implement CSP headers and XSS protection

## AI Integration Best Practices
- **Error Handling**: Graceful fallbacks when AI services are unavailable
- **Rate Limiting**: Implement proper rate limiting for AI API calls
- **Data Privacy**: Never log sensitive patient data in AI requests
- **Testing**: Mock AI responses for consistent testing

## Security Requirements
- **HIPAA Compliance**: Encrypt sensitive health data
- **Authentication**: Multi-factor authentication for providers
- **Session Management**: Secure session handling with proper timeouts
- **File Uploads**: Validate file types and scan for malware
- **API Security**: Rate limiting and input validation on all endpoints