# ADR-003: DB-Backed Session Management Engine

## Context
Stateless JWT authentication has a major drawback: it is difficult to instantly invalidate (revoke) tokens before they expire. If a user logs out, resets their password, or an administrator locks an account, the active access tokens remain valid until their expiration time.

To resolve this, we need a session management engine that provides the flexibility of stateful sessions (instant revocation, tracking active devices) without completely sacrificing the scalability of JWT.

## Decision
We implement a **DB-backed Session Management Engine** using the `user_sessions` table.
1. **Session Lifecycles**:
   - **Login**: Generates a new session in `user_sessions` with unique `session_id`, `access_token_jti`, and `refresh_token_jti`.
   - **Session Verification**: In `get_current_user` dependency, we query `user_sessions` using the token's `sid` (session ID).
   - **Session Rejection**: The token is rejected if the database record is marked `revoked = True`, `expires_at` has passed, or if the time since `last_activity_at` exceeds the configured **Session Idle Timeout** (default: 120 minutes).
   - **Logout**: Instantly marks the specific session as `revoked = True` with `revoked_reason = 'LOGOUT'`.
2. **Device & Multi-session Tracking**:
   - User sessions capture `ip_address` and `user_agent` (device type).
   - The `/sessions` endpoint returns all active devices, allowing users to view where they are logged in.
   - Users can revoke a specific device session (`/revoke-session/{id}`) or logout from all devices (`/logout-all`).

## Consequences
### Positive
* **Instant Revocation**: Compromised or logged-out tokens are denied access immediately on the next API request.
* **Idle Timeout Enforcement**: Protects users who leave their browser open by expiring the DB session after inactivity, regardless of JWT expiration.
* **Device Control**: Provides professional-grade security features where users can monitor and terminate unauthorized logins.

### Negative
* **Database Query Overhead**: Every authenticated API request triggers a select query on `user_sessions` to check revocation status.
* *Mitigation*: The `user_sessions` table is indexed on `id` (primary key lookup is extremely fast), and we update `last_activity_at` using a throttle (e.g. only update if the last activity was more than 1 minute ago) or keep it lightweight.

## Status
**Accepted**

## Date
2026-07-07
