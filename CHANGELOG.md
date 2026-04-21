# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-04-21

### Added
- Initial release of Workflow Automation Platform
- FastAPI backend with async SQLAlchemy ORM
- PostgreSQL 16 database support
- Redis 7 caching and queue system
- Celery workers for async task processing
- Web UI with HTMX and Tailwind CSS
- JWT authentication with refresh tokens
- API Keys for service integration
- RBAC with 4 roles and 24 granular permissions
- Workflow engine with 4 trigger types (webhook, scheduled, manual, file_upload)
- 8 action types (HTTP, Email, Database, Transform, Export CSV/PDF, Notify)
- Slack, Email SMTP, and Discord integrations
- Real-time execution monitoring with timeline view
- Audit logging for all actions
- Redis caching with TTL and decorators
- Rate limiting (100 req/min per client)
- 53+ unit tests with pytest
- Complete documentation (API Guide, Architecture, Development, Installation, Examples)
- 5 built-in workflow templates
- Workflow versioning with diff
- Dashboard with analytics and health score
- Export functionality (CSV, PDF)
- Bulk operations support

### Security
- JWT token-based authentication
- API Key authentication with scopes
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Webhook HMAC signature validation

## [0.9.0] - 2026-04-20

### Added
- Core workflow engine implementation
- Basic FastAPI structure
- Database models and migrations
- Initial Web UI with HTMX

### Fixed
- Various bug fixes and improvements

---

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- MAJOR.MINOR.PATCH
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.
