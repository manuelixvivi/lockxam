# Task Assignment: Milestone 3 - SuperAdmin AI Control Center Expansion (R4)

- Working Directory: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m3
- Workspace Root: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
- Authoritative Request File: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md
- Project Scope: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md
- Survey Handoff: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_explorer_survey_3\handoff.md

## Exclusive Write Ownership
You exclusively own and may edit:
- `app/schemas/ai/ai_management.py`
- `app/services/ai/ai_management_service.py`
- `frontend/src/api/superadminAi.ts`
- `frontend/src/views/superadmin/SuperAdminAiSystemView.tsx`
- `tests/test_superadmin_ai_config.py` (new test file)

DO NOT edit files owned by other milestones.

## Implementation Scope
1. **Backend Schemas**:
   - In `app/schemas/ai/ai_management.py`:
     - Extend `AiProviderConfigUpdateRequest` to accept:
       - `eval_model_name: Optional[str] = None`
       - `strict_transformer: Optional[bool] = None`
       - `embedding_model: Optional[str] = None`
       - `rag_top_k: Optional[int] = None`
       - `rag_similarity_threshold: Optional[float] = None`
       - `max_rag_tokens: Optional[int] = None`
     - Extend `AiProviderConfigResponse` to include `embedding_model: str`, `rag_top_k: int`, `rag_similarity_threshold: float`, `max_rag_tokens: int`.
     - Extend `AiSystemOverviewResponse` to include `ai_safety_status: Dict[str, Any]` with keys:
       - `hmac_callback_configured: bool`
       - `webhook_secret_set: bool`
       - `replay_protection_active: bool`

2. **Backend Service**:
   - In `app/services/ai/ai_management_service.py`:
     - In `update_config`, persist `eval_model_name`, `strict_transformer`, and RAG parameters when provided in payload.
     - In `get_overview`, compute `ai_safety_status`: check `AI_WEBHOOK_SECRET` presence, HMAC callback route health, and replay protection event logging status.

3. **Frontend API Types & Client**:
   - In `frontend/src/api/superadminAi.ts`:
     - Update `AiProviderConfigUpdatePayload` to include `eval_model_name`, `strict_transformer`, `embedding_model`, `rag_top_k`, `rag_similarity_threshold`, `max_rag_tokens`.
     - Update `AiProviderConfig` and `AiSystemOverview` interfaces accordingly.

4. **SuperAdmin AI System View**:
   - In `frontend/src/views/superadmin/SuperAdminAiSystemView.tsx`:
     - In Configuration tab, add form state and UI inputs for `eval_model_name` (Evaluation Model).
     - Add toggle switch for `strict_transformer` (Strict Transformer Enforcement).
     - Add RAG Tuning controls: Embedding Model input, Top-K slider/input (1–10), Similarity Threshold slider (0.50–0.95), and Context Token Limit input (512–4096).
     - In Overview & System Health tabs, render AI Safety Status indicators (HMAC Callback Health, Webhook Secret Verification, Replay Protection Status).

5. **Mandatory Integrity Warning**:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Verification
- Run backend tests: `.venv\Scripts\pytest.exe tests/test_superadmin_ai_config.py -v`
- Run frontend build: `npm run build` in `frontend/` (0 errors)
- Document all changes and verification output in `C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m3\handoff.md`.

## 2026-09-11T02:37:18Z
You are teamwork_preview_worker_m3.
Your working directory is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m3
The workspace root is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam
The authoritative request file is: C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md

You MUST read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\ORIGINAL_REQUEST.md before starting work.
Also read C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\PROJECT.md and C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m3\DISPATCH.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your mission:
Implement Milestone 3 (SuperAdmin AI Control Center Expansion R4):
- In app/schemas/ai/ai_management.py: Extend AiProviderConfigUpdateRequest with eval_model_name, strict_transformer, embedding_model, rag_top_k, rag_similarity_threshold, max_rag_tokens; extend AiProviderConfigResponse with RAG parameters; extend AiSystemOverviewResponse with ai_safety_status (hmac_callback_configured, webhook_secret_set, replay_protection_active).
- In app/services/ai/ai_management_service.py: Update update_config to persist eval_model_name, strict_transformer, and RAG tuning parameters; update get_overview to return ai_safety_status.
- In frontend/src/api/superadminAi.ts: Extend interfaces for payloads and responses.
- In frontend/src/views/superadmin/SuperAdminAiSystemView.tsx: Add UI controls for Evaluation Model (eval_model_name), Strict Transformer toggle, RAG tuning sliders/inputs, and AI Safety status badges.
- Write tests in tests/test_superadmin_ai_config.py and run: .venv\Scripts\pytest.exe tests/test_superadmin_ai_config.py -v.
- Run npm run build in frontend/ to confirm 0 errors.
- Write handoff report to C:\Users\irul2\Downloads\Equigrade_x_Lockxam\.agents\teamwork_preview_worker_m3\handoff.md and notify orchestrator via send_message.

