# Security policy

MindFull Horizon handles sensitive mental-health data. Please report vulnerabilities privately.

- Use GitHub's "Report a vulnerability" (Security tab -> Advisories) on https://github.com/ayushjaiswal21/MindFullHorizon . Do not open a public issue with exploit details.
- Include the affected URL or file, steps to reproduce and impact. Never include real user data.
- Known open issues are tracked in [docs/STATUS.md](docs/STATUS.md); please check it before reporting.

Operational rules for maintainers: never commit `.env` or database files, rotate any API key that was ever shared, and keep helpline numbers in one config file with a "last verified" date.
