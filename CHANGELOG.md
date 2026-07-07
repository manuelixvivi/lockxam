# Changelog

All notable changes to the EquiGrade platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-platform] - 2026-07-07

### Added
- **Clean Architecture & Repository Pattern**: Created `BaseRepository` implementing generic CRUD operations (create, update, delete, exist, count, paginate) under SQLALchemy 2.0.
- **DB-Backed Session Engine**: Added `user_sessions` model supporting device tracking (IP and User-Agent), idle timeouts (120 minutes), and revocation endpoints (`/sessions`, `/revoke-session/{id}`, `/logout-all`).
- **Refresh Token Rotation (RTR)**: Implemented secure token rotation on `/refresh` and built a replay attack protection system that auto-revokes the entire session upon detecting token reuse.
- **Login Rate Limiting**: Added `login_attempts` brute-force protection which locks user-IP combinations for 15 minutes after 5 consecutive failures.
- **Password Policy Enforcement**: Created password complexity validations requiring lowercase, uppercase, digits, symbols, and a minimum of 8 characters.
- **Developer Experience (DevEx) Configs**: Created central `pyproject.toml` configuration mapping Black, Ruff, Mypy, and Pytest-Cov.
- **Git Hooks**: Integrated `pre-commit` hook configurations locally for automatic code gate checks on commit.
- **Containerization**: Configured `Dockerfile` and `docker-compose.yml` for isolated FastAPI web servers and PostgreSQL 16 database services.
- **Faker Database Seeder**: Created `seed.py` utilizing the Faker package to generate schools, sessions, logs, and accounts automatically.
- **Continuous Integration (CI)**: Created `.github/workflows/ci.yml` defining automated GitHub Actions testing and code quality pipelines.
- **ADR & TDD Documentation**: Created Architecture Decision Records (`docs/adr/`) and a comprehensive Technical Design Document (`docs/TDD.md`).

### Changed
- **API Versioning**: Standardized all API routes under the `/api/v1` namespace (e.g., `/api/v1/auth/login`).
- **Paging Result Schema**: Refactored the generic pagination response to return a typed `PageResult` schema.

### Security
- **Dynamic JWT Signatures**: Integrated dynamic secret key selection via `kid` (Key ID) header fields.
- **Token Versioning**: Added token versioning checks (`ver: 1`) in dependencies to prevent token replay vulnerabilities across server versions.
