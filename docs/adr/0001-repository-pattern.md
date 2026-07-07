# ADR-001: Implementation of Repository Pattern

## Context
In standard FastAPI applications, database query logic (SQLAlchemy session calls) is often written directly inside route handler functions (API layer) or services. As the application grows, this approach leads to several problems:
1. **Coupling**: The API routers and service layers become tightly coupled to the database ORM (SQLAlchemy).
2. **Code Duplication**: Basic CRUD operations (e.g., query by ID, pagination, updates) are rewritten repeatedly across different endpoints.
3. **Harder Testing**: Testing the business logic requires active database connections, as queries are embedded directly in service functions without abstractions.

We need a pattern that decouples database operations, promotes reuse, and isolates ORM details from the core business logic.

## Decision
We implement the **Repository Pattern** with a generic base class.
1. All database operations will reside within a dedicated repository layer under `app/repositories/`.
2. A generic `BaseRepository[ModelType]` is created to implement common CRUD operations:
   - `get_by_id(db, obj_id)`
   - `get_all(db)`
   - `create(db, obj)`
   - `create_many(db, objs)`
   - `update(db, obj)`
   - `update_many(db, objs)`
   - `delete(db, obj)`
   - `soft_delete(db, obj)`
   - `exists(db, obj_id)`
   - `count(db, ...)`
   - `paginate(db, ...)`
3. Business services (`app/services/`) will only interact with repositories and will not invoke SQLAlchemy query expressions directly.

## Consequences
### Positive
* **DRY (Don't Repeat Yourself)**: Basic CRUD is inherited automatically by all entity repositories, reducing boilerplate by up to 90%.
* **Decoupled Business Logic**: Services do not know how queries are executed or which ORM is used.
* **Safer Transaction Boundaries**: The repository only performs stage operations (e.g. `db.add()`) while the service layer determines the transaction boundaries (`db.commit()` / `db.rollback()`), allowing atomic transactions across multiple repositories.

### Negative
* **Extra Layer**: Adds one extra file/layer of abstraction for every model. However, for simple models, this is mitigated by inheriting everything from `BaseRepository`.
* **Complexity in Joins**: Complex domain queries (multiple joins and aggregations) still require writing custom SQLAlchemy methods inside specific repositories.

## Status
**Accepted**

## Date
2026-07-07
