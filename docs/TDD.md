# EquiGrade Technical Design Document (TDD)

## 1. System Overview
EquiGrade is a production-grade Educational Platform designed to facilitate school management, exam scheduling, exam delivery, and automated essay evaluations using Artificial Intelligence (AI) and Retrieval-Augmented Generation (RAG).

This document serves as the primary technical specification for EquiGrade's core infrastructure, security architecture, and developer pipeline.

---

## 2. Technology Stack
* **Language**: Python 3.12+
* **Framework**: FastAPI (Asynchronous Web Framework)
* **Database ORM**: SQLAlchemy 2.0 (Transactional DB connection & mapping)
* **Migrations**: Alembic
* **Database**: PostgreSQL 16
* **Task Queue**: Celery (for asynchronous heavy workloads like AI Evaluation)
* **Caching & Broker**: Redis
* **Linting & Formatting**: Black, Ruff, Mypy
* **Testing**: Pytest, Pytest-Cov, Faker

---

## 3. Core Directory Structure
```text
app/
├── api/                  # API Layer (routers & versioned endpoints)
│   └── v1/               # Version 1 routers (auth, health, etc.)
├── core/                 # Shared configs, database connection, dependencies
├── exceptions/           # Global Exception classes & handlers
├── logging/              # Structured logger setup
├── middleware/           # HTTP Request interceptors (latency, Request ID)
├── models/               # SQLAlchemy ORM models
├── repositories/         # Database query wrappers (Repository Pattern)
├── schemas/              # Pydantic data serialization & validation schemas
├── services/             # Business Logic & transaction orchestrations
└── utils/                # Helper tools (date formatting, uuid helpers)
docs/
├── adr/                  # Architecture Decision Records
└── TDD.md                # Technical Design Document
tests/                    # Test cases (conftest, unit, and integration tests)
```

---

## 4. Database Structure
EquiGrade uses PostgreSQL. The Entity-Relationship Diagram (ERD) below details the tables defined in the Security Foundation:

```mermaid
erDiagram
    SCHOOL_LEVELS {
        int id PK
        string name
        string code UK
        string description
    }

    LICENSE_TYPES {
        int id PK
        string code UK
        string name
        int duration_days
        int max_users
        boolean is_active
    }

    SCHOOLS {
        int id PK
        uuid public_id UK
        string npsn UK
        string name
        int school_level_id FK
        string status
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }

    AUTH_ACCOUNTS {
        int id PK
        uuid public_id
        int school_id FK
        string username
        string password_hash
        string role
        boolean is_active
        datetime last_login
        datetime created_at
        datetime updated_at
    }

    USER_SESSIONS {
        uuid id PK
        int auth_account_id FK
        uuid access_token_jti
        uuid refresh_token_jti
        string ip_address
        string user_agent
        datetime last_activity_at
        datetime expires_at
        datetime created_at
        boolean revoked
        string revoked_reason
        datetime revoked_at
    }

    ACTIVITY_LOGS {
        int id PK
        int auth_account_id FK
        int school_id FK
        uuid session_id FK
        string action_type
        string action_name
        string endpoint
        string method
        string ip_address
        string user_agent
        jsonb meta_data
        datetime created_at
    }

    LOGIN_ATTEMPTS {
        int id PK
        string ip_address
        string username
        int attempts
        datetime last_attempt_at
        datetime blocked_until
    }

    SCHOOL_LICENSES {
        int id PK
        uuid public_id UK
        int school_id FK
        int license_type_id FK
        int activation_key_id FK "nullable, UK"
        datetime start_date
        datetime end_date
        int max_users
        string status
        datetime created_at
        datetime updated_at
    }

    ACTIVATION_KEYS {
        int id PK
        uuid public_id UK
        string key UK "secure random hash"
        int license_type_id FK
        int school_id FK "target school"
        int generated_by_id FK "SuperAdmin"
        datetime generated_at
        int used_by_id FK "nullable, School Admin"
        datetime used_at "nullable"
        int cancelled_by_id FK "nullable, SuperAdmin"
        datetime cancelled_at "nullable"
        datetime valid_until
        string status
        datetime created_at
        datetime updated_at
    }

    RENEWAL_REQUESTS {
        int id PK
        uuid public_id UK
        string request_number UK
        int school_id FK
        int requested_by_id FK "School Admin"
        int license_type_id FK
        string status
        string payment_proof_url "nullable"
        text superadmin_notes "nullable"
        int processed_by_id FK "nullable, SuperAdmin"
        datetime processed_at "nullable"
        datetime created_at
        datetime updated_at
    }

    SCHOOLS ||--o{ AUTH_ACCOUNTS : "contains"
    AUTH_ACCOUNTS ||--o{ USER_SESSIONS : "owns"
    AUTH_ACCOUNTS ||--o{ ACTIVITY_LOGS : "performs"
    USER_SESSIONS ||--o{ ACTIVITY_LOGS : "associated_with"
    SCHOOLS ||--o{ SCHOOL_LICENSES : "has"
    LICENSE_TYPES ||--o{ SCHOOL_LICENSES : "defines"
    LICENSE_TYPES ||--o{ ACTIVATION_KEYS : "defines"
    SCHOOLS ||--o{ ACTIVATION_KEYS : "targets"
    ACTIVATION_KEYS ||--o| SCHOOL_LICENSES : "activates"
    SCHOOLS ||--o{ RENEWAL_REQUESTS : "submits"
    LICENSE_TYPES ||--o{ RENEWAL_REQUESTS : "requests"
```

---

## 5. Architectural Pattern: Clean Architecture & Repository Pattern
EquiGrade separates concerns using a layered architecture:

```mermaid
graph TD
    API[API Layer: app/api/] -->|HTTP Requests| Dep[Dependency Layer: app/core/dependencies.py & rbac.py]
    Dep -->|Role & Auth Validation| Service[Service Layer: app/services/]
    Service -->|Atomically Orchestrates| Repo[Repository Layer: app/repositories/]
    Repo -->|Queries & Hydrates| Model[Model Layer: app/models/]
    Repo -->|ORM Database Session| DB[(PostgreSQL Database)]
```

### 5.1 Repository Pattern Rules
* **BaseRepository**: A generic class `BaseRepository[ModelType]` provides standard database operations (create, read, update, delete, exists, soft_delete, count, pagination) using SQLAlchemy 2.0 select statement scalars.
* **No Inline Commits**: Repositories are strictly prohibited from calling `db.commit()` or `db.rollback()`. They stage database state using `db.add()`, `db.flush()`, or `db.delete()`.
* **Atomic Transactions**: The Service layer is responsible for invoking `db.commit()` inside a `try...except` block, rolling back in case of exceptions. This allows multiple repositories to execute operations under a single ACID transaction.

### 5.2 Error Handling & Exception Framework
EquiGrade uses a centralized exception handling strategy to decouple services from HTTP-specific classes:
1. **Business Exception Raising**: Services raise subclasses of `AppException` (e.g. `BusinessException`, `AuthenticationException`, `PermissionException`, `LicenseExpiredException`) located in `app/exceptions/base.py`.
2. **Global Exception Mapping**: A central registry in `app/exceptions/handlers.py` catches `AppException` and maps them to appropriate HTTP status codes (e.g., 401, 403, 422).
3. **Structured JSON Response**: The handler returns a clean JSON response (e.g. `{"detail": "..."}` or custom structured payload like `{"error": {"code": "...", "message": "..."}}`), ensuring frontend clients receive predictable response bodies.

### 5.3 Multi-tenancy & Tenant Isolation
EquiGrade implements a shared-database, shared-schema multi-tenancy model:
1. **Tenant Identifier**: The `schools` table acts as the primary tenant. Models that belong to a specific school (e.g. `AuthAccount`, `SchoolLicense`, `RenewalRequest`, and future academic entities) contain a foreign key `school_id`.
2. **Session Context Isolation**: Upon successful authentication, the user's `school_id` is embedded in the JWT claim.
3. **Automatic Filtering**: Repositories must enforce filters on `school_id` for all school-level queries to prevent cross-tenant data leaks.

---

## 6. Authentication & Session Flow
EquiGrade enforces stateless JWT delivery paired with stateful database verification.

### 6.1 Authentication (Login) Sequence
```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as API (/api/v1/auth/login)
    participant Service as AuthService
    participant DB as PostgreSQL
 
    Client->>API: POST (username, password)
    API->>Service: authenticate(username, password)
    Service->>DB: Check rate limiting & fetch user
    DB-->>Service: Return account
    Service->>Service: Verify hash password
    Service->>DB: Log session & reset rate limits
    Service->>Service: Sign JWT (access_token, refresh_token)
    Service->>DB: Log login activity log
    Service->>DB: db.commit()
    Service-->>API: Return tokens & profile
    API-->>Client: HTTP 200 (access_token, refresh_token)
```

### 6.2 Refresh Token Rotation (RTR) & Replay Attack Protection
To prevent refresh token theft, every token refresh triggers rotation. If an old refresh token is reused, the entire session is instantly terminated:

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as API (/api/v1/auth/refresh)
    participant Service as AuthService
    participant DB as PostgreSQL
 
    Client->>API: POST (refresh_token)
    API->>Service: refresh(refresh_token)
    Service->>Service: Verify signature & extract JTI
    Service->>DB: Fetch session by JTI
    alt Refresh token is invalid/revoked/expired
        Service-->>API: Raise AuthenticationException
        API-->>Client: HTTP 401 Unauthorized
    else Refresh JTI is NOT active (REUSE DETECTED)
        Service->>DB: Revoke entire session (revoked_reason = 'REUSE_DETECTED')
        Service->>DB: db.commit()
        Service-->>API: Raise AuthenticationException
        API-->>Client: HTTP 401 Unauthorized (Force log out all clients)
    else Refresh JTI matches active JTI
        Service->>Service: Generate new access & refresh JTI
        Service->>DB: Update active JTIs in session database
        Service->>DB: db.commit()
        Service-->>API: Return new access/refresh token pair
        API-->>Client: HTTP 200 (new tokens)
    end
```

---

## 7. Security Design (Non-functional Security Requirements)
1. **Password Complexity Policy**: Minimum 8 characters, requiring at least one lowercase letter, one uppercase letter, one digit, and one special symbol. Checked via regex before hashing using `bcrypt`.
2. **Brute Force Lockout**: 5 failed login attempts for a specific `(ip_address, username)` combination locks the account from further attempts for 15 minutes.
3. **Session Idle Timeout**: Sessions expire after 120 minutes of inactivity. The `get_current_user` dependency updates `last_activity_at` and revokes the session if the elapsed time exceeds the idle threshold.
4. **JWT Key Rotation**: Secret keys are selected dynamically using Key ID (`kid`) in the JWT header, allowing secrets to be rotated in production without invalidating active sessions.
5. **Token Versioning**: Tokens include a version claim (`"ver": 1`). If the token version does not match the active server token version, the request is rejected.

---

## 8. Development Pipeline & DevEx (Phase 0.5)
1. **Quality Gates**: Ruff (linting), Black (formatting), and Mypy (strict type-checking) are configured in `pyproject.toml`.
2. **Git Pre-commit hooks**: Enforces formatting, linting, and type checking locally before every commit.
3. **CI Pipeline (GitHub Actions)**: Builds a PostgreSQL service container, installs dependencies, checks syntax (Black & Ruff), runs static analysis (Mypy), and executes tests.
4. **Pytest Coverage**: Measures test suite coverage. Current coverage stands at **88%** with all 35 unit & integration tests passing.

---

## 9. Deployment & Runtime Architecture
The following flowchart illustrates the physical and runtime deployment architecture for EquiGrade, decoupling core API resources from Celery tasks and external AI/Vector dependencies:

```mermaid
flowchart TD
    Client[Client / Web Browser] -->|HTTPS| Proxy[Reverse Proxy: Nginx / Cloudflare]
    Proxy -->|WSGI / ASGI| App[FastAPI Application: Uvicorn]
    App -->|Read / Write SQL| DB[(Primary DB: PostgreSQL 16)]
    App -->|Cache / Broker| Redis[(In-Memory: Redis)]
    Redis -->|Task Queue| Worker[Celery Asynchronous Workers]
    Worker -->|Read Context| DB
    Worker -->|Fetch Reference Vectors| VecDB[(Vector Database: pgvector / Qdrant)]
    Worker -->|Generate Vector Embeddings| Embed[Embedding API / Service]
    Worker -->|Prompt Orchestration| LLM[LLM Engine: Gemini / OpenAI API]
```

---

## 10. AI Evaluation & RAG Pipeline (Future)
For automated essay evaluation, the system decouples heavy computation into an asynchronous AI Pipeline:

```mermaid
flowchart TD
    Ans[Student submits Answer] -->|Trigger Exam End| API[FastAPI endpoint]
    API -->|Queue job| Celery[Celery Task Broker]
    Celery -->|Pulls from Queue| Worker[Celery Worker Process]
    Worker -->|Fetch Rubric & Answer Key| DB[(PostgreSQL)]
    Worker -->|Generate Query Embeddings| Embed[Embedding API]
    Embed -->|Query Context| VectorDB[(Vector DB: RAG Reference)]
    VectorDB -->|Return Reference context| Worker
    Worker -->|Orchestrate Prompt| LLM[LLM Engine: Gemini / OpenAI]
    LLM -->|Return score & feedback| Worker
    Worker -->|Save scores| DB
    DB -->|Notify| Teacher[Teacher Review Interface]
```

---

## 11. LockExam Integration
To support secure high-stakes examinations, EquiGrade integrates with the **LockExam** subsystem:
* **Secure Exam Mode**: Restricts browser navigation, blocks copy-paste commands, prevents tab switching, and detects unauthorized shortcut keys.
* **Heartbeat Protocol**: Continuous ping-pong connection between client-side exam shell and server. Session automatically flags suspension if three consecutive heartbeats are missed.
* **Device Binding**: Locks an active exam session to a unique hardware fingerprint. Prevents students from resuming a quiz on a different device without supervisor authentication.
* **Focus Monitoring**: Logs window-blur events (e.g. when browser loses focus) and records infractions directly in the database.
* **Offline Detection & Sync**: Temporarily caches responses in local storage during network interruptions and synchronizes updates with the server upon reconnection.

---

## 12. License & Subscription Domain
The License Domain manages the lifecycle of school subscriptions, generation of cryptographically secure activation keys (which are hashed using SHA-256 in the database to prevent plain-text exposure), and tracking of renewal requests.

### 12.1 Key Generation Flow
Activation keys are generated exclusively by platform administrators:

```mermaid
sequenceDiagram
    autonumber
    actor SA as SuperAdmin
    participant API as License API (/keys)
    participant Service as LicenseService
    participant DB as PostgreSQL
    
    SA->>API: POST (license_type_id, school_id)
    API->>Service: generate_activation_key(license_type_id, school_id, admin_id)
    Service->>Service: Validate school & license type
    Service->>Service: Generate secure random plaintext key
    Service->>Service: Hash plaintext key (SHA-256)
    Service->>DB: Insert ActivationKey (status = 'GENERATED')
    Service->>DB: Log activity (GENERATE_ACTIVATION_KEY)
    Service->>DB: db.commit()
    Service-->>API: Return key record & plaintext key
    API-->>SA: HTTP 200 OK (Displays key once)
```

### 12.2 License Activation Sequence Flow
When an Activation Key is submitted by a School Admin, the backend processes the request through the following sequence of steps in a single database transaction:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as School Admin
    participant API as License API (/activate)
    participant Service as LicenseService
    participant DB as PostgreSQL
    
    Admin->>API: POST (key_plain)
    API->>Service: activate_license(plain_key, school_id, user_id)
    Service->>Service: Hash plain_key (SHA-256)
    Service->>DB: Fetch ActivationKey by hash & lock row
    DB-->>Service: Return ActivationKey record
    Service->>Service: Verify key validity, expiry & school target ownership
    
    alt If active license exists
        Service->>DB: Fetch active license end_date
        DB-->>Service: Return end_date
        Service->>Service: Calculate new.start_date = current_active.end_date
        Service->>DB: Insert new SchoolLicense (status = 'PENDING')
    else If no active license exists
        Service->>Service: Calculate new.start_date = now()
        Service->>DB: Insert new SchoolLicense (status = 'ACTIVE')
        Service->>DB: Update School status = 'ACTIVE'
    end
    
    Service->>DB: Update ActivationKey (status = 'USED', used_by, used_at)
    Service->>DB: Log activity (ACTIVATE_LICENSE)
    Service->>DB: db.commit()
    Service-->>API: Return generated SchoolLicense
    API-->>Admin: HTTP 200 OK (License details)
```

---

## 13. Domain & Module Dependency Tree
To guide subsequent sprints, the educational modules must be built according to the following dependency hierarchy:

```mermaid
graph TD
    Security[1. Security Domain] --> School[2. School Domain]
    School --> License[3. License Domain]
    License --> Academic[4. Academic Domain]
    Academic --> Teacher[5. Teacher Domain]
    Teacher --> Class[6. Classroom Domain]
    Class --> Student[7. Student Domain]
    Student --> Exam[8. Exam Domain]
    Exam --> AI[9. AI Domain]
```

---

## 14. Non-Functional Requirements (NFR) & Operational Constraints
The target service level indicators (SLIs) and capacity limits are specified below:

### 14.1 Service Level Indicators (SLIs)
| Requirement | Target Metric | Verification Method |
| :--- | :--- | :--- |
| **Availability** | 99.5% uptime monthly | Health probe endpoint `/api/v1/health` |
| **Login Response** | < 300 ms (latency under normal load) | Middleware latency logging |
| **Refresh Token Response** | < 200 ms | Middleware latency logging |
| **AI Evaluation Processing** | Asynchronous execution (No blocking) | Celery task scheduler |
| **Max Concurrent Users** | 500 active concurrent connections | Locust load testing suite |
| **Security Standards** | OWASP Top 10 Compliance | Static analysis and manual audits |
| **Search Response** | < 2.0 seconds under peak load | Middleware/API performance logs |

### 14.2 Operational & Capacity Constraints
* **Maximum Students**: 5,000 students per school tenant.
* **Maximum Teachers**: 500 teachers per school tenant.
* **Maximum XLSX Rows**: 10,000 rows per bulk import file.
* **Import Timeout**: 5 minutes (300 seconds) execution ceiling.
* **Concurrent Administrators**: Maximum 5 concurrent active admin sessions per school.

---

## 15. Appendices

### Appendix A: Naming Conventions
To maintain strict project style coherence, the following conventions are enforced:

| Object Type | Case Convention | Example |
| :--- | :--- | :--- |
| **PostgreSQL Table** | `snake_case` | `user_sessions`, `login_attempts` |
| **PostgreSQL Column** | `snake_case` | `auth_account_id`, `is_active` |
| **Python Class** | `PascalCase` | `AuthService`, `BaseRepository` |
| **Variables & Functions** | `snake_case` | `session_id`, `get_current_user` |
| **Constants** | `UPPER_CASE` | `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM` |

### Appendix B: Architecture Rules & Clean Code Summary
Every developer committing to EquiGrade must adhere to these guidelines:
1. **Separation of Database Queries**: API Routers are prohibited from invoking SQLAlchemy sessions. All data retrieval and storage operations must go through repositories.
2. **Transaction Boundaries**: Repositories are prohibited from committing changes (`db.commit()` or `db.rollback()`). All writes must be staged (`db.add()`) and committed atomically inside services.
3. **HTTP Decoupling**: Service classes must not import `fastapi.HTTPException` or reference HTTP details. Services raise business exceptions (defined under `app/exceptions/`), which are translated by global handlers.
4. **Action Audits**: All state-modifying actions (insert, update, delete) must record an entry in the `activity_logs` table.
5. **Testing Enforcement**: Every new router endpoint, repository query, or business logic flow must have corresponding unit or integration test cases written under `tests/`.

### Appendix C: Frozen Business Rules (School Operations & Admin Domain v3.0 Baseline)
These rules are baseline-frozen and must be enforced by all services in the School Operations and Admin Domain:
1. **Class Membership History**: Student class changes (mutations) must never update the `class_id` of an existing record directly. A historical ledger (`ClassMembership` relation) must be maintained containing `id, student_id, class_id, start_date, end_date, status (ACTIVE/ENDED)`. During a student mutation, the existing record is closed (`status = 'ENDED'`, `end_date = now()`) and a new record is created (`status = 'ACTIVE'`, `start_date = now()`).
2. **Subject Deactivation Constraint**: Once a Subject is associated with any Classrooms or Assessment sessions, it is protected from hard deletion. It can only be soft-deactivated (`is_active = False`).
3. **Teacher Deactivation Safety check**: Deactivating a Teacher (`is_active = False`) is prohibited if they have active assignments. The system must validate and warn if the teacher is assigned to any `Upcoming Exam`, active `Teaching Assignment`, or `Proctor Assignment`.
4. **Student Deactivation Block**: A Student cannot be deactivated or deleted if they are currently linked to a running `Exam Session`.
5. **Schedule Conflict Validation**: Schedule conflict checks must prevent overlapping bookings for the `Classroom`, the `Teacher` (both as teacher-in-charge or proctor), and the `Student` (ensuring a student is never scheduled for two concurrent exams).
6. **Classroom Edit Lock**: When an `Exam Session` is in the `Running` state, its associated `Classroom` configuration (assigned Teacher, Subject, and Student roster) is locked as Read-Only to preserve the exam snapshot.
7. **Audit Log Delta Tracking**: The `activity_logs` must record a full audit trail capturing `Who` (user), `When` (timestamp), `What` (action), and the state delta (`Before` and `After` JSON representation of affected records) for all mutating operations.
8. **XLSX Import Modes**: Administrative bulk data imports via XLSX must support three modes: `Insert Only` (rejects duplicates), `Update Existing` (updates existing records, ignores new), and `Upsert` (inserts new, updates existing).
