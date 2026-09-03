# 🤖 equigradeAI — Open-Source AI Essay Engine & Rubric Generator

> **Powered by GPT-OSS 120B (Groq LPU)** | **Plug-and-Play REST API** | **Adaptive Education Level Strictness (SD, SMP, SMA)**

`equigradeAI` is a lightweight, high-performance, open-source AI microservice built for automated **Essay Rubric Generation**, **Pedagogical Consistency Validation**, and **Batch Student Essay Grading**. Designed for educational institutions, LMS platforms, and developers who need an API-first AI engine to grade student essays objectively.

---

## ✨ Key Features

1. **🎯 Automated Essay Rubric Generation (`/api/v1/ai/rubric/generate`)**:
   - Analyzes questions and teacher answer keys to generate structured Bloom Taxonomy-aligned rubrics (C1-C6).
   - Extracts key concepts automatically.
   - Tailors complexity to education level (`SD`, `SMP`, `SMA`).

2. **🔍 Pedagogical Rubric & Key Validation (`/api/v1/ai/rubric/validate`)**:
   - Advises teachers on logical consistency between Question, Answer Key, and Rubric.
   - Returns review signals (`VALID`, `SUSPICIOUS`, `INVALID`).

3. **📝 Batch & Individual Essay Grading (`/api/v1/ai/grading/evaluate`, `/api/v1/ai/grading/batch-question`)**:
   - **Post-Exam Batch Grading**: Groups answers by `question_id` to evaluate multiple students in parallel chunks.
   - **Independent Fairness Guarantee**: Strictly isolates each student's score from others.
   - **RAG Augmented Grading**: Passive exemplar context from past teacher evaluations.

4. **⚡ High Performance & Low Latency**:
   - Powered by **Groq LPU Inference Engine** using `openai/gpt-oss-120b` with fallback to `openai/gpt-oss-20b`.

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/equigrade/equigradeAI.git
cd equigradeAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and set your Groq API Key:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=YOUR_GROQ_API_KEY_HERE
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
PORT=5000
```

### 3. Run the Server

```bash
python sandbox_app.py
```

The server will start at `http://localhost:5000`.

---

## 📡 REST API Reference

### 1. Health Check
`GET /api/v1/ai/health`

**Response:**
```json
{
  "status": "online",
  "service": "equigradeAI",
  "version": "2.0.0-modular",
  "engine": "GPT-OSS 120B (Groq LPU)"
}
```

---

### 2. Generate Essay Rubric
`POST /api/v1/ai/rubric/generate`

**Body:**
```json
{
  "question": "Jelaskan proses fotosintesis pada tumbuhan dan sebutkan organel tempat berlangsungnya.",
  "answer_key": "Fotosintesis adalah proses tumbuhan mengolah air dan CO2 menggunakan klorofil di dalam kloroplas.",
  "grade_level": "SMA",
  "education_class": "Kelas 11"
}
```

---

### 3. Batch Grade Question
`POST /api/v1/ai/grading/batch-question`

**Body:**
```json
{
  "question_id": 101,
  "question_text": "Jelaskan Hukum Dalton!",
  "answer_key": "Perbandingan massa unsur berangka bulat sederhana.",
  "rubric": [
    {"ku_id": "C1", "text": "Kesesuaian konsep hukum", "weight": 100.0}
  ],
  "submissions": [
    {"student_id": "std_1", "student_answer": "Jawaban siswa 1..."},
    {"student_id": "std_2", "student_answer": "Jawaban siswa 2..."}
  ]
}
```

---

## 📜 License & Open Source

This project is licensed under the **MIT License**. Free for commercial and educational use.
Developed with ❤️ for EquiGrade & Open-Source Education Community.
