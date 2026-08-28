# Global Import Contract v1.0

This contract establishes the canonical validation and transaction standard for all bulk data imports within the EquiGrade platform.

---

## 1. Import Lifecycle

Every import operation must progress through the following sequential lifecycle:

```text
  [Upload XLSX]
        │
        ▼
   [Parse Rows] (Frontend reads spreadsheet into raw JSON rows)
        │
        ▼
[Frontend Preview] (Renders table preview for visual verification)
        │
        ▼
  [POST Payload] (Uploads the entire batch array in a single request)
        │
        ▼
  [Validate All] (Backend executes full semantic & integrity checks)
        │
        ├──────────────────────────┐
        ▼                          ▼
   [Errors Found]             [All Valid]
        │                          │
        ▼                          ▼
 [HTTP 422 Response]        [Begin Transaction] (Database persistence begins)
 (No Database write occurred)      │
                                   ├───────────────────────┐
                                   ▼                       ▼
                            [Write Failure]         [Write Success]
                                   │                       │
                                   ▼                       ▼
                            [Rollback All]            [Commit All]
                                   │                       │
                                   ▼                       ▼
                            [HTTP 400/500]            [HTTP 200 OK]
```

---

## 2. Validation Stages

Every batch import must pass through **six distinct validation layers** in the backend before database persistence:

1. **Structural Validation**: Ensure mandatory headers exist, column formats are valid, and rows are not empty.
2. **Semantic Validation**: Verify field limits, data types, and value patterns (e.g., NISN must be numeric and 10 digits).
3. **Reference Resolution**: Lookup and resolve relational foreign entities against the database.
4. **Tenant Validation**: Ensure all resolved references belong strictly to the active authenticated school ID.
5. **Authorization**: Verify the caller has the required role (e.g. `SCHOOL_ADMIN` for student bulk uploads).
6. **Business Invariant Validation**: Enforce unique database constraints and domain-specific rules (e.g., class capacity or teacher-subject competency).

---

## 3. Atomicity, Validation, and Persistence Boundaries

To ensure complete database integrity, validation and persistence must be strictly isolated:

### A. Validation Failure (Pre-Persistence)
* Validation checks are executed **before** opening a transaction or writing any data to the database.
* If any single row fails validation, processing stops immediately.
* **Database State**: No database write operations are performed.
* **Response**: Return a structured report (`ImportValidationResult`) in an `HTTP 422 Unprocessable Entity` response. No rollback is required since no changes were attempted.

### B. Persistence/Database Failure
* After all validations pass successfully, a database transaction is opened.
* **Database State**: The batch payload is written/flushed to the database.
* **Response**:
  - **Success**: The transaction is committed exactly once at the end, returning an `HTTP 200 OK` response.
  - **Write/Database Error**: If any database write fails (e.g., database constraint violation or connection loss), a `db.rollback()` is executed, rolling back all records in the batch. Returns an `HTTP 400` or `HTTP 500` error response.

---

## 4. Reference Resolution Rules

To prevent broken relational trees or orphaned records, reference lookups must be authoritative:
* **Academic Class Resolution**: A class reference must be resolved using:
  ```text
  school_id + academic_year_id + class.name
  ```
  Class lookup must never be resolved by name alone. The `academic_year_id` must be provided as context by the admin from the frontend UI selection.
* **No Implicit Creation**: Importers must **never** implicitly create missing master records (such as Class or Subject) or auto-register teacher subject competencies. If a reference does not exist, the row must be rejected.

---

## 5. Tenant Isolation & Security

* **Authoritative School ID**: The active school ID must be resolved strictly from the logged-in user's JWT token context on the backend (`current_user.get("school_id")`).
* **Cross-Tenant Prevention**: Any resolved relation or ID belonging to a different `school_id` must be rejected immediately with an HTTP 403/404. The Excel file must never supply or be trusted for the tenant `school_id`.

---

## 6. Duplicate Detection & Race Conditions

* **Excel File Deduplication**: Importers must check for duplicates (e.g., same NISN or Code) *within* the uploaded file.
* **Database Collision Check**: Importers must run pre-checks against existing records in the database.
* **Race Condition Protection**: We must not rely solely on SELECT-then-INSERT. The database must enforce strict `UNIQUE` constraints:
  - `auth_accounts(school_id, nisn)`
  - `classes(school_id, academic_year_id, name)`
  - `schools(npsn)`

  Any SQLAlchemy insertion must catch `IntegrityError`, perform a transaction rollback, and map the conflict back to a structured validation error response.

---

## 7. Global Error & Result Contract

All import endpoints must utilize the canonical Pydantic models defined in `app/schemas/common/import_validation.py`:

### A. Row Error Schema (`ImportRowError`)
```json
{
  "row": 14,
  "field": "class_name",
  "value": "X IPA 9",
  "code": "CLASS_NOT_FOUND",
  "message": "Kelas 'X IPA 9' tidak ditemukan pada Tahun Ajaran 2026/2027."
}
```
*Credentials, tokens, or system passwords must never be exposed in error messages.*

### B. Validation Result Schema (`ImportValidationResult`)
```json
{
  "success": false,
  "total_rows": 100,
  "valid_rows": 99,
  "errors": [
    {
      "row": 14,
      "field": "class_name",
      "value": "X IPA 9",
      "code": "CLASS_NOT_FOUND",
      "message": "Kelas 'X IPA 9' tidak ditemukan pada Tahun Ajaran 2026/2027."
    }
  ]
}
```

---

## 8. Division of Responsibility

### Frontend Responsibility
* Parse XLSX/CSV spreadsheet files into structured JSON array payloads.
* Provide an interactive table preview of the parsed rows.
* Render detailed validation error lists highlighting the specific row and field.
* Prevent submission if the frontend detects structural errors.

### Backend Responsibility
* Authenticate and authorize the request.
* Execute all business rules, reference resolution, and tenant checks.
* Orchestrate database transaction boundaries and enforce all-or-nothing rollback behavior.

---

## 9. Historical Data Protection

Bulk import operations must **never** be allowed to modify, update, or overwrite historical/immutable exam data:
* `ExamSnapshot`
* `AppliedRubric`
* `StudentAnswers`
* `FinalResult`

Attempting to import or bulk-insert data that targets these tables must be blocked at the service boundary.
