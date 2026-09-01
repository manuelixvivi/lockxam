"""
equigradeAI — Open-Source Python Client Example
================================================
Demonstrates how to pull API keys dynamically and call the equigradeAI REST API
for automatic essay rubric generation and student answer grading.
"""

import json

import requests

# API Base URL (Change to your deployed server URL or local address)
BASE_URL = "http://localhost:5000"

# Your Groq API Key (Can be passed via header X-API-Key or Authorization Bearer)
GROQ_API_KEY = "gsk_your_groq_api_key_here"

headers = {"Content-Type": "application/json", "X-API-Key": GROQ_API_KEY}


def check_health():
    """1. Health Check"""
    print("\n--- [1] Checking API Health ---")
    try:
        res = requests.get(f"{BASE_URL}/api/v1/ai/health")
        print("Health Response:", json.dumps(res.json(), indent=2))
    except Exception as e:
        print("Error checking health:", e)


def generate_essay_rubric():
    """2. Generate Essay Rubric & Key Concepts"""
    print("\n--- [2] Generating Essay Rubric ---")
    payload = {
        "question_text": "Jelaskan proses fotosintesis pada tumbuhan dan sebutkan organel tempat berlangsungnya.",
        "answer_key": "Fotosintesis adalah proses tumbuhan mengolah air dan CO2 menggunakan energi cahaya matahari dengan klorofil di dalam organel kloroplas untuk menghasilkan glukosa dan oksigen.",
        "education_level": "SMA",
        "education_class": "Kelas 11",
    }

    try:
        res = requests.post(f"{BASE_URL}/api/v1/ai/rubric/generate", headers=headers, json=payload)
        data = res.json()
        print("Rubric Response:", json.dumps(data, indent=2))
        return data
    except Exception as e:
        print("Error generating rubric:", e)
        return {}


def grade_student_essay(rubrics, concepts):
    """3. Grade Student Essay Answer"""
    print("\n--- [3] Grading Student Essay Answer ---")
    payload = {
        "question_text": "Jelaskan proses fotosintesis pada tumbuhan dan sebutkan organel tempat berlangsungnya.",
        "answer_key": "Fotosintesis adalah proses tumbuhan mengolah air dan CO2 menggunakan klorofil di kloroplas.",
        "student_answer": "Fotosintesis adalah cara tumbuhan buat makanan dari cahaya matahari dan air di dalam kloroplas.",
        "education_level": "SMA",
        "education_class": "Kelas 11",
        "rubrics": rubrics,
        "concepts": concepts,
    }

    try:
        res = requests.post(f"{BASE_URL}/api/v1/ai/essay/grade", headers=headers, json=payload)
        print("Grading Response:", json.dumps(res.json(), indent=2))
    except Exception as e:
        print("Error grading essay:", e)


if __name__ == "__main__":
    check_health()

    # Run rubric generation
    rubric_data = generate_essay_rubric()

    if rubric_data.get("status") == "success":
        rubrics = rubric_data.get("rubrics", [])
        concepts = rubric_data.get("concepts", [])

        # Grade a student answer using generated rubrics
        grade_student_essay(rubrics, concepts)
