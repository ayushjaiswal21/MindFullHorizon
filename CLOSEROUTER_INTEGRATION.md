# CloseRouter AI Integration Guide

## Overview

MindFull Horizon integrates with CloseRouter's universal AI model gateway to provide advanced AI-powered mental health insights and clinical documentation. This integration enables access to 150+ AI models through a single API endpoint.

## Features

### 🤖 Multi-Model AI Analysis
- **Clinical Documentation**: Claude 3.5 Sonnet for professional clinical notes
- **Sentiment Analysis**: GPT-4o for emotional tone analysis
- **Risk Assessment**: o3-mini for reasoning-based risk evaluation
- **Digital Wellness**: GPT-4o for screen time and academic performance correlation
- **Institutional Analytics**: GPT-4o for campus-wide mental health trends

### 🔄 Intelligent Fallback System
- Automatic model switching when primary models are unavailable
- Graceful degradation to fallback responses
- Rate limit handling with exponential backoff
- Comprehensive error recovery

### 📊 Enhanced Analytics
- Real-time rate limit monitoring
- API status health checks
- Model performance tracking
- Usage analytics and optimization

## Configuration

### Environment Variables

Create a `.env` file in your project root with the following configuration:

```bash
# CloseRouter AI Service Configuration
CLOSEROUTER_API_KEY=your-closerouter-api-key-here
AI_EXTERNAL_CALLS_ENABLED=true

# AI Model Configuration (CloseRouter Models)
AI_MODEL_PRIMARY=gpt-4o
AI_MODEL_FAST=gpt-4o-mini
AI_MODEL_REASONING=o3-mini
AI_MODEL_CLINICAL=claude-3-5-sonnet-20241022
AI_MODEL_ANALYTICS=gpt-4o
AI_MODEL_VISION=gpt-4o
AI_MODEL_SEARCH=gpt-4o-search-preview-2025-03-11

# CloseRouter Configuration
CLOSEROUTER_BASE_URL=https://api.closerouter.com/v1
```

### Model Selection

The system uses different models for different use cases:

| Use Case | Primary Model | Fallback Models |
|----------|---------------|-----------------|
| Clinical Documentation | Claude 3.5 Sonnet | GPT-4.1 Mini, GPT-4o |
| Sentiment Analysis | GPT-4o | GPT-4.1, Claude 3.5 Sonnet |
| Risk Assessment | o3-mini | o1-mini, GPT-4o |
| Digital Wellness | GPT-4o | GPT-4o Mini, GPT-4.1 Nano |
| General Chat | GPT-4o Mini | GPT-3.5 Turbo, GPT-4.1 Nano |

## API Endpoints

### AI Status Check
```http
GET /api/ai-status
```
Returns AI service status, rate limits, and model information.

### Enhanced Clinical Analysis
```http
POST /api/enhanced-clinical-analysis
Content-Type: application/json

{
  "transcript": "Session transcript text...",
  "patient_data": {
    "wellness_trend": "Improving",
    "digital_score": "Good",
    "engagement": "High"
  }
}
```

### Digital Wellness Analysis
```http
POST /api/submit-digital-detox
Content-Type: application/json

{
  "screen_time": 6.5,
  "academic_score": 85,
  "social_interactions": "high"
}
```

## Rate Limiting

CloseRouter implements the following rate limits:

- **Free Tier**: 100 requests per day
- **Hourly Limit**: 1000 requests per hour
- **Monthly Limit**: 5000 requests per month

The system automatically handles rate limiting with:
- Exponential backoff retry logic
- Rate limit header monitoring
- Graceful degradation to fallback responses

## Error Handling

### API Errors
- **401 Unauthorized**: Invalid API key
- **404 Not Found**: Model not available
- **429 Too Many Requests**: Rate limit exceeded
- **500 Server Error**: CloseRouter service issues

### Fallback Mechanisms
When AI services are unavailable, the system provides:
- Basic clinical note templates
- Pre-defined wellness recommendations
- Offline analysis capabilities
- User-friendly error messages

## Security

### API Key Management
- Store API keys in environment variables
- Never commit API keys to version control
- Use `.env` files for local development
- Implement proper key rotation

### Data Privacy
- All patient data is processed securely
- No sensitive information is logged
- HIPAA-compliant data handling
- Secure transmission to CloseRouter

## Monitoring

### Health Checks
The system provides comprehensive monitoring:

```python
# Check AI service status
status = ai_service.check_api_status()
print(f"Status: {status['status']}")
print(f"Rate Limits: {status['rate_limits']}")

# Get model information
info = ai_service.get_model_info()
print(f"Available Models: {info['available_models']}")
```

### Logging
All AI interactions are logged for:
- Performance monitoring
- Error tracking
- Usage analytics
- Compliance auditing

## Best Practices

### Model Selection
1. Use Claude 3.5 Sonnet for clinical documentation
2. Use GPT-4o for general analysis and insights
3. Use o3-mini for reasoning and risk assessment
4. Use GPT-4o Mini for fast responses

### Error Handling
1. Always implement fallback mechanisms
2. Monitor rate limits and adjust usage
3. Log errors for debugging
4. Provide user-friendly error messages

### Performance Optimization
1. Use appropriate model sizes for tasks
2. Implement caching for repeated requests
3. Batch similar requests when possible
4. Monitor response times and optimize

## Troubleshooting

### Common Issues

**API Key Issues**
```bash
# Check if API key is set
echo $CLOSEROUTER_API_KEY

# Test API connection
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.closerouter.com/v1/models
```

**Rate Limiting**
- Monitor rate limit headers
- Implement exponential backoff
- Use fallback responses during limits

**Model Availability**
- Check model status in CloseRouter dashboard
- Use fallback model chains
- Monitor model performance

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
export AI_DEBUG_MODE=true
```

## Integration Examples

### Clinical Note Generation
```python
from ai_service import ai_service

# Generate clinical note
note = ai_service.generate_clinical_note(
    transcript="Patient discussed anxiety symptoms...",
    patient_info={
        'wellness_trend': 'Improving',
        'digital_score': 'Good'
    }
)
```

### Enhanced Analysis
```python
# Generate comprehensive analysis
analysis = ai_service.generate_enhanced_clinical_analysis(
    transcript="Session transcript...",
    patient_data={
        'assessment_scores': {'gad7': 8, 'phq9': 6},
        'engagement_level': 'High'
    }
)
```

### Digital Wellness Analysis
```python
# Analyze digital wellness data
wellness = ai_service.analyze_digital_wellness(
    screen_time=6.5,
    academic_score=85,
    social_interactions='high'
)
```

## Support

For CloseRouter API support:
- Documentation: https://docs.closerouter.com
- API Status: https://status.closerouter.com
- Support: support@closerouter.com

For MindFull Horizon integration issues:
- Check application logs
- Verify environment configuration
- Test API connectivity
- Review rate limit usage

## Future Enhancements

### Planned Features
- Real-time streaming responses
- Multi-modal analysis (text, audio, video)
- Advanced reasoning capabilities
- Custom model fine-tuning
- Enhanced security features

### Model Updates
- Automatic model version updates
- Performance optimization
- New model integration
- Specialized mental health models

---

**Last Updated**: August 30, 2025
**Version**: 1.0.0
**Compatibility**: CloseRouter API v1
