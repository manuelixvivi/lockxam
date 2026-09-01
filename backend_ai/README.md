# 🤖 equigradeAI — Open-Source AI Essay Engine & Rubric Generator

> **Powered by Llama 3 (Groq LPU)** | **Plug-and-Play REST API** | **Adaptive Education Level Strictness (SD, SMP, SMA)**

`equigradeAI` is a lightweight, high-performance, open-source AI microservice built for automated **Essay Rubric Generation** and **Hybrid Student Essay Grading**. Designed for educational institutions, LMS platforms, and developers who need an API-first AI engine to grade student essays objectively.

---

## ✨ Key Features

1. **🎯 Automated Essay Rubric Generation (`/api/v1/ai/rubric/generate`)**:
   - Analyzes questions and teacher answer keys to generate structured Bloom Taxonomy-aligned rubrics (C1-C6).
   - Extracts key concepts automatically.
   - Tailors complexity to education level (`SD`, `SMP`, `SMA`).

2. **📝 Hybrid Student Essay Grading (`/api/v1/ai/essay/grade`)**:
   - **Procedural Essays**: Full LLM cognitive evaluation against generated rubrics.
   - **Enumeration Essays**: Hybrid LLM item matcher + deterministic Python scoring (zero math hallucinations).
   - **Adaptive Strictness**: Lenient for SD, moderate for SMP, strict for SMA.
   - **Language & Enrichment Appreciation**: Awards full credit for casual phrasing or extra correct context.

3. **🔑 Plug-and-Play Dynamic API Key Integration**:
   - Zero hardcoding required! Callers can pass their Groq API Key dynamically via HTTP headers (`X-API-Key`, `X-Groq-API-Key`, `Authorization: Bearer <key>`) or use server `.env`.

4. **⚡ High Performance & Low Latency**:
   - Powered by **Groq LPU Inference Engine** using `llama-3.1-8b-instant` (rubrics) and `llama-3.3-70b-versatile` (grading).

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
pip install -r requirements_sandbox.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and set your Groq API Key:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
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
  "version": "1.0.0-opensource",
  "engine": "Llama-3 (Groq LPU)"
}
```

---

### 2. Generate Essay Rubric
`POST /api/v1/ai/rubric/generate`

**Headers:**
```http
Content-Type: application/json
X-API-Key: gsk_your_groq_api_key_here
```

**Body:**
```json
{
  "question_text": "Jelaskan proses fotosintesis pada tumbuhan dan sebutkan organel tempat berlangsungnya.",
  "answer_key": "Fotosintesis adalah proses tumbuhan mengolah air dan CO2 menggunakan klorofil di dalam kloroplas.",
  "education_level": "SMA",
  "education_class": "Kelas 11"
}
```

**Response:**
```json
{
  "status": "success",
  "question_type": "PROSEDURAL",
  "bloom_level": "C3",
  "complexity_score": 70,
  "concepts": ["fotosintesis", "klorofil", "kloroplas"],
  "rubrics": [
    {
      "ku_id": "ku_1",
      "text": "Menjelaskan konsep dasar fotosintesis dengan tepat",
      "weight": 60,
      "bloom_level": "C3"
    },
    {
      "ku_id": "ku_2",
      "text": "Mengidentifikasi kloroplas sebagai organel berlangsungnya fotosintesis",
      "weight": 40,
      "bloom_level": "C2"
    }
  ]
}
```

---

### 3. Grade Student Essay
`POST /api/v1/ai/essay/grade`

**Headers:**
```http
Content-Type: application/json
X-API-Key: gsk_your_groq_api_key_here
```

**Body:**
```json
{
  "question_text": "Jelaskan proses fotosintesis pada tumbuhan dan sebutkan organel tempat berlangsungnya.",
  "answer_key": "Fotosintesis adalah proses tumbuhan mengolah air dan CO2 di kloroplas.",
  "student_answer": "Fotosintesis adalah cara tumbuhan buat makanan dari cahaya matahari di organel kloroplas.",
  "education_level": "SMA",
  "education_class": "Kelas 11",
  "rubrics": [
    { "ku_id": "ku_1", "text": "Menjelaskan konsep dasar...", "weight": 60 },
    { "ku_id": "ku_2", "text": "Mengidentifikasi kloroplas...", "weight": 40 }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "final_score": 100,
  "decision": {
    "status": "EVALUATED",
    "final_score": 100,
    "confidence": 0.95
  },
  "metrics": {
    "concept": 100,
    "semantic": 82,
    "logic": 100,
    "reasoning": 100
  },
  "feedback": "Jawaban Anda sangat baik! Anda telah menjelaskan proses fotosintesis dan peran kloroplas secara akurat. 🌟",
  "rubric_scores": [
    { "ku_id": "ku_1", "text": "Menjelaskan konsep dasar...", "weight": 60, "achieved": 100 },
    { "ku_id": "ku_2", "text": "Mengidentifikasi kloroplas...", "weight": 40, "achieved": 100 }
  ]
}
```

---

## 💻 SDK & Code Examples

### Python (`client_example.py`)
```python
import requests

res = requests.post(
    "http://localhost:5000/api/v1/ai/rubric/generate",
    headers={"X-API-Key": "gsk_your_key_here"},
    json={
        "question_text": "Jelaskan pengertian fotosintesis.",
        "answer_key": "Fotosintesis adalah...",
        "education_level": "SMA"
    }
)
print(res.json())
```

### Node.js (`client_example.js`)
```javascript
const res = await fetch("http://localhost:5000/api/v1/ai/rubric/generate", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "gsk_your_key_here"
  },
  body: JSON.stringify({
    question_text: "Jelaskan pengertian fotosintesis.",
    answer_key: "Fotosintesis adalah...",
    education_level: "SMA"
  })
});
console.log(await res.json());
```

---

## 📜 License & Open Source

This project is licensed under the **MIT License**. Free for commercial and educational use.
Developed with ❤️ for EquiGrade & Open-Source Education Community.
