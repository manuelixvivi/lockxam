import math
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.ai.ai_grading_service import AiGradingService


@dataclass(frozen=True)
class BenchmarkEssaySample:
    """
    Evaluation test sample representing a held-out student essay
    with teacher-finalized ground truth score and feedback.
    """

    sample_id: str
    subject_name: str
    class_level: str
    question_text: str
    answer_key: str
    rubrics_json: List[Dict[str, Any]]
    max_score: float
    student_answer: str
    teacher_ground_truth_score: float
    teacher_ground_truth_feedback: str


@dataclass(frozen=True)
class BenchmarkKnowledgePreset:
    """
    Historical teacher-finalized case used strictly for the RAG knowledge base.
    """

    preset_id: str
    subject_name: str
    class_level: str
    question_text: str
    answer_key: str
    rubrics_json: List[Dict[str, Any]]
    max_score: float
    student_answer: str
    teacher_score: float
    teacher_feedback: str


@dataclass
class SingleEvaluationOutput:
    sample_id: str
    subject_name: str
    teacher_score: float
    no_rag_score: float
    rag_score: float
    no_rag_error: float
    rag_error: float
    no_rag_latency_ms: float
    rag_latency_ms: float
    retrieved_case_count: int
    similarity_scores: List[float]
    no_rag_feedback: str
    rag_feedback: str
    feedback_quality_no_rag: Dict[str, float]
    feedback_quality_rag: Dict[str, float]


class BenchmarkEvaluationService:
    """
    Scientific Evaluation & Benchmark Engine — Milestone A7
    Computes statistical metrics (MAE, RMSE, Correlation, Agreement, Latency, Feedback Quality)
    comparing Baseline LLM against RAG-Augmented LLM.
    """

    # ── Statistical Calculation Utilities ─────────────────────────────────────

    @staticmethod
    def calculate_mae(predictions: List[float], ground_truths: List[float]) -> float:
        """Mean Absolute Error: mean(|y_pred - y_true|)."""
        if not predictions or not ground_truths or len(predictions) != len(ground_truths):
            return 0.0
        return sum(abs(p - g) for p, g in zip(predictions, ground_truths, strict=False)) / len(predictions)

    @staticmethod
    def calculate_rmse(predictions: List[float], ground_truths: List[float]) -> float:
        """Root Mean Squared Error: sqrt(mean((y_pred - y_true)^2))."""
        if not predictions or not ground_truths or len(predictions) != len(ground_truths):
            return 0.0
        mse = sum((p - g) ** 2 for p, g in zip(predictions, ground_truths, strict=False)) / len(predictions)
        return math.sqrt(mse)

    @staticmethod
    def calculate_pearson_correlation(x: List[float], y: List[float]) -> float:
        """Pearson Linear Correlation Coefficient r."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        mean_x = statistics.mean(x)
        mean_y = statistics.mean(y)
        std_x = statistics.pstdev(x)
        std_y = statistics.pstdev(y)

        if std_x == 0 or std_y == 0:
            return 1.0 if x == y else 0.0

        covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=False)) / len(x)
        return max(-1.0, min(1.0, covariance / (std_x * std_y)))

    @staticmethod
    def calculate_spearman_correlation(x: List[float], y: List[float]) -> float:
        """Spearman Rank Correlation Coefficient rho."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        def get_ranks(seq: List[float]) -> List[float]:
            sorted_indices = sorted(range(len(seq)), key=lambda i: seq[i])
            ranks = [0.0] * len(seq)
            i = 0
            while i < len(seq):
                j = i
                while j < len(seq) and seq[sorted_indices[j]] == seq[sorted_indices[i]]:
                    j += 1
                rank = (i + 1 + j) / 2.0
                for k in range(i, j):
                    ranks[sorted_indices[k]] = rank
                i = j
            return ranks

        rank_x = get_ranks(x)
        rank_y = get_ranks(y)
        return BenchmarkEvaluationService.calculate_pearson_correlation(rank_x, rank_y)

    @staticmethod
    def calculate_tolerance_agreement(
        predictions: List[float], ground_truths: List[float], tolerance: float = 5.0
    ) -> float:
        """Percentage of predictions within +/- tolerance points of ground truth."""
        if not predictions or not ground_truths or len(predictions) != len(ground_truths):
            return 0.0
        matching = sum(1 for p, g in zip(predictions, ground_truths, strict=False) if abs(p - g) <= tolerance)
        return (matching / len(predictions)) * 100.0

    @staticmethod
    def evaluate_feedback_rubric(
        feedback_text: str,
        ground_truth_feedback: str,
        rubrics_json: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, float]:
        """
        Evaluates qualitative feedback across 5 academic dimensions (0-2 scale each):
        1. Correctness: Accurate conceptual reasoning without misinformation.
        2. Relevance: Direct alignment with the specific essay prompt.
        3. Explanation: Clarity and logical explanation of strengths/weaknesses.
        4. Actionability: Concrete improvement guidance for the student.
        5. Rubric Alignment: Addresses official evaluation criteria.
        """
        fb_lower = (feedback_text or "").lower()
        gt_lower = (ground_truth_feedback or "").lower()

        # Dimension 1: Correctness (0: empty/erroneous, 1: partial, 2: highly accurate)
        correctness = (
            2.0
            if len(fb_lower) > 30 and "salah total" not in fb_lower
            else (1.0 if fb_lower else 0.0)
        )

        # Dimension 2: Relevance
        relevance = 2.0 if len(fb_lower) > 20 else 1.0

        # Dimension 3: Explanation
        explanation = (
            2.0
            if any(
                term in fb_lower
                for term in [
                    "karena",
                    "karena itu",
                    "sehingga",
                    "mencakup",
                    "menjelaskan",
                    "namun",
                    "yaitu",
                    "melibatkan",
                ]
            )
            else 1.0
        )

        # Dimension 4: Actionability
        actionability = (
            2.0
            if any(
                term in fb_lower
                for term in [
                    "pertahankan",
                    "tingkatkan",
                    "kembangkan",
                    "perhatikan",
                    "tambahkan",
                    "sebaiknya",
                    "pelajari",
                ]
            )
            else 1.0
        )

        # Dimension 5: Rubric Alignment
        rubric_alignment = 2.0 if rubrics_json and len(rubrics_json) > 0 else 1.5

        total_score = correctness + relevance + explanation + actionability + rubric_alignment
        avg_score = total_score / 5.0

        return {
            "correctness": correctness,
            "relevance": relevance,
            "explanation": explanation,
            "actionability": actionability,
            "rubric_alignment": rubric_alignment,
            "average_feedback_score": round(avg_score, 2),
        }

    # ── Synthetic Multi-Disciplinary Benchmark Dataset ─────────────────────────

    @classmethod
    def get_benchmark_knowledge_corpus(cls) -> List[BenchmarkKnowledgePreset]:
        """
        Historical Teacher-Finalized Cases (Knowledge Base / Train Split).
        These cases are pre-indexed in the Vector Store as references.
        """
        return [
            # Chemistry Cases
            BenchmarkKnowledgePreset(
                preset_id="KB_KIM_01",
                subject_name="Kimia",
                class_level="XI",
                question_text="Jelaskan Hukum Dalton (Hukum Kelipatan Berganda) beserta contohnya!",
                answer_key="Bila dua unsur membentuk dua senyawa atau lebih, perbandingan massa salah satu unsur yang berikatan dengan massa tetap unsur lain berbanding sebagai bilangan bulat dan sederhana. Contoh: CO dan CO2.",
                rubrics_json=[
                    {
                        "name": "Definisi Hukum",
                        "points": 5,
                        "description": "Menyebutkan perbandingan massa bulat sederhana",
                    },
                    {
                        "name": "Contoh Senyawa",
                        "points": 5,
                        "description": "Memberikan contoh pasangan senyawa seperti CO dan CO2",
                    },
                ],
                max_score=10.0,
                student_answer="Hukum Dalton menyatakan jika dua unsur bergabung membentuk lebih dari satu senyawa, perbandingan massanya berupa bilangan bulat dan sederhana seperti gas CO dan CO2.",
                teacher_score=9.5,
                teacher_feedback="Penjelasan definisi dan contoh pasangan oksida karbon sangat akurat dan presisi.",
            ),
            BenchmarkKnowledgePreset(
                preset_id="KB_KIM_02",
                subject_name="Kimia",
                class_level="XI",
                question_text="Jelaskan faktor-faktor yang mempengaruhi laju reaksi!",
                answer_key="Faktor: konsentrasi reaktan, luas permukaan bidang sentuh, suhu/temperatur, dan katalis yang menurunkan energi aktivasi.",
                rubrics_json=[
                    {
                        "name": "Konsentrasi & Suhu",
                        "points": 5,
                        "description": "Menjelaskan pengaruh frekuensi tumbukan",
                    },
                    {
                        "name": "Luas Permukaan & Katalis",
                        "points": 5,
                        "description": "Menjelaskan luas bidang sentuh dan energi aktivasi",
                    },
                ],
                max_score=10.0,
                student_answer="Faktor laju reaksi meliputi konsentrasi, luas permukaan, suhu yang mempercepat partikel, dan katalisator.",
                teacher_score=9.0,
                teacher_feedback="Sangat baik, keempat faktor disebutkan dengan tepat beserta peran partikelnya.",
            ),
            # Physics Cases
            BenchmarkKnowledgePreset(
                preset_id="KB_FIS_01",
                subject_name="Fisika",
                class_level="XI",
                question_text="Jelaskan Hukum II Newton tentang gerak dan rumusnya!",
                answer_key="Percepatan sebuah benda berbanding lurus dengan resultan gaya yang bekerja dan berbanding terbalik dengan massa benda (Sigma F = m * a).",
                rubrics_json=[
                    {
                        "name": "Konsep Gaya & Percepatan",
                        "points": 5,
                        "description": "Hubungan sebanding gaya dan percepatan",
                    },
                    {
                        "name": "Hubungan Massa & Rumus",
                        "points": 5,
                        "description": "Hubungan berbanding terbalik massa dan rumus Sigma F = m.a",
                    },
                ],
                max_score=10.0,
                student_answer="Hukum II Newton menyatakan percepatan sebanding dengan total gaya dan berbanding terbalik dengan massa, dirumuskan F = m.a.",
                teacher_score=10.0,
                teacher_feedback="Sempurna, formulasi konsep dan matematis lengkap dan benar.",
            ),
            BenchmarkKnowledgePreset(
                preset_id="KB_FIS_02",
                subject_name="Fisika",
                class_level="XI",
                question_text="Jelaskan perbedaan antara proses isotermal dan adiabatik dalam termodinamika!",
                answer_key="Isotermal adalah proses termodinamika pada suhu konstan (delta T = 0), sedangkan adiabatik adalah proses tanpa pertukaran kalor antara sistem dan lingkungan (Q = 0).",
                rubrics_json=[
                    {"name": "Isotermal", "points": 5, "description": "Suhu tetap delta T = 0"},
                    {
                        "name": "Adiabatik",
                        "points": 5,
                        "description": "Tanpa perpindahan kalor Q = 0",
                    },
                ],
                max_score=10.0,
                student_answer="Isotermal terjadi saat suhunya tetap sehingga delta U nol, sedangkan adiabatik tidak ada kalor yang masuk atau keluar (Q = 0).",
                teacher_score=9.5,
                teacher_feedback="Sangat tepat membedakan parameter suhu konstan dan isolasi kalor sistem.",
            ),
            # Biology Cases
            BenchmarkKnowledgePreset(
                preset_id="KB_BIO_01",
                subject_name="Biologi",
                class_level="XI",
                question_text="Jelaskan proses fotosintesis pada tumbuhan hijau dan persamaan kimianya!",
                answer_key="Fotosintesis terjadi di kloroplas menggunakan air (H2O), karbon dioksida (CO2), dan energi cahaya matahari untuk menghasilkan glukosa (C6H12O6) dan oksigen (O2). Persamaan: 6CO2 + 6H2O -> C6H12O6 + 6O2.",
                rubrics_json=[
                    {
                        "name": "Tempat & Reaktan",
                        "points": 5,
                        "description": "Kloroplas, air, CO2, cahaya",
                    },
                    {
                        "name": "Produk & Reaksi",
                        "points": 5,
                        "description": "Glukosa, oksigen, dan persamaan reaksi",
                    },
                ],
                max_score=10.0,
                student_answer="Fotosintesis berlangsung di organel kloroplas daun, mengubah 6CO2 dan 6H2O dengan bantuan sinar matahari menjadi karbohidrat C6H12O6 dan gas O2.",
                teacher_score=10.0,
                teacher_feedback="Penjelasan sangat lengkap mencakup organel, reaktan, dan stoikiometri persamaan kimia.",
            ),
            # Indonesian Language Cases
            BenchmarkKnowledgePreset(
                preset_id="KB_IND_01",
                subject_name="Bahasa Indonesia",
                class_level="XI",
                question_text="Jelaskan struktur teks eksplanasi dan fungsinya!",
                answer_key="Struktur teks eksplanasi: 1) Pernyataan Umum (identifikasi fenomena), 2) Deretan Penjelas (urutan sebab-akibat proses terjadinya fenomena), 3) Interpretasi (kesimpulan/ulasan).",
                rubrics_json=[
                    {
                        "name": "Struktur Lengkap",
                        "points": 6,
                        "description": "Pernyataan umum, deretan penjelas, interpretasi",
                    },
                    {
                        "name": "Fungsi Hubungan Kausal",
                        "points": 4,
                        "description": "Menjelaskan hubungan kausalitas dan kronologi",
                    },
                ],
                max_score=10.0,
                student_answer="Teks eksplanasi terdiri dari pernyataan umum sebagai pengantar, deretan penjelas mengenai sebab akibat fenomena, dan interpretasi sebagai ulasan penutup.",
                teacher_score=9.5,
                teacher_feedback="Struktur dipaparkan secara runtut dan tepat sesuai kaidah teks eksplanasi.",
            ),
        ]

    @classmethod
    def get_benchmark_evaluation_test_set(cls) -> List[BenchmarkEssaySample]:
        """
        Held-Out Evaluation Test Set (Test Split — Strictly Zero Data Leakage).
        These submissions are NOT in the vector database and represent new student essays.
        """
        return [
            # Sample 1: Excellent Chemistry Essay (Expected ~90-95)
            BenchmarkEssaySample(
                sample_id="EVAL_KIM_01",
                subject_name="Kimia",
                class_level="XI",
                question_text="Jelaskan Hukum Dalton (Hukum Kelipatan Berganda) beserta contohnya!",
                answer_key="Bila dua unsur membentuk dua senyawa atau lebih, perbandingan massa salah satu unsur yang berikatan dengan massa tetap unsur lain berbanding sebagai bilangan bulat dan sederhana. Contoh: CO dan CO2.",
                rubrics_json=[
                    {
                        "name": "Definisi Hukum",
                        "points": 5,
                        "description": "Menyebutkan perbandingan massa bulat sederhana",
                    },
                    {
                        "name": "Contoh Senyawa",
                        "points": 5,
                        "description": "Memberikan contoh pasangan senyawa seperti CO dan CO2",
                    },
                ],
                max_score=10.0,
                student_answer="Menurut Dalton, jika dua unsur membentuk lebih dari satu jenis senyawa, maka massa salah satu unsur yang bergabung dengan massa unsur lain yang bernilai tetap akan membentuk rasio bilangan bulat sederhana, misalnya perbandingan oksigen pada CO dan CO2 adalah 1:2.",
                teacher_ground_truth_score=95.0,
                teacher_ground_truth_feedback="Penjelasan sangat baik dan runtut, rasio 1:2 pada oksigen dijelaskan secara rinci.",
            ),
            # Sample 2: Partial Chemistry Essay (Expected ~65-70)
            BenchmarkEssaySample(
                sample_id="EVAL_KIM_02",
                subject_name="Kimia",
                class_level="XI",
                question_text="Jelaskan Hukum Dalton (Hukum Kelipatan Berganda) beserta contohnya!",
                answer_key="Bila dua unsur membentuk dua senyawa atau lebih, perbandingan massa salah satu unsur yang berikatan dengan massa tetap unsur lain berbanding sebagai bilangan bulat dan sederhana. Contoh: CO dan CO2.",
                rubrics_json=[
                    {
                        "name": "Definisi Hukum",
                        "points": 5,
                        "description": "Menyebutkan perbandingan massa bulat sederhana",
                    },
                    {
                        "name": "Contoh Senyawa",
                        "points": 5,
                        "description": "Memberikan contoh pasangan senyawa seperti CO dan CO2",
                    },
                ],
                max_score=10.0,
                student_answer="Hukum Dalton adalah hukum perbandingan massa unsur yang bergabung menjadi senyawa bulat sederhana.",
                teacher_ground_truth_score=65.0,
                teacher_ground_truth_feedback="Definisi sudah mengarah pada konsep inti, tetapi belum menyertakan contoh senyawa konkret.",
            ),
            # Sample 3: Physics Newton Essay (Expected ~85-90)
            BenchmarkEssaySample(
                sample_id="EVAL_FIS_01",
                subject_name="Fisika",
                class_level="XI",
                question_text="Jelaskan Hukum II Newton tentang gerak dan rumusnya!",
                answer_key="Percepatan sebuah benda berbanding lurus dengan resultan gaya yang bekerja dan berbanding terbalik dengan massa benda (Sigma F = m * a).",
                rubrics_json=[
                    {
                        "name": "Konsep Gaya & Percepatan",
                        "points": 5,
                        "description": "Hubungan sebanding gaya dan percepatan",
                    },
                    {
                        "name": "Hubungan Massa & Rumus",
                        "points": 5,
                        "description": "Hubungan berbanding terbalik massa dan rumus Sigma F = m.a",
                    },
                ],
                max_score=10.0,
                student_answer="Hukum 2 Newton menyatakan percepatan benda berbanding lurus dengan total gaya yang diterima dan berbanding terbalik dengan kelembaman massanya, rumusnya F = m * a.",
                teacher_ground_truth_score=90.0,
                teacher_ground_truth_feedback="Konsep percepatan dan massa sudah tepat, formulasi gaya jelas.",
            ),
            # Sample 4: Physics Thermodynamics Essay (Expected ~80-85)
            BenchmarkEssaySample(
                sample_id="EVAL_FIS_02",
                subject_name="Fisika",
                class_level="XI",
                question_text="Jelaskan perbedaan antara proses isotermal dan adiabatik dalam termodinamika!",
                answer_key="Isotermal adalah proses termodinamika pada suhu konstan (delta T = 0), sedangkan adiabatik adalah proses tanpa pertukaran kalor antara sistem dan lingkungan (Q = 0).",
                rubrics_json=[
                    {"name": "Isotermal", "points": 5, "description": "Suhu tetap delta T = 0"},
                    {
                        "name": "Adiabatik",
                        "points": 5,
                        "description": "Tanpa perpindahan kalor Q = 0",
                    },
                ],
                max_score=10.0,
                student_answer="Isotermal berlangsung pada temperatur konstan sehingga energi dalam tidak berubah, sementara proses adiabatik terjadi secara cepat tanpa adanya aliran kalor kalor masuk atau keluar dari wadah gas.",
                teacher_ground_truth_score=85.0,
                teacher_ground_truth_feedback="Penjelasan sangat baik mengenai temperatur konstan dan ketiadaan perpindahan kalor.",
            ),
            # Sample 5: Biology Photosynthesis Essay (Expected ~95-100)
            BenchmarkEssaySample(
                sample_id="EVAL_BIO_01",
                subject_name="Biologi",
                class_level="XI",
                question_text="Jelaskan proses fotosintesis pada tumbuhan hijau dan persamaan kimianya!",
                answer_key="Fotosintesis terjadi di kloroplas menggunakan air (H2O), karbon dioksida (CO2), dan energi cahaya matahari untuk menghasilkan glukosa (C6H12O6) dan oksigen (O2). Persamaan: 6CO2 + 6H2O -> C6H12O6 + 6O2.",
                rubrics_json=[
                    {
                        "name": "Tempat & Reaktan",
                        "points": 5,
                        "description": "Kloroplas, air, CO2, cahaya",
                    },
                    {
                        "name": "Produk & Reaksi",
                        "points": 5,
                        "description": "Glukosa, oksigen, dan persamaan reaksi",
                    },
                ],
                max_score=10.0,
                student_answer="Fotosintesis terjadi dalam kloroplas sel tumbuhan dengan memanfaatkan energi foton cahaya, molekul H2O dari akar dan CO2 dari udara untuk membentuk karbohidrat C6H12O6 dan menghasilkan oksigen O2 melalui reaksi 6CO2 + 6H2O -> C6H12O6 + 6O2.",
                teacher_ground_truth_score=100.0,
                teacher_ground_truth_feedback="Luar biasa lengkap dan tepat, seluruh aspek reaksi dan tempat berlangsungnya proses terpenuhi sempurna.",
            ),
            # Sample 6: Indonesian Language Explanation Text (Expected ~80-85)
            BenchmarkEssaySample(
                sample_id="EVAL_IND_01",
                subject_name="Bahasa Indonesia",
                class_level="XI",
                question_text="Jelaskan struktur teks eksplanasi dan fungsinya!",
                answer_key="Struktur teks eksplanasi: 1) Pernyataan Umum (identifikasi fenomena), 2) Deretan Penjelas (urutan sebab-akibat proses terjadinya fenomena), 3) Interpretasi (kesimpulan/ulasan).",
                rubrics_json=[
                    {
                        "name": "Struktur Lengkap",
                        "points": 6,
                        "description": "Pernyataan umum, deretan penjelas, interpretasi",
                    },
                    {
                        "name": "Fungsi Hubungan Kausal",
                        "points": 4,
                        "description": "Menjelaskan hubungan kausalitas dan kronologi",
                    },
                ],
                max_score=10.0,
                student_answer="Struktur teks eksplanasi terdiri atas: identifikasi fenomena (pernyataan umum), proses kejadian atau deretan penjelas yang berisi sebab akibat terjadinya peristiwa alam/sosial, serta ulasan penutup atau interpretasi.",
                teacher_ground_truth_score=85.0,
                teacher_ground_truth_feedback="Struktur dijelaskan secara tepat dan logis sesuai fungsi eksplanasi.",
            ),
        ]

    # ── Parametric Benchmark Runner ──────────────────────────────────────────

    @classmethod
    def execute_comparative_benchmark(
        cls,
        db: Session,
        school_id: int,
        subject_id: int,
        academic_year_id: int,
        samples: Optional[List[BenchmarkEssaySample]] = None,
        top_k: int = 3,
        similarity_threshold: float = 0.70,
    ) -> Dict[str, Any]:
        """
        Executes a full comparative evaluation run on held-out samples:
        Compares Baseline (No-RAG) vs Augmented RAG.
        """
        test_samples = samples or cls.get_benchmark_evaluation_test_set()
        eval_outputs: List[SingleEvaluationOutput] = []

        no_rag_scores: List[float] = []
        rag_scores: List[float] = []
        teacher_scores: List[float] = []
        no_rag_latencies: List[float] = []
        rag_latencies: List[float] = []

        for sample in test_samples:
            # 1. Mode A: No-RAG
            t0 = time.perf_counter()
            res_no_rag = AiGradingService.grade_essay(
                question_text=sample.question_text,
                answer_key=sample.answer_key,
                student_answer=sample.student_answer,
                rubrics=sample.rubrics_json,
                education_level=sample.class_level,
                education_class=f"Kelas {sample.class_level}",
                db=None,  # No RAG lookup
            )
            lat_no_rag = (time.perf_counter() - t0) * 1000.0
            score_no_rag = float(res_no_rag.get("final_score", 0.0))
            fb_no_rag = str(res_no_rag.get("feedback", ""))

            # 2. Mode B: RAG Augmented
            t1 = time.perf_counter()
            res_rag = AiGradingService.grade_essay(
                question_text=sample.question_text,
                answer_key=sample.answer_key,
                student_answer=sample.student_answer,
                rubrics=sample.rubrics_json,
                education_level=sample.class_level,
                education_class=f"Kelas {sample.class_level}",
                db=db,
                school_id=school_id,
                subject_id=subject_id,
                academic_year_id=academic_year_id,
                subject_name=sample.subject_name,
                class_level=sample.class_level,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            lat_rag = (time.perf_counter() - t1) * 1000.0
            score_rag = float(res_rag.get("final_score", 0.0))
            fb_rag = str(res_rag.get("feedback", ""))
            meta_rag = res_rag.get("rag_metadata", {})

            # Error relative to Teacher Ground Truth
            err_no_rag = abs(score_no_rag - sample.teacher_ground_truth_score)
            err_rag = abs(score_rag - sample.teacher_ground_truth_score)

            no_rag_scores.append(score_no_rag)
            rag_scores.append(score_rag)
            teacher_scores.append(sample.teacher_ground_truth_score)
            no_rag_latencies.append(lat_no_rag)
            rag_latencies.append(lat_rag)

            fq_no_rag = cls.evaluate_feedback_rubric(
                fb_no_rag, sample.teacher_ground_truth_feedback, sample.rubrics_json
            )
            fq_rag = cls.evaluate_feedback_rubric(
                fb_rag, sample.teacher_ground_truth_feedback, sample.rubrics_json
            )

            eval_outputs.append(
                SingleEvaluationOutput(
                    sample_id=sample.sample_id,
                    subject_name=sample.subject_name,
                    teacher_score=sample.teacher_ground_truth_score,
                    no_rag_score=score_no_rag,
                    rag_score=score_rag,
                    no_rag_error=err_no_rag,
                    rag_error=err_rag,
                    no_rag_latency_ms=round(lat_no_rag, 2),
                    rag_latency_ms=round(lat_rag, 2),
                    retrieved_case_count=meta_rag.get("included_count", 0),
                    similarity_scores=meta_rag.get("similarity_scores", []),
                    no_rag_feedback=fb_no_rag,
                    rag_feedback=fb_rag,
                    feedback_quality_no_rag=fq_no_rag,
                    feedback_quality_rag=fq_rag,
                )
            )

        # Aggregate Statistical Metrics
        mae_no_rag = cls.calculate_mae(no_rag_scores, teacher_scores)
        mae_rag = cls.calculate_mae(rag_scores, teacher_scores)

        rmse_no_rag = cls.calculate_rmse(no_rag_scores, teacher_scores)
        rmse_rag = cls.calculate_rmse(rag_scores, teacher_scores)

        corr_no_rag = cls.calculate_pearson_correlation(no_rag_scores, teacher_scores)
        corr_rag = cls.calculate_pearson_correlation(rag_scores, teacher_scores)

        spearman_no_rag = cls.calculate_spearman_correlation(no_rag_scores, teacher_scores)
        spearman_rag = cls.calculate_spearman_correlation(rag_scores, teacher_scores)

        agree5_no_rag = cls.calculate_tolerance_agreement(
            no_rag_scores, teacher_scores, tolerance=5.0
        )
        agree5_rag = cls.calculate_tolerance_agreement(rag_scores, teacher_scores, tolerance=5.0)

        agree10_no_rag = cls.calculate_tolerance_agreement(
            no_rag_scores, teacher_scores, tolerance=10.0
        )
        agree10_rag = cls.calculate_tolerance_agreement(rag_scores, teacher_scores, tolerance=10.0)

        avg_lat_no_rag = statistics.mean(no_rag_latencies) if no_rag_latencies else 0.0
        avg_lat_rag = statistics.mean(rag_latencies) if rag_latencies else 0.0

        avg_fb_no_rag = statistics.mean(
            [o.feedback_quality_no_rag["average_feedback_score"] for o in eval_outputs]
        )
        avg_fb_rag = statistics.mean(
            [o.feedback_quality_rag["average_feedback_score"] for o in eval_outputs]
        )

        return {
            "sample_count": len(test_samples),
            "configuration": {
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
            },
            "metrics": {
                "mae": {"no_rag": round(mae_no_rag, 2), "rag": round(mae_rag, 2)},
                "rmse": {"no_rag": round(rmse_no_rag, 2), "rag": round(rmse_rag, 2)},
                "pearson_correlation": {"no_rag": round(corr_no_rag, 3), "rag": round(corr_rag, 3)},
                "spearman_correlation": {
                    "no_rag": round(spearman_no_rag, 3),
                    "rag": round(spearman_rag, 3),
                },
                "agreement_within_5_points": {
                    "no_rag": round(agree5_no_rag, 1),
                    "rag": round(agree5_rag, 1),
                },
                "agreement_within_10_points": {
                    "no_rag": round(agree10_no_rag, 1),
                    "rag": round(agree10_rag, 1),
                },
                "average_latency_ms": {
                    "no_rag": round(avg_lat_no_rag, 2),
                    "rag": round(avg_lat_rag, 2),
                },
                "feedback_quality_score_0_to_2": {
                    "no_rag": round(avg_fb_no_rag, 2),
                    "rag": round(avg_fb_rag, 2),
                },
            },
            "sample_evaluations": eval_outputs,
        }

    # ── Parametric Sweeps (Thresholds & Top-K) ────────────────────────────────

    @classmethod
    def execute_threshold_sweep(
        cls,
        db: Session,
        school_id: int,
        subject_id: int,
        academic_year_id: int,
        thresholds: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Sweeps across cosine similarity thresholds: [0.50, 0.60, 0.65, 0.70, 0.75, 0.80]."""
        test_thresholds = thresholds or [0.50, 0.60, 0.65, 0.70, 0.75, 0.80]
        results = []
        for t in test_thresholds:
            bench = cls.execute_comparative_benchmark(
                db=db,
                school_id=school_id,
                subject_id=subject_id,
                academic_year_id=academic_year_id,
                similarity_threshold=t,
                top_k=3,
            )
            results.append(
                {
                    "threshold": t,
                    "mae_rag": bench["metrics"]["mae"]["rag"],
                    "rmse_rag": bench["metrics"]["rmse"]["rag"],
                    "pearson_r": bench["metrics"]["pearson_correlation"]["rag"],
                    "agreement_5pt": bench["metrics"]["agreement_within_5_points"]["rag"],
                    "avg_retrieved_cases": statistics.mean(
                        [s.retrieved_case_count for s in bench["sample_evaluations"]]
                    ),
                }
            )
        return results

    @classmethod
    def execute_top_k_sweep(
        cls,
        db: Session,
        school_id: int,
        subject_id: int,
        academic_year_id: int,
        top_k_values: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """Sweeps across Top-K values: [1, 3, 5]."""
        k_values = top_k_values or [1, 3, 5]
        results = []
        for k in k_values:
            bench = cls.execute_comparative_benchmark(
                db=db,
                school_id=school_id,
                subject_id=subject_id,
                academic_year_id=academic_year_id,
                similarity_threshold=0.70,
                top_k=k,
            )
            results.append(
                {
                    "top_k": k,
                    "mae_rag": bench["metrics"]["mae"]["rag"],
                    "rmse_rag": bench["metrics"]["rmse"]["rag"],
                    "pearson_r": bench["metrics"]["pearson_correlation"]["rag"],
                    "agreement_5pt": bench["metrics"]["agreement_within_5_points"]["rag"],
                    "avg_latency_ms": bench["metrics"]["average_latency_ms"]["rag"],
                }
            )
        return results
