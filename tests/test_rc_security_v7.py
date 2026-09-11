import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette import status

from app.core.dependencies import get_current_user
from app.core.security.keys import (
    QR_SIGNING_SECRET,
    get_ai_webhook_secret,
    get_qr_signing_secret,
)
from app.models.exam.enums import ExamAttemptStatus
from app.models.exam.exam_attempt import ExamAttempt
from app.models.exam.exam_checkin_pin import ExamCheckinPin
from app.models.teacher.proctor_event import ProctorAuditEvent
from main import app
from tests.test_exam_security_boundaries import _create_school_hierarchy


# =============================================================================
# 1. AI WEBHOOK FAIL-CLOSED & HMAC VALIDATION TESTS
# =============================================================================

def test_ai_webhook_callback_fail_closed_when_secret_unset(client, monkeypatch):
    """Memastikan /ai/callback menolak request dengan HTTP 503 jika AI_WEBHOOK_SECRET tidak diset."""
    monkeypatch.delenv("AI_WEBHOOK_SECRET", raising=False)

    payload = json.dumps({
        "attempt_id": 123,
        "question_id": 456,
        "score": 85.0,
        "feedback": "Jawaban lengkap",
        "grading_status": "COMPLETED",
        "grading_version": 1,
    })

    res = client.post(
        "/api/v1/exam/ai/callback",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-AI-Signature": "sha256=abcdef1234567890",
        },
    )
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "AI webhook is not configured." in res.json()["detail"]


def test_ai_webhook_callback_rejects_missing_or_invalid_signature(client, monkeypatch):
    """Memastikan /ai/callback menolak request jika header signature hilang atau HMAC tidak cocok."""
    test_secret = "test-ai-webhook-secret-key-super-safe-123"
    monkeypatch.setenv("AI_WEBHOOK_SECRET", test_secret)

    payload = json.dumps({
        "attempt_id": 123,
        "question_id": 456,
        "score": 85.0,
        "feedback": "Jawaban lengkap",
        "grading_status": "COMPLETED",
        "grading_version": 1,
    })

    # 1. Missing signature header
    res_no_sig = client.post(
        "/api/v1/exam/ai/callback",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    assert res_no_sig.status_code == status.HTTP_403_FORBIDDEN
    assert "Missing X-AI-Signature" in res_no_sig.json()["detail"]

    # 2. Invalid HMAC signature
    res_bad_sig = client.post(
        "/api/v1/exam/ai/callback",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-AI-Signature": "sha256=invalidhashvalue000000000000000000000000000000000000000000000000",
        },
    )
    assert res_bad_sig.status_code == status.HTTP_403_FORBIDDEN
    assert "Invalid HMAC signature" in res_bad_sig.json()["detail"]


def test_ai_webhook_production_startup_fail_fast(monkeypatch):
    """Memastikan get_ai_webhook_secret() raise RuntimeError di production jika unset."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("AI_WEBHOOK_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="Production Security Error: 'AI_WEBHOOK_SECRET' must be explicitly set"):
        get_ai_webhook_secret()


# =============================================================================
# 2. STUDENT BROADCAST IDOR PROTECTION TESTS
# =============================================================================

def test_student_broadcast_idor_protection(db, client):
    """Memastikan endpoint /sessions/{session_id}/broadcasts menolak siswa yang tidak terdaftar (IDOR)."""
    ctx = _create_school_hierarchy(db)
    session = ctx["session"]
    unauthorized_student = ctx["student2"]
    authorized_student = ctx["student1"]

    # Buat event broadcast pengawas
    broadcast_evt = ProctorAuditEvent(
        proctor_assignment_id=session.id,
        student_id=0,
        event_type="ANNOUNCEMENT",
        reason="PENTING: Waktu ujian tersisa 15 menit lagi.",
        proctor_id=ctx["teacher"].id,
        action_taken="BROADCAST",
    )
    db.add(broadcast_evt)
    db.commit()

    # 1. Siswa yang TIDAK berhak dan TIDAK memiliki attempt mencoba membaca -> MUST 403
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(unauthorized_student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res = client.get(f"/api/v1/exam/sessions/{session.id}/broadcasts")
        assert res.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # 2. Siswa yang memiliki attempt aktif membaca -> MUST 200 OK
    attempt = ExamAttempt(
        exam_session_id=session.id,
        student_id=authorized_student.id,
        status=ExamAttemptStatus.IN_PROGRESS,
        randomized_order=[ctx["question"].id],
        deadline_at=datetime.now(timezone.utc) + timedelta(minutes=45),
    )
    db.add(attempt)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": str(authorized_student.id),
        "role": "STUDENT",
        "school_id": ctx["school"].id,
    }
    try:
        res_ok = client.get(f"/api/v1/exam/sessions/{session.id}/broadcasts")
        assert res_ok.status_code == status.HTTP_200_OK
        data = res_ok.json()
        assert len(data["broadcasts"]) >= 1
        assert "PENTING" in data["broadcasts"][0]["message"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# 3. GENERIC 500 ERROR SANITIZATION (ZERO INTERNAL EXCEPTION LEAKAGE)
# =============================================================================

def test_checkin_error_leakage_sanitized(db, client):
    """Memastikan error fatal pada absensi check-in menghasilkan pesan generik tanpa trace internal."""
    ctx = _create_school_hierarchy(db)
    student = ctx["student1"]

    exp_ts = int(time.time()) + 180
    payload_str = f"{ctx['schedule'].id}:{exp_ts}"
    real_sig = hmac.new(QR_SIGNING_SECRET.encode(), payload_str.encode(), hashlib.sha256).hexdigest()[:16]

    pin_rec = ExamCheckinPin(
        pin_code="998877",
        schedule_id=ctx["schedule"].id,
        token=f"{ctx['schedule'].id}:{exp_ts}:{real_sig}",
        expires_ts=exp_ts,
    )
    db.add(pin_rec)
    db.commit()

    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("FATAL: Postgres deadlocked")):
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": str(student.id),
            "role": "STUDENT",
            "school_id": ctx["school"].id,
        }
        try:
            res = client.post(
                f"/api/v1/exam/checkin?token=998877&expected_schedule_id={ctx['schedule'].id}",
                headers={"X-Device-Id": "test-device-1"},
            )
            assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            detail = res.json()["detail"]
            assert detail == "Gagal menyimpan data absensi."
            assert "Postgres" not in detail
            assert "deadlocked" not in detail
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# 4. QR CRYPTOGRAPHY SEPARATION (QR_SIGNING_SECRET)
# =============================================================================

def test_qr_signing_secret_decoupling(monkeypatch):
    """Memastikan QR_SIGNING_SECRET dapat dikonfigurasi mandiri terpisah dari SECRET_KEY."""
    custom_qr_secret = "custom-dedicated-qr-signing-secret-key-999"
    monkeypatch.setenv("QR_SIGNING_SECRET", custom_qr_secret)

    resolved = get_qr_signing_secret()
    assert resolved == custom_qr_secret
