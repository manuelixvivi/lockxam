/**
 * equigradeAI — Open-Source JavaScript / Node.js Client Example
 * =============================================================
 * Demonstrates how to pull API keys dynamically and call the equigradeAI REST API.
 */

const BASE_URL = "http://localhost:5000";
const GROQ_API_KEY = "gsk_your_groq_api_key_here";

async function main() {
  console.log("--- [1] Checking API Health ---");
  const healthRes = await fetch(`${BASE_URL}/api/v1/ai/health`);
  const healthData = await healthRes.json();
  console.log("Health:", healthData);

  console.log("\n--- [2] Generating Essay Rubric ---");
  const rubricRes = await fetch(`${BASE_URL}/api/v1/ai/rubric/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": GROQ_API_KEY,
    },
    body: JSON.stringify({
      question_text: "Jelaskan perbedaan sel hewan dan sel tumbuhan.",
      answer_key: "Sel tumbuhan memiliki dinding sel, kloroplas, dan vakuola besar. Sel hewan tidak memiliki dinding sel dan kloroplas.",
      education_level: "SMA",
      education_class: "Kelas 11",
    }),
  });
  const rubricData = await rubricRes.json();
  console.log("Generated Rubrics:", JSON.stringify(rubricData, null, 2));

  if (rubricData.status === "success") {
    console.log("\n--- [3] Grading Student Essay ---");
    const gradeRes = await fetch(`${BASE_URL}/api/v1/ai/essay/grade`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": GROQ_API_KEY,
      },
      body: JSON.stringify({
        question_text: "Jelaskan perbedaan sel hewan dan sel tumbuhan.",
        answer_key: "Sel tumbuhan memiliki dinding sel dan kloroplas.",
        student_answer: "Sel tumbuhan punya dinding sel sama kloroplas buat fotosintesis, kalau sel hewan ga punya.",
        education_level: "SMA",
        education_class: "Kelas 11",
        rubrics: rubricData.rubrics,
        concepts: rubricData.concepts,
      }),
    });
    const gradeData = await gradeRes.json();
    console.log("Grading Result:", JSON.stringify(gradeData, null, 2));
  }
}

main().catch(console.error);
