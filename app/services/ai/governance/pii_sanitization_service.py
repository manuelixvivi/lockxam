import re
from typing import Any, Dict, List, Tuple


class PiiSanitizationService:
    """
    Milestone A8: Privacy & PII Detection / Sanitization Engine.
    Detects personal identifying information (PII) in student responses and teacher feedback.
    Applies non-destructive token masking without mutating immutable historical assessment records.
    """

    # 1. Email Addresses
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    # 2. Indonesian Phone Numbers (+62 / 08...)
    PHONE_PATTERN = re.compile(r"(?:\+62|62|08)[0-9\-\s]{8,14}[0-9]")

    # 3. National Student Identity (NISN 10-digit) & Teacher Identity (NIP 18-digit)
    NISN_PATTERN = re.compile(r"\b(?:NISN\s*[:=]?\s*)?([0-9]{10})\b", re.IGNORECASE)
    NIP_PATTERN = re.compile(r"\b(?:NIP\s*[:=]?\s*)?([0-9]{18})\b", re.IGNORECASE)

    # 4. Self-Identification / Student Name Patterns
    NAME_SELF_ID_PATTERN = re.compile(
        r"\b(?:nama\s+saya(?:\s+adalah)?|nama\s*:\s*|siswa\s*:\s*|perkenalkan\s+saya)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
        re.IGNORECASE,
    )

    # 5. Teacher Honorifics & Name Patterns
    TEACHER_HONORIFIC_PATTERN = re.compile(
        r"\b(?:Pak|Bapak|Ibu|Bu|Bpk\.|Ibu\s+Guru|Pak\s+Guru|Dr\.|Drs\.|Dra\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
        re.IGNORECASE,
    )

    @classmethod
    def sanitize_text(
        cls, text: str, field_name: str = "text"
    ) -> Tuple[str, List[Dict[str, Any]], str]:
        """
        Scans and redacts PII tokens from input text.
        Returns:
            (sanitized_text, list_of_detected_entities, pii_status)
            pii_status: 'CLEAN' (no PII found) or 'SANITIZED' (PII detected and redacted).
        """
        if not text or not text.strip():
            return text, [], "CLEAN"

        sanitized = text
        detected: List[Dict[str, Any]] = []

        # 1. Redact Emails
        for match in cls.EMAIL_PATTERN.finditer(sanitized):
            val = match.group(0)
            detected.append(
                {
                    "type": "EMAIL",
                    "field": field_name,
                    "char_length": len(val),
                    "detection_method": "REGEX",
                }
            )
        sanitized = cls.EMAIL_PATTERN.sub("[EMAIL_ADDRESS]", sanitized)

        # 2. Redact Phone Numbers
        for match in cls.PHONE_PATTERN.finditer(sanitized):
            val = match.group(0).strip()
            detected.append(
                {
                    "type": "PHONE",
                    "field": field_name,
                    "char_length": len(val),
                    "detection_method": "REGEX",
                }
            )
        sanitized = cls.PHONE_PATTERN.sub("[PHONE_NUMBER]", sanitized)

        # 3. Redact NIP
        for match in cls.NIP_PATTERN.finditer(sanitized):
            val = match.group(0).strip()
            detected.append(
                {
                    "type": "NIP",
                    "field": field_name,
                    "char_length": len(val),
                    "detection_method": "REGEX",
                }
            )
        sanitized = cls.NIP_PATTERN.sub("[NIP_NUMBER]", sanitized)

        # 4. Redact NISN
        for match in cls.NISN_PATTERN.finditer(sanitized):
            val = match.group(0).strip()
            detected.append(
                {
                    "type": "NISN",
                    "field": field_name,
                    "char_length": len(val),
                    "detection_method": "REGEX",
                }
            )
        sanitized = cls.NISN_PATTERN.sub("[NISN_NUMBER]", sanitized)

        # 5. Redact Student Names with introduction context
        def replace_self_name(m: re.Match) -> str:
            full_match = m.group(0)
            name_part = m.group(1)
            detected.append(
                {
                    "type": "STUDENT_NAME",
                    "field": field_name,
                    "char_length": len(name_part),
                    "detection_method": "HEURISTIC_CONTEXT",
                }
            )
            prefix = full_match[: m.start(1) - m.start(0)]
            return f"{prefix}[STUDENT_NAME]"

        sanitized = cls.NAME_SELF_ID_PATTERN.sub(replace_self_name, sanitized)

        # 6. Redact Teacher Names with honorific context
        def replace_teacher_name(m: re.Match) -> str:
            full_match = m.group(0)
            name_part = m.group(1)
            detected.append(
                {
                    "type": "TEACHER_NAME",
                    "field": field_name,
                    "char_length": len(name_part),
                    "detection_method": "HEURISTIC_CONTEXT",
                }
            )
            prefix = full_match[: m.start(1) - m.start(0)]
            return f"{prefix}[TEACHER_NAME]"

        sanitized = cls.TEACHER_HONORIFIC_PATTERN.sub(replace_teacher_name, sanitized)

        status = "SANITIZED" if len(detected) > 0 else "CLEAN"
        return sanitized, detected, status
