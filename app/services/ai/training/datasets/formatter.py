import json
import logging
from typing import Any, Dict, List, Optional

from app.services.ai.training.schemas import SftConversationExample, SftMessage

logger = logging.getLogger(__name__)


class SftFormatter:
    """
    Milestone A9.1: SFT Conversational Formatter.
    Transforms raw teacher-ground-truth assessment payloads into standardized
    ChatML / OpenAI conversational messages with structured JSON assistant completions.
    Zero historical RAG context is injected to maintain clean parameter adaptation isolation.
    """

    SYSTEM_PROMPT = (
        "You are EquiGrade AI, an objective, rigorous, and pedagogical educational assessment evaluator. "
        "Evaluate student essay answers strictly adhering to the provided question, answer key, and scoring rubric. "
        "Output your evaluation in valid structured JSON format containing 'score', 'normalized_score', and 'feedback'."
    )

    @classmethod
    def _format_rubric_text(cls, rubric: Any) -> str:
        """
        Formats rubric criteria into clear textual guidelines.
        """
        if not rubric:
            return "No explicit rubric provided. Grade based on alignment with the answer key."

        if isinstance(rubric, str):
            return rubric

        if isinstance(rubric, list):
            lines = []
            for idx, r in enumerate(rubric, 1):
                if isinstance(r, dict):
                    desc = r.get("criterion") or r.get("description") or r.get("name") or str(r)
                    weight = r.get("weight") or r.get("points") or r.get("max_points") or ""
                    weight_str = f" (Weight/Points: {weight})" if weight else ""
                    lines.append(f"{idx}. {desc}{weight_str}")
                else:
                    lines.append(f"{idx}. {str(r)}")
            return "\n".join(lines)

        return str(rubric)

    @classmethod
    def format_user_prompt(
        cls,
        question: str,
        answer_key: Optional[str],
        rubric: Any,
        student_answer: str,
        max_score: float = 10.0,
    ) -> str:
        """
        Constructs a structured Markdown prompt for the user role.
        """
        rubric_text = cls._format_rubric_text(rubric)
        key_text = (answer_key or "").strip() or "Standard academic comprehension expected."

        return (
            f"### QUESTION\n{question.strip()}\n\n"
            f"### ANSWER KEY / REFERENCE ANSWER\n{key_text}\n\n"
            f"### SCORING RUBRIC (Max Score: {max_score})\n{rubric_text}\n\n"
            f"### STUDENT ESSAY ANSWER\n{student_answer.strip()}\n\n"
            f"Evaluate the student's essay answer and return your evaluation in structured JSON format "
            f"containing 'score' (number), 'normalized_score' (0.0 - 1.0), and 'feedback' (substantive qualitative explanation)."
        )

    @classmethod
    def format_assistant_response(
        cls,
        score: float,
        normalized_score: float,
        feedback: str,
        rubric_applied: Optional[Any] = None,
    ) -> str:
        """
        Constructs canonical deterministic JSON string for assistant role completion.
        """
        response_dict: Dict[str, Any] = {
            "score": round(float(score), 2),
            "normalized_score": round(float(normalized_score), 4),
            "feedback": (feedback or "").strip(),
        }
        if rubric_applied:
            response_dict["rubric_applied"] = rubric_applied

        return json.dumps(response_dict, ensure_ascii=False, indent=2)

    @classmethod
    def format_single_example(cls, raw_payload: Dict[str, Any]) -> SftConversationExample:
        """
        Converts a single candidate raw SFT dictionary into an SftConversationExample.
        """
        question = raw_payload.get("question", "")
        answer_key = raw_payload.get("answer_key", "")
        rubric = raw_payload.get("rubric")
        student_answer = raw_payload.get("student_answer", "")
        max_score = float(raw_payload.get("max_score", 10.0))

        target = raw_payload.get("target", {})
        score = float(target.get("score", 0.0))

        # Calculate normalized score if not explicitly present
        if "normalized_score" in target:
            normalized_score = float(target["normalized_score"])
        elif "final_percentage" in target:
            normalized_score = round(float(target["final_percentage"]) / 100.0, 4)
        else:
            normalized_score = round(score / max_score, 4) if max_score > 0 else 0.0

        feedback = target.get("feedback", "")
        rubric_applied = target.get("rubric_applied")

        user_content = cls.format_user_prompt(
            question=question,
            answer_key=answer_key,
            rubric=rubric,
            student_answer=student_answer,
            max_score=max_score,
        )

        assistant_content = cls.format_assistant_response(
            score=score,
            normalized_score=normalized_score,
            feedback=feedback,
            rubric_applied=rubric_applied,
        )

        messages = [
            SftMessage(role="system", content=cls.SYSTEM_PROMPT),
            SftMessage(role="user", content=user_content),
            SftMessage(role="assistant", content=assistant_content),
        ]

        return SftConversationExample(
            messages=messages,
            task=raw_payload.get("task", "essay_grading"),
            candidate_id=raw_payload.get("candidate_id"),
            question_group_key=raw_payload.get("question_group_key"),
            metadata={
                "subject": raw_payload.get("subject"),
                "class_level": raw_payload.get("class_level"),
                "max_score": max_score,
                "target_score": score,
            },
        )

    @classmethod
    def format_split(cls, raw_items: List[Dict[str, Any]]) -> List[SftConversationExample]:
        """
        Formats a list of candidate dictionaries into conversational SFT examples.
        """
        return [cls.format_single_example(item) for item in raw_items]

    @classmethod
    def format_dataset(
        cls, split_payloads: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[SftConversationExample]]:
        """
        Formats all splits ('train', 'val', 'test') into conversational SFT examples.
        """
        return {split_name: cls.format_split(items) for split_name, items in split_payloads.items()}
