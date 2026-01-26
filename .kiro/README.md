# Kiro Configuration for Mindful Horizon

This directory contains Kiro-specific configuration files that enhance the development experience for the Mindful Horizon mental health platform.

## Directory Structure

```
.kiro/
├── steering/           # Development guidance and standards
│   ├── project-overview.md      # Project architecture and overview
│   ├── development-standards.md # Code quality and security standards
│   ├── testing-guidelines.md    # Testing best practices
│   └── deployment-guide.md      # Production deployment guide
├── hooks/             # Automated development workflows
│   ├── lint-on-save.json       # Python linting on file save
│   ├── template-validation.json # HTML template validation
│   ├── security-review.json    # Security review for routes
│   ├── ai-integration-check.json # AI service validation
│   └── test-on-commit.json     # Run tests before commits
├── settings/          # Kiro configuration
│   └── mcp.json      # MCP server configuration
└── README.md         # This file
```

## Steering Files

### Always Included
- `project-overview.md`: Provides context about the Mindful Horizon platform
- `development-standards.md`: Enforces code quality, security, and HIPAA compliance

### Conditionally Included
- `testing-guidelines.md`: Activated when working with test files
- `deployment-guide.md`: Manual inclusion for deployment tasks

## Hooks

The project includes several automated hooks that trigger during development:

1. **Lint on Save**: Automatically checks Python files for PEP 8 compliance
2. **Template Validation**: Reviews HTML templates for accessibility and security
3. **Security Review**: Performs security audits on route modifications
4. **AI Integration Check**: Validates AI service changes for privacy compliance
5. **Test on Commit**: Runs test suite before commits

## MCP Servers

Configured MCP servers provide additional development tools:
- **Python Linting**: Automated code quality checks
- **Security Scanner**: Vulnerability and dependency scanning

## Usage

These configurations are automatically applied when working with Kiro. The steering files provide context-aware guidance, while hooks automate quality checks and security reviews throughout the development process.

For healthcare applications like Mindful Horizon, these configurations ensure HIPAA compliance, security best practices, and maintainable code quality.