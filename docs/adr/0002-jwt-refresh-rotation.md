# ADR-002: JWT Refresh Token Rotation

## Context
JSON Web Tokens (JWTs) are commonly used for stateless authentication. To maintain security, access tokens are short-lived (e.g. 60 minutes). When they expire, users utilize a long-lived refresh token (e.g. 30 days) to request a new access token without re-entering credentials.

However, if an attacker steals a long-lived refresh token, they can maintain persistent access to the victim's account. Standard token expiration is insufficient for this threat. We need a mechanism to:
1. Limit the window of opportunity for stolen refresh tokens.
2. Detect if a refresh token has been leaked and reused.
3. Automatically invalidate compromised sessions.

## Decision
We implement **Refresh Token Rotation (RTR)** backed by database session validation.
1. Every time a client requests a new access token using a refresh token:
   - The server validates the token signature, version, and expiration.
   - The server checks if the refresh token's unique identifier (JTI) matches the active JTI recorded in `user_sessions`.
   - If valid, the server generates a **new** access token and a **new** refresh token (with a new JTI).
   - The server updates `user_sessions` with the new JTIs, effectively invalidating the old refresh token.
2. **Replay Attack Detection**: If a client attempts to refresh using an *old* refresh token (whose JTI is no longer active):
   - The server detects this as a replay attack (token reuse).
   - The server immediately revokes the **entire session** (`is_revoked = True`, `revoked_reason = 'REFRESH_TOKEN_REUSE_DETECTED'`).
   - The server rejects the refresh request, forcing all clients on that session to re-authenticate.

## Consequences
### Positive
* **High Security**: Minimizes the lifetime of any stolen refresh token to its first use.
* **Proactive Breach Mitigation**: If an attacker steals a token and refreshes it, the victim's client will eventually try to refresh with the same token, triggering instant revocation of the entire session and locking out the attacker.
* **Strict Session Control**: Protects stateless JWT credentials using stateful DB-backed guards.

### Negative
* **Database Queries on Refresh**: Validating JTIs requires a database lookup, slightly diminishing the "stateless" benefit of JWTs. This is an acceptable trade-off for security and is mitigated by indexing the `user_sessions` table.

## Status
**Accepted**

## Date
2026-07-07
