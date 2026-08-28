import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_file_does_not_contain(filepath, pattern, error_message, repo_exemption=False):
    if not os.path.exists(filepath):
        return True
    repo_call_pattern = r"repository\.(update|delete|create|save|add)\("
    passed = True
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        in_docstring = False
        for line_num, line in enumerate(f, 1):
            sline = line.strip()

            # Accurate docstring toggle tracking based on triple quotes count
            dq_count = sline.count('"""') + sline.count("'''")
            if dq_count % 2 != 0:
                in_docstring = not in_docstring
                if sline.startswith('"""') or sline.startswith("'''"):
                    continue

            if (
                in_docstring
                or sline.startswith("#")
                or sline.startswith("//")
                or sline.startswith("*")
            ):
                continue

            if re.search(pattern, line):
                if repo_exemption and re.search(repo_call_pattern, line):
                    continue
                print(
                    f"[FAIL] {error_message} found at line {line_num} in {os.path.relpath(filepath, BASE_DIR)}: {sline}"
                )
                passed = False
    return passed


def run_checks():
    print("=== EQUIGRADE x LOCKXAM — AUTOMATED ARCHITECTURE STATIC CHECKS ===")
    passed = True

    db_access_patterns = [
        (r"\bdb\.query\(", "Direct ORM db.query() call"),
        (r"\bdb\.get\(", "Direct ORM db.get() call"),
        (r"\bdb\.execute\(", "Direct ORM db.execute() call"),
        (r"\bdb\.scalar\(", "Direct ORM db.scalar() call"),
        (r"\bdb\.scalars\(", "Direct ORM db.scalars() call"),
        (r"\bselect\(", "Direct ORM select() query"),
        (r"\binsert\(", "Direct ORM insert() query"),
        (r"\bupdate\(", "Direct ORM update() query"),
        (r"\bdelete\(", "Direct ORM delete() query"),
    ]

    # 1. Zero active direct DB access across ALL app/services/ (all subdirectories)
    services_dir = os.path.join(BASE_DIR, "app", "services")
    for root, _, files in os.walk(services_dir):
        for file in files:
            if file.endswith(".py"):
                fp = os.path.join(root, file)
                for pat, msg in db_access_patterns:
                    is_exempt_op = pat in [r"\bupdate\(", r"\bdelete\("]
                    if not check_file_does_not_contain(
                        fp, pat, f"{msg} in Service Layer", repo_exemption=is_exempt_op
                    ):
                        passed = False

    # 2. Zero direct DB access (db.get / db.query / db.execute) in app/api/exam.py and app/api/auth.py
    for api_rel in ["app/api/exam.py", "app/api/auth.py"]:
        api_fp = os.path.join(BASE_DIR, api_rel)
        for pat in [r"\bdb\.get\(", r"\bdb\.query\(", r"\bdb\.execute\("]:
            if not check_file_does_not_contain(api_fp, pat, f"Direct ORM {pat} call in {api_rel}"):
                passed = False

    # 3. Zero cross-domain imports in app/services/exam/
    exam_svc_dir = os.path.join(BASE_DIR, "app", "services", "exam")
    for root, _, files in os.walk(exam_svc_dir):
        for file in files:
            if file.endswith(".py"):
                fp = os.path.join(root, file)
                if not check_file_does_not_contain(
                    fp,
                    r"app\.repositories\.academic",
                    "Cross-domain import from academic repositories",
                ):
                    passed = False
                if not check_file_does_not_contain(
                    fp, r"app\.models\.academic", "Cross-domain import from academic models"
                ):
                    passed = False
                if not check_file_does_not_contain(
                    fp, r"app\.models\.teacher", "Cross-domain import from teacher models"
                ):
                    passed = False

    # 4. Zero localStorage token leakage in frontend
    frontend_src = os.path.join(BASE_DIR, "frontend", "src")
    for root, _, files in os.walk(frontend_src):
        for file in files:
            if file.endswith((".ts", ".tsx")):
                fp = os.path.join(root, file)
                if not check_file_does_not_contain(
                    fp, r"localStorage.*access_token", "localStorage access_token usage"
                ):
                    passed = False
                if not check_file_does_not_contain(
                    fp, r"localStorage.*refresh_token", "localStorage refresh_token usage"
                ):
                    passed = False

    # 5. Zero token_default, uploadAnswerImage, or BROADCAST_STORE
    for root, _, files in os.walk(BASE_DIR):
        if "node_modules" in root or ".git" in root or ".venv" in root or "scripts" in root:
            continue
        for file in files:
            if file.endswith((".ts", ".tsx", ".py")):
                fp = os.path.join(root, file)
                if not check_file_does_not_contain(
                    fp, r"token_default", "Hardcoded fallback token 'token_default'"
                ):
                    passed = False
                if not check_file_does_not_contain(
                    fp,
                    r"uploadAnswerImage|upload-answer-image",
                    "Unfrozen uploadAnswerImage feature",
                ):
                    passed = False
                if not check_file_does_not_contain(
                    fp, r"BROADCAST_STORE", "In-memory BROADCAST_STORE dict"
                ):
                    passed = False

    # 6. Zero mockQuestions in StudentCbtEngineView.tsx
    cbt_view = os.path.join(
        BASE_DIR, "frontend", "src", "views", "student", "StudentCbtEngineView.tsx"
    )
    if not check_file_does_not_contain(cbt_view, r"mockQuestions", "CBT mock fallback questions"):
        passed = False

    # 7. TeacherSubject authority — no active writes to teacher.subjects_taught in services or API.
    #    Pattern: any line that assigns a value to teacher.subjects_taught
    #    (e.g. teacher.subjects_taught = ...) outside of the read-only projection in list_teachers.
    #    We explicitly exclude: lines that are comments, lines in list_teachers (read-time projection).
    #    list_teachers() in staff_service.py is the ONE permitted projection write site.
    def check_no_subjects_taught_write(filepath, allowed_function_context="list_teachers"):
        """Fail if any active teacher.subjects_taught = assignment exists outside the read projection."""
        if not os.path.exists(filepath):
            return True
        # Pattern: assignment to .subjects_taught
        write_pat = re.compile(r"\.subjects_taught\s*=")
        ok = True
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            in_docstring = False
            current_fn = None
            for line_num, line in enumerate(f, 1):
                sline = line.strip()
                # Track docstrings
                dq_count = sline.count('"""') + sline.count("'''")
                if dq_count % 2 != 0:
                    in_docstring = not in_docstring
                if in_docstring or sline.startswith("#"):
                    continue
                # Rough function context tracking
                fn_match = re.match(r"def\s+(\w+)\s*\(", sline)
                if fn_match:
                    current_fn = fn_match.group(1)
                if write_pat.search(line):
                    if current_fn == allowed_function_context:
                        # list_teachers is the one permitted projection write site — skip
                        continue
                    rel = os.path.relpath(filepath, BASE_DIR)
                    print(
                        f"[FAIL] Active write to teacher.subjects_taught (TeacherSubject authority violation) "
                        f"at line {line_num} in {rel}: {sline}"
                    )
                    ok = False
        return ok

    # Apply to all services and api files
    for root, _, files in os.walk(os.path.join(BASE_DIR, "app", "services")):
        for file in files:
            if file.endswith(".py"):
                if not check_no_subjects_taught_write(os.path.join(root, file)):
                    passed = False
    for root, _, files in os.walk(os.path.join(BASE_DIR, "app", "api")):
        for file in files:
            if file.endswith(".py"):
                if not check_no_subjects_taught_write(
                    os.path.join(root, file), allowed_function_context="__NONE__"
                ):
                    passed = False

    # 8. No writable subjects_taught field in Create/Update request schemas
    schemas_dir = os.path.join(BASE_DIR, "app", "schemas")

    def check_no_writable_subjects_taught_schema(filepath):
        """Fail if a Create/Update request schema exposes subjects_taught as a non-comment field."""
        if not os.path.exists(filepath):
            return True
        in_request_cls = False
        ok = True
        write_cls_pat = re.compile(r"class\s+\w*(Create|Update|Request)\w*\s*\(")
        field_pat = re.compile(r"^\s*subjects_taught\s*:")
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                sline = line.strip()
                if sline.startswith("#"):
                    continue
                if write_cls_pat.match(sline):
                    in_request_cls = True
                elif re.match(r"^class\s+", sline):
                    in_request_cls = False
                if in_request_cls and field_pat.match(line):
                    rel = os.path.relpath(filepath, BASE_DIR)
                    print(
                        f"[FAIL] Writable subjects_taught field in request schema at line {line_num} in {rel}: {sline}"
                    )
                    ok = False
        return ok

    for root, _, files in os.walk(schemas_dir):
        for file in files:
            if file.endswith(".py"):
                if not check_no_writable_subjects_taught_schema(os.path.join(root, file)):
                    passed = False

    if passed:
        print("[PASS] ALL 100% ARCHITECTURE QUALITY GATES CLEARED!")
        sys.exit(0)
    else:
        print("[FAIL] ARCHITECTURE CONFORMANCE CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
