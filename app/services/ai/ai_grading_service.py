import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EQUIGRADE_AI_URL = os.environ.get("EQUIGRADE_AI_URL", "http://localhost:5000")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


class AiGradingService:
    """Service bridge connecting EquiGrade backend to equigradeAI Open-Source microservice."""

    @staticmethod
    def check_ai_health() -> Dict[str, Any]:
        """Check if equigradeAI microservice is online."""
        url = f"{EQUIGRADE_AI_URL.rstrip('/')}/api/v1/ai/health"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EquiGrade-Backend/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"equigradeAI service check failed: {e}")

        return {
            "status": "offline",
            "service": "equigradeAI",
            "message": "Service offline or unreachable",
        }

    @staticmethod
    def generate_rubric(
        question_text: str,
        answer_key: str,
        education_level: str = "SMA",
        education_class: str = "Kelas 11",
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call equigradeAI to generate essay rubrics & key concepts."""
        url = f"{EQUIGRADE_AI_URL.rstrip('/')}/api/v1/ai/rubric/generate"
        headers = {"Content-Type": "application/json", "X-API-Key": api_key or GROQ_API_KEY}
        payload = {
            "question_text": question_text,
            "answer_key": answer_key,
            "education_level": education_level,
            "education_class": education_class,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            error_body = he.read().decode("utf-8")
            logger.error(f"AI Rubric Generation HTTP Error {he.code}: {error_body}")
            raise RuntimeError(f"Gagal generate rubrik AI: {error_body}")
        except Exception as e:
            logger.error(f"AI Rubric Generation Exception: {e}")
            raise RuntimeError(f"Gagal terhubung ke equigradeAI service ({e})")

    @staticmethod
    def grade_essay(
        question_text: str,
        answer_key: str,
        student_answer: str,
        rubrics: Optional[List[Dict[str, Any]]] = None,
        concepts: Optional[List[str]] = None,
        education_level: str = "SMA",
        education_class: str = "Kelas 11",
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call equigradeAI to grade a student's essay answer."""
        url = f"{EQUIGRADE_AI_URL.rstrip('/')}/api/v1/ai/essay/grade"
        headers = {"Content-Type": "application/json", "X-API-Key": api_key or GROQ_API_KEY}
        payload = {
            "question_text": question_text,
            "answer_key": answer_key,
            "student_answer": student_answer,
            "rubrics": rubrics or [],
            "concepts": concepts or [],
            "education_level": education_level,
            "education_class": education_class,
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            error_body = he.read().decode("utf-8")
            logger.error(f"AI Essay Grading HTTP Error {he.code}: {error_body}")
            raise RuntimeError(f"Gagal koreksi essay AI: {error_body}")
        except Exception as e:
            logger.error(f"AI Essay Grading Exception: {e}")
            raise RuntimeError(f"Gagal terhubung ke equigradeAI service ({e})")
