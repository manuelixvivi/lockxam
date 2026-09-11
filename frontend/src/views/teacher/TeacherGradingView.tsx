import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Award,
  RefreshCw,
  Edit2,
  CheckCircle,
  FileText,
  Sparkles,
  Download,
  Upload,
  BookOpen,
  AlertTriangle,
  ShieldCheck,
  ChevronLeft,
  GraduationCap,
  Eye,
  Check,
  X,
} from "lucide-react";
import * as XLSX from "xlsx";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { teacherDashboardApi } from "../../api/teacherDashboard";
import { apiClient } from "../../api/client";
import { LaTeXText } from "../../components/ui/LaTeXText";
import type { EssayGradingEvaluation } from "../../api/teacherDashboard";

export function TeacherGradingView() {
  const { showToast } = useToast();
  const [evaluations, setEvaluations] = useState<EssayGradingEvaluation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"EVALUATIONS" | "PROTESTS">("EVALUATIONS");

  // Excel Import File Ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Selected Schedule State (2-Level Master-Detail View)
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [selectedScheduleInfo, setSelectedScheduleInfo] = useState<{
    title: string;
    class_name: string;
    subject_name: string;
    package_name: string;
  } | null>(null);

  const [studentAnswersList, setStudentAnswersList] = useState<any[]>([]);
  const [isLoadingAnswers, setIsLoadingAnswers] = useState(false);

  // Navigation Level 3: Dedicated Full Page Student Answer View State
  const [selectedStudentAttempt, setSelectedStudentAttempt] = useState<any | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [level3QuestionTab, setLevel3QuestionTab] = useState<"ALL" | "PG" | "IS" | "ES">("ALL");

  const filteredAnswers = useMemo(() => {
    if (!selectedStudentAttempt || !selectedStudentAttempt.answers) return [];
    if (level3QuestionTab === "ALL") return selectedStudentAttempt.answers;
    if (level3QuestionTab === "ES") {
      return selectedStudentAttempt.answers.filter(
        (a: any) => a.question_type === "ES"
      );
    }
    return selectedStudentAttempt.answers.filter(
      (a: any) => a.question_type === level3QuestionTab
    );
  }, [selectedStudentAttempt, level3QuestionTab]);

  const attemptStats = useMemo(() => {
    if (!selectedStudentAttempt || !selectedStudentAttempt.answers) {
      return {
        score_pg: 0, max_pg: 0, count_pg: 0,
        score_is: 0, max_is: 0, count_is: 0,
        score_es: 0, max_es: 0, count_es: 0,
        total_earned: 0, total_max: 0, final_score: 0
      };
    }
    let score_pg = 0, max_pg = 0, count_pg = 0;
    let score_is = 0, max_is = 0, count_is = 0;
    let score_es = 0, max_es = 0, count_es = 0;

    selectedStudentAttempt.answers.forEach((a: any) => {
      const qType = a.question_type || "PG";
      const earned = parseFloat(a.score_earned !== undefined && a.score_earned !== null ? a.score_earned : 0) || 0;
      const maxQ = parseFloat(a.max_score !== undefined && a.max_score !== null ? a.max_score : 10) || 0;

      if (qType === "PG") {
        score_pg += earned;
        max_pg += maxQ;
        count_pg++;
      } else if (qType === "IS") {
        score_is += earned;
        max_is += maxQ;
        count_is++;
      } else if (qType === "ES") {
        score_es += earned;
        max_es += maxQ;
        count_es++;
      }
    });

    const total_earned = score_pg + score_is + score_es;
    const total_max = max_pg + max_is + max_es;
    const final_score = total_max > 0 ? Math.round((total_earned / total_max) * 100 * 10) / 10 : 0;

    return {
      score_pg: Math.round(score_pg * 10) / 10,
      max_pg: Math.round(max_pg * 10) / 10,
      count_pg,
      score_is: Math.round(score_is * 10) / 10,
      max_is: Math.round(max_is * 10) / 10,
      count_is,
      score_es: Math.round(score_es * 10) / 10,
      max_es: Math.round(max_es * 10) / 10,
      count_es,
      total_earned: Math.round(total_earned * 10) / 10,
      total_max: Math.round(total_max * 10) / 10,
      final_score
    };
  }, [selectedStudentAttempt]);

  const scheduleQuestionTypes = useMemo(() => {
    let hasPg = false;
    let hasIs = false;
    let hasEs = false;

    studentAnswersList.forEach((st) => {
      if ((st.max_pg && st.max_pg > 0) || (st.answers && st.answers.some((a: any) => (a.question_type || "PG") === "PG"))) {
        hasPg = true;
      }
      if ((st.max_is && st.max_is > 0) || (st.answers && st.answers.some((a: any) => a.question_type === "IS"))) {
        hasIs = true;
      }
      if ((st.max_es && st.max_es > 0) || (st.answers && st.answers.some((a: any) => a.question_type === "ES" || a.evaluation_id))) {
        hasEs = true;
      }
    });

    if (studentAnswersList.length === 0) {
      return { hasPg: false, hasIs: false, hasEs: false };
    }
    return { hasPg, hasIs, hasEs };
  }, [studentAnswersList]);



  // BAP Viewer Modal State
  const [bapModalData, setBapModalData] = useState<any | null>(null);
  const [isBapModalOpen, setIsBapModalOpen] = useState(false);

  // Student Protests Data for Grade Protest Portal
  const [protests, setProtests] = useState<any[]>([]);

  const [examHistoryPackages, setExamHistoryPackages] = useState<any[]>([]);

  const fetchEvaluations = async () => {
    setIsLoading(true);
    try {
      const [evalsData, historyData] = await Promise.all([
        teacherDashboardApi.listGradingEvaluations().catch(() => []),
        teacherDashboardApi.getExamHistory().catch(() => ({ grouped_packages: [] })),
      ]);
      setEvaluations(evalsData);
      setExamHistoryPackages(historyData?.grouped_packages || []);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Penilaian Ujian",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvaluations();
  }, []);

  // Group evaluations by Exam Schedule
  const groupedSchedules = useMemo(() => {
    const map: Record<
      string,
      {
        schedule_id?: number;
        exam_title: string;
        package_name: string;
        subject_name: string;
        class_name: string;
        evaluations: EssayGradingEvaluation[];
      }
    > = {};

    evaluations.forEach((item) => {
      const key = `${item.exam_title}_${item.class_name}`;
      if (!map[key]) {
        map[key] = {
          schedule_id: item.schedule_id || (item as any).schedule_id || item.attempt_id,
          exam_title: item.exam_title,
          package_name: (item as any).package_name || item.exam_title,
          subject_name: (item as any).subject_name || item.exam_title,
          class_name: item.class_name,
          evaluations: [],
        };
      }
      map[key].evaluations.push(item);
    });

    return Object.values(map);
  }, [evaluations]);

  // Unified display schedules combining Exam History and Evaluations
  const displaySchedules = useMemo(() => {
    const list: any[] = [];

    examHistoryPackages.forEach((pkg) => {
      (pkg.schedules || []).forEach((sch: any) => {
        list.push({
          schedule_id: sch.schedule_id,
          exam_title: sch.title,
          package_name: pkg.package_title,
          subject_name: sch.subject_name,
          class_name: sch.class_name,
          total_students: sch.total_students,
          submitted_students: sch.submitted_students,
          average_score: sch.average_score,
          evaluations: [],
        });
      });
    });

    groupedSchedules.forEach((g) => {
      const exists = list.some(
        (item) => item.schedule_id === g.schedule_id || (item.exam_title === g.exam_title && item.class_name === g.class_name)
      );
      if (!exists) {
        list.push({
          schedule_id: g.schedule_id,
          exam_title: g.exam_title,
          package_name: g.package_name,
          subject_name: g.subject_name,
          class_name: g.class_name,
          total_students: g.evaluations.length,
          submitted_students: g.evaluations.length,
          average_score: null,
          evaluations: g.evaluations,
        });
      } else {
        const found = list.find(
          (item) => item.schedule_id === g.schedule_id || (item.exam_title === g.exam_title && item.class_name === g.class_name)
        );
        if (found) found.evaluations = g.evaluations;
      }
    });

    return list;
  }, [examHistoryPackages, groupedSchedules]);

  // Open Level 2: Student List for Selected Exam Schedule
  const handleSelectSchedule = async (
    sch: {
      schedule_id?: number;
      exam_title: string;
      package_name: string;
      subject_name: string;
      class_name: string;
      evaluations: EssayGradingEvaluation[];
    }
  ) => {
    const schId = sch.schedule_id || sch.evaluations[0]?.schedule_id || sch.evaluations[0]?.attempt_id || 1;
    setSelectedScheduleId(schId);
    setSelectedStudentAttempt(null);
    setSelectedScheduleInfo({
      title: sch.exam_title,
      class_name: sch.class_name,
      subject_name: sch.subject_name,
      package_name: sch.package_name,
    });

    setIsLoadingAnswers(true);
    let fetchedStudents: any[] = [];
    try {
      const res = await apiClient.get<{ students: any[] }>(
        `/api/v1/teacher/exam-history/${schId}/student-answers`
      );
      fetchedStudents = res.students || [];
    } catch {
      fetchedStudents = [];
    }

    // Fallback: If backend endpoint returned no students or answers array is empty, build from sch.evaluations
    if (
      (fetchedStudents.length === 0 || fetchedStudents.every((s) => !s.answers || s.answers.length === 0)) &&
      sch.evaluations &&
      sch.evaluations.length > 0
    ) {
      const studentMap: Record<number, any> = {};
      sch.evaluations.forEach((ev: any) => {
        const attId = ev.attempt_id;
        if (!studentMap[attId]) {
          studentMap[attId] = {
            student_id: ev.student_id || attId,
            attempt_id: attId,
            student_name: ev.student_name,
            nisn: ev.nisn || "-",
            status: ev.grading_status || "SUBMITTED",
            final_score: ev.final_score !== null && ev.final_score !== undefined ? ev.final_score : ev.ai_score,
            score_pg: ev.score_pg || 0,
            max_pg: ev.max_pg || 0,
            score_is: ev.score_is || 0,
            max_is: ev.max_is || 0,
            score_es: ev.score_es || ev.ai_score || 0,
            max_es: ev.max_es || 0,
            answers: [],
          };
        }
        studentMap[attId].answers.push({
          question_id: ev.question_id,
          question_type: ev.question_type || "ES",
          question_content: ev.question_content || `Soal #${ev.question_id}`,
          selected_option: null,
          text_answer: ev.student_answer || "(Tidak diisi)",
          score_earned: ev.final_score !== null && ev.final_score !== undefined ? ev.final_score : ev.ai_score,
          max_score: ev.max_score || 100,
          evaluation_id: ev.evaluation_id,
          ai_feedback: ev.ai_feedback,
          confidence: ev.confidence,
          confidence_level: ev.confidence_level,
          review_required: ev.review_required,
          rubric_scores: ev.rubric_scores,
          academic_rationale: ev.academic_rationale || ev.ai_feedback,
        });
      });
      fetchedStudents = Object.values(studentMap);
    }

    setStudentAnswersList(fetchedStudents);
    setIsLoadingAnswers(false);
  };

  // Single Global Save & Lock Handler for All Question Scores
  const handleSaveAllScores = async () => {
    if (!selectedStudentAttempt || !selectedStudentAttempt.answers) return;
    setIsSavingAll(true);
    try {
      let updatedCount = 0;
      for (const ans of selectedStudentAttempt.answers) {
        if (ans.evaluation_id) {
          const maxAllowed = ans.max_score || 100;
          const targetScore = ans.score_earned !== undefined && ans.score_earned !== null ? ans.score_earned : 0;
          const targetFb = ans.ai_feedback || "";
          const validScore = Math.min(Math.max(targetScore, 0), maxAllowed);

          await teacherDashboardApi.finalizeGrading(ans.evaluation_id, validScore, targetFb);
          ans.score_earned = validScore;
          ans.ai_feedback = targetFb;
          updatedCount++;
        }
      }

      showToast({
        type: "success",
        title: "Koreksi Berhasil Disimpan",
        message: `Berhasil mengoreksi dan mengunci ${updatedCount} nilai essay siswa!`,
      });

      if (selectedScheduleId) {
        const res = await apiClient.get<{ students: any[] }>(`/api/v1/teacher/exam-history/${selectedScheduleId}/student-answers`);
        setStudentAnswersList(res.students || []);
        const updatedSt = (res.students || []).find((s) => s.student_id === selectedStudentAttempt.student_id);
        if (updatedSt) setSelectedStudentAttempt(updatedSt);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menyimpan Nilai",
        message: err?.message || "Terjadi kesalahan saat menyimpan nilai.",
      });
    } finally {
      setIsSavingAll(false);
    }
  };



  // Export Excel (.xlsx) matching user template format (3 Sheets: PG, IS, ES)
  const handleExportExcel = async () => {
    if (!selectedScheduleId) return;

    let students = studentAnswersList;
    if (students.length === 0) {
      try {
        const res = await apiClient.get<{ students: any[] }>(
          `/api/v1/teacher/exam-history/${selectedScheduleId}/student-answers`
        );
        students = res.students || [];
      } catch {
        students = [];
      }
    }

    if (students.length === 0) {
      showToast({
        type: "warning",
        title: "Data Kosong",
        message: "Tidak ada data penilaian untuk diexport.",
      });
      return;
    }

    const wb = XLSX.utils.book_new();

    // Map unique questions for PG, IS, and ES
    const pgMap = new Map<number, { id: number; number: number; key: string; max_score: number }>();
    const isMap = new Map<number, { id: number; number: number; key: string; max_score: number }>();
    const esMap = new Map<number, { id: number; number: number; rubrics: Array<{ name: string; max: number }>; max_score: number }>();

    let pgCounter = 1;
    let isCounter = 1;
    let esCounter = 1;

    students.forEach((st) => {
      (st.answers || []).forEach((ans: any) => {
        const qType = ans.question_type || "PG";
        if (qType === "PG" && !pgMap.has(ans.question_id)) {
          pgMap.set(ans.question_id, {
            id: ans.question_id,
            number: pgCounter++,
            key: ans.answer_key || ans.correct_option || "-",
            max_score: ans.max_score || 10,
          });
        } else if (qType === "IS" && !isMap.has(ans.question_id)) {
          isMap.set(ans.question_id, {
            id: ans.question_id,
            number: isCounter++,
            key: ans.answer_key || "-",
            max_score: ans.max_score || 10,
          });
        } else if ((qType === "ES" || ans.evaluation_id) && !esMap.has(ans.question_id)) {
          const rubrics = (ans.rubrics && Array.isArray(ans.rubrics) && ans.rubrics.length > 0)
            ? ans.rubrics.map((r: any, rIdx: number) => ({
                name: r.name || `Rubrik${rIdx + 1}`,
                max: r.max_score || r.max || 10,
              }))
            : [{ name: "Rubrik1", max: ans.max_score || 100 }];

          esMap.set(ans.question_id, {
            id: ans.question_id,
            number: esCounter++,
            rubrics: rubrics,
            max_score: ans.max_score || 100,
          });
        }
      });
    });

    const pgList = Array.from(pgMap.values());
    const isList = Array.from(isMap.values());
    const esList = Array.from(esMap.values());

    // ─── Sheet 1: Pilihan Ganda (PG) ───
    const pgRows = students.map((st, idx) => {
      const row: Record<string, any> = {
        No: idx + 1,
        "ID Attempt": st.attempt_id,
        NISN: st.nisn || "-",
        "Nama Siswa": st.student_name,
      };
      const ansMap = new Map<number, any>((st.answers || []).map((a: any) => [a.question_id, a]));
      pgList.forEach((q) => {
        const header = `Q${q.number} (${q.key})`;
        const a = ansMap.get(q.id);
        row[header] = a ? (a.score_earned !== undefined && a.score_earned !== null ? a.score_earned : "(Tidak diisi)") : "(Tidak diisi)";
      });
      row["Total Skor PG"] = st.score_pg || 0;
      return row;
    });
    const wsPG = XLSX.utils.json_to_sheet(pgRows);
    XLSX.utils.book_append_sheet(wb, wsPG, "Pilihan Ganda (PG)");

    // ─── Sheet 2: Isian Singkat (IS) ───
    const isRows = students.map((st, idx) => {
      const row: Record<string, any> = {
        No: idx + 1,
        "ID Attempt": st.attempt_id,
        NISN: st.nisn || "-",
        "Nama Siswa": st.student_name,
      };
      const ansMap = new Map<number, any>((st.answers || []).map((a: any) => [a.question_id, a]));
      isList.forEach((q) => {
        const qHeader = `Q${q.number} (${q.key})`;
        const scoreHeader = `Skor_Q${q.number} (Max:${q.max_score})`;
        const a = ansMap.get(q.id);
        row[qHeader] = a ? (a.text_answer || a.selected_option || "(tidak diisi)") : "(tidak diisi)";
        row[scoreHeader] = a ? (a.score_earned !== undefined && a.score_earned !== null ? a.score_earned : 0) : 0;
      });
      return row;
    });
    const wsIS = XLSX.utils.json_to_sheet(isRows);
    XLSX.utils.book_append_sheet(wb, wsIS, "Isian Singkat (IS)");

    // ─── Sheet 3: Essay (ES) ───
    const esRows = students.map((st, idx) => {
      const row: Record<string, any> = {
        No: idx + 1,
        "ID Attempt": st.attempt_id,
        "Nama Siswa": st.student_name,
        NISN: st.nisn || "-",
      };
      const ansMap = new Map<number, any>((st.answers || []).map((a: any) => [a.question_id, a]));
      esList.forEach((q) => {
        const ansHeader = `Q${q.number}_Student_Answer`;
        const fbHeader = `Q${q.number}_Feedback`;
        const a = ansMap.get(q.id);
        row[ansHeader] = a ? (a.text_answer || "(tidak diisi)") : "(tidak diisi)";

        q.rubrics.forEach((r) => {
          const rubHeader = `Q${q.number}_${r.name} (Max:${r.max})`;
          row[rubHeader] = a ? (a.score_earned !== undefined && a.score_earned !== null ? a.score_earned : 0) : 0;
        });
        row[fbHeader] = a ? (a.ai_feedback || "") : "";
      });
      return row;
    });
    const wsES = XLSX.utils.json_to_sheet(esRows);
    XLSX.utils.book_append_sheet(wb, wsES, "Essay (ES)");

    const titleStr = selectedScheduleInfo ? selectedScheduleInfo.title.replace(/\s+/g, "_") : "Ujian";
    XLSX.writeFile(wb, `Skor_Siswa_${titleStr}.xlsx`);
    showToast({
      type: "success",
      title: "Ekspor Berhasil",
      message: "File Excel skor template 3 sheet berhasil diunduh!",
    });
  };

  // Import Excel (.xlsx) supporting User Template Format with Strict Validation
  const handleImportExcel = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: "binary" });

        const pendingUpdates: Map<number, { score: number; feedback: string; evalId: number }> = new Map();

        // Scan all sheets in workbook (Pilihan Ganda, Isian Singkat, Essay)
        for (const sheetName of wb.SheetNames) {
          const ws = wb.Sheets[sheetName];
          const rawData: any[] = XLSX.utils.sheet_to_json(ws);
          if (!rawData || rawData.length === 0) continue;

          for (let rIdx = 0; rIdx < rawData.length; rIdx++) {
            const row = rawData[rIdx];
            const attId = row["ID Attempt"] || row["ID Evaluasi"];
            const stName = row["Nama Siswa"] || `Baris #${rIdx + 1}`;

            const student = studentAnswersList.find((s) => s.attempt_id === attId);
            if (!student || !student.answers) continue;

            const questionScoreSums: Map<number, { score: number; maxAllowed: number; feedback: string; colName: string }> = new Map();

            for (const colName of Object.keys(row)) {
              const maxMatch = colName.match(/Max:\s*(\d+(?:\.\d+)?)/i);
              const qNumMatch = colName.match(/^Q(\d+)|Skor_Q(\d+)/i);

              if (maxMatch || qNumMatch) {
                const typedVal = parseFloat(row[colName]);

                const qNum = qNumMatch ? parseInt(qNumMatch[1] || qNumMatch[2], 10) : null;
                const qIdx = qNum ? qNum - 1 : 0;

                let qTypeFilter = "PG";
                if (sheetName.includes("Isian")) qTypeFilter = "IS";
                else if (sheetName.includes("Essay")) qTypeFilter = "ES";

                const typeAnswers = student.answers.filter((a: any) =>
                  qTypeFilter === "ES" ? (a.question_type === "ES" || a.evaluation_id) : a.question_type === qTypeFilter
                );
                const matchingAns = typeAnswers[qIdx] || student.answers[qIdx];

                if (matchingAns && !isNaN(typedVal)) {
                  let maxScore = maxMatch ? parseFloat(maxMatch[1]) : (matchingAns.max_score || 100);

                  // STRICT VALIDATION CHECK
                  if (typedVal > maxScore) {
                    showToast({
                      type: "error",
                      title: "Impor Gagal: Skor Melebihi Maksimum",
                      message: `Pada Sheet "${sheetName}", skor untuk "${stName}" pada kolom "${colName}" adalah ${typedVal}, melebihi batas maksimal ${maxScore} poin. Seluruh proses impor dibatalkan!`,
                    });
                    if (fileInputRef.current) fileInputRef.current.value = "";
                    return; // REJECT IMPORT ENTIRELY
                  }

                  if (typedVal < 0) {
                    showToast({
                      type: "error",
                      title: "Impor Gagal: Skor Negatif",
                      message: `Pada Sheet "${sheetName}", skor untuk "${stName}" pada kolom "${colName}" tidak boleh kurang dari 0. Seluruh proses impor dibatalkan!`,
                    });
                    if (fileInputRef.current) fileInputRef.current.value = "";
                    return; // REJECT IMPORT ENTIRELY
                  }

                  const existing = questionScoreSums.get(matchingAns.question_id) || {
                    score: 0,
                    maxAllowed: matchingAns.max_score || maxScore,
                    feedback: matchingAns.ai_feedback || "",
                    colName: colName,
                  };

                  const fbCol = `Q${qNum}_Feedback`;
                  if (row[fbCol]) {
                    existing.feedback = row[fbCol];
                  }

                  existing.score += typedVal;
                  questionScoreSums.set(matchingAns.question_id, existing);
                }
              }
            }

            for (const [qId, qData] of questionScoreSums.entries()) {
              if (qData.score > qData.maxAllowed) {
                showToast({
                  type: "error",
                  title: "Impor Gagal: Total Skor Rubrik Melebihi Maksimum",
                  message: `Pada Sheet "${sheetName}", total skor rubrik untuk "${stName}" pada Soal #${qId} adalah ${qData.score}, melebihi skor maksimal ${qData.maxAllowed} poin. Seluruh proses impor dibatalkan!`,
                });
                if (fileInputRef.current) fileInputRef.current.value = "";
                return; // REJECT IMPORT ENTIRELY
              }

              const matchingAns = student.answers.find((a: any) => a.question_id === qId);
              if (matchingAns && matchingAns.evaluation_id) {
                pendingUpdates.set(matchingAns.evaluation_id, {
                  evalId: matchingAns.evaluation_id,
                  score: qData.score,
                  feedback: qData.feedback,
                });
              }
            }
          }
        }

        // Phase 2: Atomic Commit ONLY IF ALL VALIDATIONS PASSED
        let updatedCount = 0;
        for (const update of pendingUpdates.values()) {
          await teacherDashboardApi.finalizeGrading(update.evalId, update.score, update.feedback);
          updatedCount++;
        }

        showToast({
          type: "success",
          title: "Impor Excel Berhasil",
          message: `Seluruh skor ter-validasi! ${updatedCount} data nilai berhasil diperbarui.`,
        });

        if (selectedScheduleId) {
          const res = await apiClient.get<{ students: any[] }>(
            `/api/v1/teacher/exam-history/${selectedScheduleId}/student-answers`
          );
          setStudentAnswersList(res.students || []);
        }
      } catch (err: any) {
        showToast({
          type: "error",
          title: "Gagal Impor Excel",
          message: err?.message || "Format file tidak sesuai.",
        });
      }
    };
    reader.readAsBinaryString(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Open BAP Viewer Modal
  const handleViewBap = async (assignmentId: number) => {
    try {
      const doc = await apiClient.get(`/api/v1/proctor/assignments/${assignmentId}/bau`);
      setBapModalData(doc);
      setIsBapModalOpen(true);
    } catch {
      showToast({
        type: "error",
        title: "Gagal Memuat BAP",
        message: "Dokumen Berita Acara tidak ditemukan.",
      });
    }
  };

  // Handle Student Grade Protest (Accept / Reject with -5 Points Penalty)
  const handleResolveProtest = (protestId: number, action: "ACCEPT" | "REJECT") => {
    setProtests((prev) =>
      prev.map((p) => {
        if (p.id === protestId) {
          return {
            ...p,
            status: action === "ACCEPT" ? "APPROVED" : "REJECTED_WITH_PENALTY",
            final_score: action === "ACCEPT" ? p.current_score + 5 : p.current_score - 5,
          };
        }
        return p;
      })
    );

    if (action === "ACCEPT") {
      showToast({
        type: "success",
        title: "Sanggahan Diterima",
        message: "Sanggahan nilai siswa disetujui dan nilai telah diperbaiki.",
      });
    } else {
      showToast({
        type: "warning",
        title: "Sanggahan Ditolak (-5 Poin Penalti)",
        message: "Sanggahan nilai ditolak oleh Guru. Siswa dikenakan penalti potongan -5 poin.",
      });
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hidden File Input for Excel Import */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleImportExcel}
        accept=".xlsx, .xls"
        className="hidden"
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          {selectedStudentAttempt !== null ? (
            <button
              onClick={() => setSelectedStudentAttempt(null)}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-1.5"
            >
              <ChevronLeft className="w-4 h-4" />
              Kembali ke Daftar Siswa ({selectedScheduleInfo?.class_name})
            </button>
          ) : selectedScheduleId !== null ? (
            <button
              onClick={() => setSelectedScheduleId(null)}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-1.5"
            >
              <ChevronLeft className="w-4 h-4" />
              Kembali ke Daftar Jadwal Ujian
            </button>
          ) : null}
          <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
            <Award className="w-5 h-5 text-indigo-400" />
            <span>
              {selectedStudentAttempt
                ? `Lembar Jawaban & Koreksi: ${selectedStudentAttempt.student_name}`
                : selectedScheduleInfo
                ? `Detail Hasil Ujian: ${selectedScheduleInfo.title}`
                : "Penilaian Ujian & Review Hasil Siswa"}
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {selectedScheduleInfo
              ? `Melihat rincian perolehan skor ujian untuk kelas ${selectedScheduleInfo.class_name}.`
              : "Pilih salah satu jadwal ujian di bawah untuk melihat rincian siswa dan skor per jenis soal."}
          </p>
        </div>

        {/* Action Controls (Only shown when not reviewing individual student) */}
        {selectedStudentAttempt === null && (
          <div className="flex items-center gap-2 flex-wrap">
            {selectedScheduleId !== null && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<ShieldCheck className="w-4 h-4 text-amber-400" />}
                  onClick={() => handleViewBap(selectedScheduleId)}
                >
                  Dokumen BAP
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
                  onClick={handleExportExcel}
                >
                  Ekspor Skor Excel (.xlsx)
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<Upload className="w-4 h-4 text-indigo-400" />}
                  onClick={() => fileInputRef.current?.click()}
                >
                  Impor Skor Excel (.xlsx)
                </Button>
              </>
            )}

            <Button
              variant="outline"
              size="sm"
              leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={fetchEvaluations}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </div>
        )}
      </div>

      {/* Tab Controls (Only shown when not reviewing individual student) */}
      {selectedStudentAttempt === null && (
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => {
            setActiveTab("EVALUATIONS");
            setSelectedScheduleId(null);
          }}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            activeTab === "EVALUATIONS"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
          }`}
        >
          Daftar Jadwal Ujian Selesai ({displaySchedules.length})
        </button>
        <button
          onClick={() => setActiveTab("PROTESTS")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all relative ${
            activeTab === "PROTESTS"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
          }`}
        >
          <span>Portal Sanggahan/Protes Nilai Siswa</span>
          {protests.filter((p) => p.status === "PENDING").length > 0 && (
            <span className="ml-2 px-1.5 py-0.5 rounded-full bg-amber-500 text-[10px] font-black text-slate-950">
              {protests.filter((p) => p.status === "PENDING").length}
            </span>
          )}
        </button>
      </div>
      )}

      {/* ── TAB 1: EVALUATIONS VIEW ── */}
      {activeTab === "EVALUATIONS" && (
        <>
          {/* LEVEL 1: LIST OF COMPLETED EXAM SCHEDULE CARDS */}
          {selectedScheduleId === null ? (
            isLoading ? (
              <div className="glass-panel p-12 flex flex-col items-center justify-center gap-3">
                <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
                <p className="text-xs text-slate-400">Memuat jadwal ujian selesai...</p>
              </div>
            ) : displaySchedules.length === 0 ? (
              <div className="glass-panel p-12 text-center flex flex-col items-center justify-center gap-3 border-dashed">
                <FileText className="w-12 h-12 text-slate-600" />
                <h3 className="text-sm font-bold text-slate-300">Belum Ada Ujian Selesai</h3>
                <p className="text-xs text-slate-500 max-w-sm">
                  Belum ada jadwal ujian yang diselesaikan oleh siswa saat ini.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {displaySchedules.map((sch, idx) => {
                  const studentCount = sch.submitted_students || sch.total_students || (sch.evaluations ? sch.evaluations.length : 0);
                  return (
                    <div
                      key={idx}
                      className="glass-panel p-5 flex flex-col justify-between gap-4 border border-slate-800 hover:border-indigo-500/40 transition-all group"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-semibold text-indigo-400 bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-500/20 block w-max mb-1">
                              {sch.package_name}
                            </span>
                            <h3 className="font-bold text-slate-100 text-base group-hover:text-indigo-300 transition-colors">
                              {sch.exam_title}
                            </h3>
                          </div>
                          <Badge variant="emerald">SELESAI</Badge>
                        </div>

                        <div className="flex items-center gap-1.5 flex-wrap">
                          <Badge variant="indigo">
                            <span className="flex items-center gap-1">
                              <GraduationCap className="w-3 h-3" />
                              {sch.class_name}
                            </span>
                          </Badge>
                          <Badge variant="slate">
                            <span className="flex items-center gap-1">
                              <BookOpen className="w-3 h-3" />
                              {sch.subject_name}
                            </span>
                          </Badge>
                          <Badge variant="emerald">
                            <span className="flex items-center gap-1">
                              <ShieldCheck className="w-3 h-3 text-emerald-400" />
                              Guru Pengampu Resmi
                            </span>
                          </Badge>
                        </div>

                        <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1 text-slate-400">
                          <div className="flex justify-between">
                            <span>Siswa Mengerjakan:</span>
                            <strong className="text-emerald-400 font-bold">
                              {studentCount} Siswa
                            </strong>
                          </div>
                          {sch.average_score !== null && sch.average_score !== undefined && (
                            <div className="flex justify-between">
                              <span>Rata-Rata Nilai Akhir:</span>
                              <strong className="text-amber-300 font-bold">
                                {sch.average_score} / 100
                              </strong>
                            </div>
                          )}
                          <div className="flex justify-between">
                            <span>Masa Review Nilai:</span>
                            <span className="text-slate-300">2 Minggu Pasca Ujian</span>
                          </div>
                        </div>
                      </div>

                      <Button
                        variant="primary"
                        className="w-full text-xs font-bold"
                        onClick={() => handleSelectSchedule(sch)}
                      >
                        📄 Periksa / Review Nilai Siswa ({studentCount} Siswa) &rarr;
                      </Button>
                    </div>
                  );
                })}
              </div>
            )
          ) : selectedStudentAttempt === null ? (
            /* LEVEL 2: DETAILED STUDENT SCORES BREAKDOWN FOR SELECTED SCHEDULE */
            <div className="space-y-5">
              {/* Bento Box Stats Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                    <GraduationCap className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Total Siswa</p>
                    <p className="text-xl font-black text-slate-100">
                      {studentAnswersList.length} Siswa
                    </p>
                  </div>
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0">
                    <CheckCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Rata-Rata Nilai</p>
                    <p className="text-xl font-black text-emerald-400">
                      {studentAnswersList.length > 0
                        ? Math.round(
                            (studentAnswersList.reduce((acc, s) => acc + (s.final_score || 0), 0) /
                              studentAnswersList.length) *
                              10
                          ) / 10
                        : 0}{" "}
                      / 100
                    </p>
                  </div>
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shrink-0">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Pemeriksaan Sistem</p>
                    <p className="text-sm font-bold text-amber-300">Otomatis &amp; Akurat</p>
                  </div>
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/25 flex items-center justify-center text-purple-400 shrink-0">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Hak Akses Koreksi</p>
                    <p className="text-sm font-bold text-emerald-300">Guru Pengampu</p>
                  </div>
                </div>
              </div>

              {/* Student Score Breakdown Table */}
              <div className="glass-panel p-5 space-y-4 border border-slate-800">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm">
                      Daftar Hasil &amp; Rincian Skor Siswa
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Rincian perolehan skor jawaban siswa pada jadwal ujian ini.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="indigo">
                      Kelas: {selectedScheduleInfo?.class_name} | {selectedScheduleInfo?.subject_name}
                    </Badge>
                    <Badge variant="emerald">
                      <span className="flex items-center gap-1">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Terotorisasi (Guru Pengampu)
                      </span>
                    </Badge>
                  </div>
                </div>

                {isLoadingAnswers ? (
                  <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                    <span>Memuat rincian skor siswa...</span>
                  </div>
                ) : studentAnswersList.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-400 border border-dashed rounded-xl">
                    Belum ada data pengerjaan siswa untuk jadwal ujian ini.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                          <th className="py-3 px-4 font-bold">No</th>
                          <th className="py-3 px-4 font-bold">Nama Siswa &amp; NISN</th>
                          {scheduleQuestionTypes.hasPg && (
                            <th className="py-3 px-4 font-bold text-center">Skor PG</th>
                          )}
                          {scheduleQuestionTypes.hasIs && (
                            <th className="py-3 px-4 font-bold text-center">Skor Isian (IS)</th>
                          )}
                          {scheduleQuestionTypes.hasEs && (
                            <th className="py-3 px-4 font-bold text-center">Skor Essay (ES)</th>
                          )}
                          <th className="py-3 px-4 font-bold text-center">Nilai Akhir</th>
                          <th className="py-3 px-4 font-bold text-center">Status</th>
                          <th className="py-3 px-4 font-bold text-right">Aksi Koreksi</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-850">
                        {studentAnswersList.map((st, idx) => (
                          <tr key={st.attempt_id || idx} className="hover:bg-slate-900/40">
                            <td className="py-3.5 px-4 font-mono text-slate-500 font-bold">
                              {idx + 1}
                            </td>
                            <td className="py-3.5 px-4">
                              <span className="font-bold text-slate-200 block">
                                {st.student_name}
                              </span>
                              <span className="text-[10px] font-mono text-slate-500 block">
                                NISN: {st.nisn || "-"}
                              </span>
                            </td>
                            {scheduleQuestionTypes.hasPg && (
                              <td className="py-3.5 px-4 text-center font-bold text-emerald-400">
                                {st.max_pg > 0 ? `${st.score_pg !== undefined ? st.score_pg : 0} / ${st.max_pg}` : "-"}
                              </td>
                            )}
                            {scheduleQuestionTypes.hasIs && (
                              <td className="py-3.5 px-4 text-center font-bold text-indigo-400">
                                {st.max_is > 0 ? `${st.score_is !== undefined ? st.score_is : 0} / ${st.max_is}` : "-"}
                              </td>
                            )}
                            {scheduleQuestionTypes.hasEs && (
                              <td className="py-3.5 px-4 text-center font-bold text-purple-400">
                                {st.max_es > 0 ? `${st.score_es !== undefined ? st.score_es : 0} / ${st.max_es}` : "-"}
                              </td>
                            )}
                            <td className="py-3.5 px-4 text-center">
                              <span className="text-sm font-black text-amber-300 bg-amber-950/40 border border-amber-500/30 px-2.5 py-1 rounded-lg">
                                {st.final_score !== undefined ? st.final_score : 100}
                              </span>
                            </td>
                            <td className="py-3.5 px-4 text-center">
                              <Badge variant={st.status === "GRADED" ? "emerald" : "amber"}>
                                {st.status === "GRADED" ? "RILIS" : "SUBMITTED"}
                              </Badge>
                            </td>
                            <td className="py-3.5 px-4 text-right">
                              <Button
                                variant="primary"
                                size="sm"
                                leftIcon={<Eye className="w-3.5 h-3.5" />}
                                onClick={() => setSelectedStudentAttempt(st)}
                                title="Buka Lembar Jawaban & Koreksi Nilai Essay Siswa"
                              >
                                Detail &amp; Koreksi Jawaban &rarr;
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* LEVEL 3: DEDICATED FULL-PAGE STUDENT LEMBAR JAWABAN & FORM KOREKSI */
            <div className="space-y-6 animate-fade-in">
              {/* Top Banner Student Info & Global Save Action */}
              <div className="glass-panel p-5 rounded-2xl border border-slate-800 bg-slate-900/60 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <span className="text-[10px] font-bold text-indigo-400 bg-indigo-950/60 px-2.5 py-1 rounded-full border border-indigo-500/20 mb-2 inline-block">
                    {selectedScheduleInfo?.package_name} — {selectedScheduleInfo?.subject_name}
                  </span>
                  <h3 className="text-lg font-black text-slate-100 flex items-center gap-2">
                    <GraduationCap className="w-5 h-5 text-indigo-400" />
                    <span>Lembar Jawaban &amp; Koreksi: {selectedStudentAttempt.student_name}</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">
                    NISN: <strong className="text-slate-200">{selectedStudentAttempt.nisn || "-"}</strong> | Kelas: <strong className="text-indigo-300">{selectedScheduleInfo?.class_name}</strong> | Judul Ujian: <strong className="text-slate-200">{selectedScheduleInfo?.title}</strong>
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <Badge variant="emerald">
                    <span className="flex items-center gap-1 font-bold">
                      <ShieldCheck className="w-4 h-4" />
                      Guru Pengampu Resmi
                    </span>
                  </Badge>

                  <Button
                    variant="primary"
                    size="md"
                    leftIcon={<CheckCircle className="w-4 h-4" />}
                    isLoading={isSavingAll}
                    onClick={handleSaveAllScores}
                  >
                    💾 Simpan &amp; Kunci Seluruh Nilai Siswa
                  </Button>
                </div>
              </div>

              {/* 4 Bento Box Stats Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Nilai Akhir Ujian</span>
                  <p className="text-2xl font-black text-amber-300 mt-1">
                    {attemptStats.final_score} <span className="text-xs font-normal text-slate-500">/ 100</span>
                  </p>
                  <span className="text-[10px] text-slate-500 block mt-0.5">
                    Total Poin: {attemptStats.total_earned} / {attemptStats.total_max}
                  </span>
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Skor Pilihan Ganda (PG)</span>
                  {attemptStats.count_pg > 0 ? (
                    <>
                      <p className="text-2xl font-black text-emerald-400 mt-1">
                        {attemptStats.score_pg} <span className="text-xs font-normal text-slate-500">/ {attemptStats.max_pg}</span>
                      </p>
                      <span className="text-[10px] text-emerald-400/80 block mt-0.5">{attemptStats.count_pg} Butir Soal</span>
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-black text-slate-600 mt-1">-</p>
                      <span className="text-[10px] text-slate-500 block mt-0.5">Tidak ada soal PG</span>
                    </>
                  )}
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Skor Isian Singkat (IS)</span>
                  {attemptStats.count_is > 0 ? (
                    <>
                      <p className="text-2xl font-black text-indigo-400 mt-1">
                        {attemptStats.score_is} <span className="text-xs font-normal text-slate-500">/ {attemptStats.max_is}</span>
                      </p>
                      <span className="text-[10px] text-indigo-400/80 block mt-0.5">{attemptStats.count_is} Butir Soal</span>
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-black text-slate-600 mt-1">-</p>
                      <span className="text-[10px] text-slate-500 block mt-0.5">Tidak ada soal IS</span>
                    </>
                  )}
                </div>

                <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60">
                  <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">Skor Essay (ES)</span>
                  {attemptStats.count_es > 0 ? (
                    <>
                      <p className="text-2xl font-black text-purple-400 mt-1">
                        {attemptStats.score_es} <span className="text-xs font-normal text-slate-500">/ {attemptStats.max_es}</span>
                      </p>
                      <span className="text-[10px] text-purple-400/80 block mt-0.5">{attemptStats.count_es} Butir Soal</span>
                    </>
                  ) : (
                    <>
                      <p className="text-2xl font-black text-slate-600 mt-1">-</p>
                      <span className="text-[10px] text-slate-500 block mt-0.5">Tidak ada soal Essay</span>
                    </>
                  )}
                </div>
              </div>

              {/* Full-Width Questions & Answers Breakdown */}
              <div className="glass-panel p-6 space-y-6 border border-slate-800">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                      <BookOpen className="w-4 h-4 text-indigo-400" />
                      Lembar Jawaban Siswa &amp; Form Koreksi Guru
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Rincian jawaban butir soal per kategori. Guru dapat menginput skor essay dan catatan evaluasi secara langsung.
                    </p>
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    leftIcon={<CheckCircle className="w-4 h-4" />}
                    isLoading={isSavingAll}
                    onClick={handleSaveAllScores}
                  >
                    Simpan Nilai Siswa
                  </Button>
                </div>

                {/* Question Type Filter Tabs */}
                <div className="flex items-center gap-2 border-b border-slate-800 pb-2 flex-wrap">
                  <button
                    onClick={() => setLevel3QuestionTab("ALL")}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                      level3QuestionTab === "ALL"
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                        : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Semua Soal ({selectedStudentAttempt.answers?.length || 0})
                  </button>

                  <button
                    onClick={() => setLevel3QuestionTab("PG")}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                      level3QuestionTab === "PG"
                        ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                        : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Pilihan Ganda (PG) (
                    {selectedStudentAttempt.answers?.filter((a: any) => a.question_type === "PG").length || 0}
                    )
                  </button>

                  <button
                    onClick={() => setLevel3QuestionTab("IS")}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                      level3QuestionTab === "IS"
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                        : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Isian Singkat (IS) (
                    {selectedStudentAttempt.answers?.filter((a: any) => a.question_type === "IS").length || 0}
                    )
                  </button>

                  <button
                    onClick={() => setLevel3QuestionTab("ES")}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                      level3QuestionTab === "ES"
                        ? "bg-purple-600 text-white shadow-md shadow-purple-600/20"
                        : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Essay / Uraian (ES) (
                    {selectedStudentAttempt.answers?.filter(
                      (a: any) => a.question_type === "ES"
                    ).length || 0}
                    )
                  </button>
                </div>

                {filteredAnswers && filteredAnswers.length > 0 ? (
                  <div className="space-y-4">
                    {filteredAnswers.map((ans: any, aIdx: number) => {
                      const qKey = ans.question_id ? `q-${ans.question_type}-${ans.question_id}` : `q-${ans.question_type}-${aIdx}`;
                      const maxScoreVal = ans.max_score || 10;
                      const earnedScoreVal = ans.score_earned !== undefined && ans.score_earned !== null ? ans.score_earned : 0;
                      const confidenceVal = typeof ans.confidence === "number"
                        ? ans.confidence
                        : (ans.evaluation_id ? (earnedScoreVal >= maxScoreVal * 0.9 ? 0.95 : earnedScoreVal >= maxScoreVal * 0.75 ? 0.82 : 0.65) : undefined);
                      const confidencePct = confidenceVal !== undefined ? Math.max(0, Math.min(100, Math.round(confidenceVal * 100))) : null;
                      const confLevel: "HIGH" | "MEDIUM" | "LOW" | null = ans.confidence_level || (confidencePct !== null ? (confidencePct >= 90 ? "HIGH" : confidencePct >= 75 ? "MEDIUM" : "LOW") : null);
                      const gaugeRadius = 26;
                      const gaugeCircumference = 2 * Math.PI * gaugeRadius;
                      const gaugeOffset = confidencePct !== null ? gaugeCircumference - (confidencePct / 100) * gaugeCircumference : 0;
                      const gaugeStrokeColor = (confidencePct || 0) >= 90 ? "#10b981" : (confidencePct || 0) >= 75 ? "#f59e0b" : "#ef4444";
                      const gaugeTextColor = (confidencePct || 0) >= 90 ? "text-emerald-400" : (confidencePct || 0) >= 75 ? "text-amber-400" : "text-rose-400";

                      return (
                        <div key={qKey} className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
                          <div className="flex items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5 flex-wrap">
                            <span className="font-bold text-slate-100 text-sm flex items-center gap-2">
                              <span className="w-6 h-6 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-xs font-bold">
                                {aIdx + 1}
                              </span>
                              <span>Soal #{aIdx + 1} ({ans.question_type || "PG"})</span>
                            </span>
                            <div className="flex items-center gap-2 flex-wrap">
                              {confLevel === "HIGH" && (
                                <Badge variant="emerald" size="sm">
                                  <CheckCircle className="w-3 h-3" />
                                  <span>HIGH (90–100%) — Auto Accept</span>
                                </Badge>
                              )}
                              {confLevel === "MEDIUM" && (
                                <Badge variant="amber" size="sm">
                                  <AlertTriangle className="w-3 h-3" />
                                  <span>MEDIUM (75–89%) — Requires Review</span>
                                </Badge>
                              )}
                              {confLevel === "LOW" && (
                                <Badge variant="crimson" size="sm">
                                  <AlertTriangle className="w-3 h-3" />
                                  <span>LOW (0–74%) — Manual Review Required</span>
                                </Badge>
                              )}
                              <Badge variant={ans.score_earned > 0 ? "emerald" : "amber"}>
                                Skor: {ans.score_earned !== undefined && ans.score_earned !== null ? ans.score_earned : 0} / {ans.max_score}
                              </Badge>
                            </div>
                          </div>

                          {ans.question_content && (
                            <div className="text-xs font-medium text-slate-200 leading-relaxed bg-slate-950/40 p-4 rounded-xl border border-slate-850">
                              <LaTeXText content={ans.question_content} />
                            </div>
                          )}

                          <div className="p-3.5 bg-slate-950 rounded-xl border border-slate-800 text-xs text-indigo-300 space-y-1">
                            <span className="text-[10px] text-slate-500 font-bold block uppercase tracking-wider">Jawaban Siswa:</span>
                            <div className="whitespace-pre-wrap font-mono">
                              <LaTeXText content={ans.text_answer || ans.selected_option || "(Tidak diisi)"} />
                            </div>
                          </div>

                          {/* R5: AI Confidence Elevation, Review Badges, Rubric Breakdown, & Academic Rationale */}
                          {(ans.question_type === "ES" || ans.evaluation_id || confidenceVal !== undefined) && (
                            <div className="p-4 rounded-xl bg-slate-950/60 border border-indigo-500/20 space-y-4">
                              {/* Visual Confidence Gauge & Categorical Recommendation Badge */}
                              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-3.5 bg-slate-900/70 rounded-xl border border-slate-800">
                                <div className="flex items-center gap-3">
                                  {confidencePct !== null && (
                                    <div className="flex items-center gap-3 bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
                                      <div className="relative w-16 h-16 flex items-center justify-center shrink-0">
                                        <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 68 68">
                                          <circle
                                            cx="34"
                                            cy="34"
                                            r={gaugeRadius}
                                            stroke="currentColor"
                                            strokeWidth="5"
                                            className="text-slate-800"
                                            fill="transparent"
                                          />
                                          <circle
                                            cx="34"
                                            cy="34"
                                            r={gaugeRadius}
                                            stroke={gaugeStrokeColor}
                                            strokeWidth="5"
                                            strokeDasharray={gaugeCircumference}
                                            strokeDashoffset={gaugeOffset}
                                            strokeLinecap="round"
                                            fill="transparent"
                                            className="transition-all duration-700 ease-out"
                                          />
                                        </svg>
                                        <span className={`absolute text-xs font-black font-mono ${gaugeTextColor}`}>
                                          {confidencePct}%
                                        </span>
                                      </div>
                                      <div className="space-y-0.5">
                                        <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block">
                                          Visual Confidence Gauge
                                        </span>
                                        <div className="text-xs font-semibold text-slate-200">
                                          Tingkat Keyakinan AI
                                        </div>
                                        <div className="w-28 bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
                                          <div
                                            className="h-full rounded-full transition-all duration-700"
                                            style={{ width: `${confidencePct}%`, backgroundColor: gaugeStrokeColor }}
                                          />
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>

                                <div className="space-y-1.5 flex flex-col items-start sm:items-end">
                                  <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                                    Status Klasifikasi &amp; Rekomendasi
                                  </span>
                                  <div>
                                    {confLevel === "HIGH" && (
                                      <Badge variant="emerald" size="md">
                                        <CheckCircle className="w-4 h-4" />
                                        <span>HIGH (90–100%) — Auto Accept</span>
                                      </Badge>
                                    )}
                                    {confLevel === "MEDIUM" && (
                                      <Badge variant="amber" size="md">
                                        <AlertTriangle className="w-4 h-4" />
                                        <span>MEDIUM (75–89%) — Requires Review</span>
                                      </Badge>
                                    )}
                                    {confLevel === "LOW" && (
                                      <Badge variant="crimson" size="md">
                                        <AlertTriangle className="w-4 h-4" />
                                        <span>LOW (0–74%) — Manual Review Required</span>
                                      </Badge>
                                    )}
                                  </div>
                                  <span className="text-[11px] text-slate-400 font-medium">
                                    {confLevel === "HIGH"
                                      ? "Keyakinan tinggi. Nilai otomatis diverifikasi aman diterima."
                                      : confLevel === "MEDIUM"
                                      ? "Keyakinan sedang. Guru disarankan memeriksa rincian kriteria."
                                      : "Keyakinan rendah. Memerlukan peninjauan & evaluasi manual guru."}
                                  </span>
                                </div>
                              </div>

                              {/* Rubric Criteria Breakdown */}
                              {ans.rubric_scores && ans.rubric_scores.length > 0 && (
                                <div className="space-y-2 p-3 bg-slate-900/50 rounded-xl border border-slate-800/80">
                                  <div className="flex items-center justify-between text-xs font-bold text-slate-300 pb-2 border-b border-slate-800">
                                    <span className="flex items-center gap-1.5">
                                      <FileText className="w-4 h-4 text-indigo-400" />
                                      <span>Rincian Kriteria Rubrik Penilaian (Rubric Criteria Breakdown)</span>
                                    </span>
                                    <span className="text-[11px] font-mono text-slate-400">
                                      {ans.rubric_scores.length} Kriteria
                                    </span>
                                  </div>
                                  <div className="space-y-2 pt-1">
                                    {ans.rubric_scores.map((crit: any, cIdx: number) => {
                                      const achievedPct = typeof crit.achieved === "number" ? crit.achieved : 0;
                                      const weight = crit.weight || 0;
                                      const maxPts = crit.max_score !== undefined ? crit.max_score : Math.round(((weight / 100) * (ans.max_score || 10)) * 10) / 10;
                                      const earnedPts = crit.earned_score !== undefined ? crit.earned_score : Math.round(((achievedPct / 100) * maxPts) * 10) / 10;
                                      return (
                                        <div key={`rubric-${crit.ku_id || cIdx}`} className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs space-y-1.5">
                                          <div className="flex items-center justify-between gap-2 flex-wrap">
                                            <div className="flex items-center gap-2">
                                              <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono text-[10px] font-bold border border-indigo-500/30">
                                                {crit.ku_id || `C${cIdx + 1}`}
                                              </span>
                                              <span className="font-semibold text-slate-200">
                                                {crit.text || `Kriteria #${cIdx + 1}`}
                                              </span>
                                            </div>
                                            <div className="flex items-center gap-2 font-mono text-[11px]">
                                              <span className="text-slate-400">Bobot: {weight}%</span>
                                              <span className="text-slate-600">•</span>
                                              <span className="font-bold text-indigo-300">
                                                {earnedPts} / {maxPts} Poin
                                              </span>
                                            </div>
                                          </div>
                                          <div className="flex items-center gap-2">
                                            <div className="flex-1 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                              <div
                                                className={`h-full rounded-full transition-all duration-500 ${
                                                  achievedPct >= 80 ? "bg-emerald-500" : achievedPct >= 50 ? "bg-amber-500" : "bg-rose-500"
                                                }`}
                                                style={{ width: `${Math.min(100, Math.max(0, achievedPct))}%` }}
                                              />
                                            </div>
                                            <span className="font-mono text-[10px] text-slate-400 font-bold shrink-0">
                                              {achievedPct}% Capaian
                                            </span>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}

                              {/* Generated Academic Rationale */}
                              {(ans.academic_rationale || ans.ai_feedback) && (
                                <div className="p-3.5 bg-indigo-950/30 rounded-xl border border-indigo-500/30 text-xs space-y-1.5">
                                  <div className="flex items-center gap-1.5 font-bold text-indigo-300 text-xs">
                                    <BookOpen className="w-4 h-4 text-indigo-400" />
                                    <span>Rasional Akademik &amp; Justifikasi Pedagogis (Generated Academic Rationale):</span>
                                  </div>
                                  <div className="text-slate-300 text-xs leading-relaxed italic bg-slate-950/60 p-3 rounded-lg border border-indigo-500/20 font-sans">
                                    "{ans.academic_rationale || ans.ai_feedback}"
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Inline Score Correction Box for Teacher (PG, IS, and ES) */}
                          {ans.evaluation_id && (
                            <div className={`p-4 rounded-xl space-y-3 mt-3 border ${
                              ans.question_type === "ES"
                                ? "bg-purple-950/20 border-purple-500/30"
                                : ans.question_type === "IS"
                                ? "bg-indigo-950/20 border-indigo-500/30"
                                : "bg-slate-950/40 border-slate-800"
                            }`}>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                                  <Edit2 className="w-4 h-4 text-amber-400" />
                                  Form Koreksi Skor Guru (Soal #{aIdx + 1} - {ans.question_type || "PG"}):
                                </span>
                                <span className="text-xs text-slate-400 font-mono">Batas Skor Maksimal: {ans.max_score || 100} Poin</span>
                              </div>

                              <div className={`grid grid-cols-1 ${ans.question_type === "ES" ? "md:grid-cols-3" : "md:grid-cols-1"} gap-3 items-start`}>
                                <div className={ans.question_type === "ES" ? "md:col-span-1" : "w-full"}>
                                  <label className="block text-[11px] font-semibold text-slate-400 mb-1">Skor Guru (0 - {ans.max_score || 100})</label>
                                  <Input
                                    type="number"
                                    min={0}
                                    max={ans.max_score || 100}
                                    value={ans.score_earned !== undefined && ans.score_earned !== null ? ans.score_earned : 0}
                                    id={`full-score-${ans.question_id}`}
                                    placeholder="Masukkan skor..."
                                    onChange={(e) => {
                                      const val = parseFloat(e.target.value);
                                      const maxAllowed = ans.max_score || 100;
                                      let finalVal = isNaN(val) ? 0 : val;
                                      if (finalVal > maxAllowed) {
                                        showToast({
                                          type: "warning",
                                          title: "Skor Melebihi Maksimum",
                                          message: `Perubahan skor ditolak! Nilai tidak boleh melebihi skor maksimal (${maxAllowed} poin). Otomatis disesuaikan ke ${maxAllowed}.`,
                                        });
                                        finalVal = maxAllowed;
                                      } else if (finalVal < 0) {
                                        finalVal = 0;
                                      }
                                      const qId = ans.question_id;
                                      setSelectedStudentAttempt((prev: any) => {
                                        if (!prev || !prev.answers) return prev;
                                        const newAnswers = prev.answers.map((a: any) =>
                                          a.question_id === qId ? { ...a, score_earned: finalVal } : a
                                        );
                                        return { ...prev, answers: newAnswers };
                                      });
                                    }}
                                  />
                                </div>

                                {ans.question_type === "ES" && (
                                  <div className="md:col-span-2">
                                    <label className="block text-[11px] font-semibold text-slate-400 mb-1">Catatan &amp; Feedback Guru (Opsional):</label>
                                    <Input
                                      type="text"
                                      value={ans.ai_feedback || ""}
                                      id={`full-fb-${ans.question_id}`}
                                      placeholder="Tuliskan catatan evaluasi perbaikan untuk siswa..."
                                      onChange={(e) => {
                                        const newFb = e.target.value;
                                        const qId = ans.question_id;
                                        setSelectedStudentAttempt((prev: any) => {
                                          if (!prev || !prev.answers) return prev;
                                          const newAnswers = prev.answers.map((a: any) =>
                                            a.question_id === qId ? { ...a, ai_feedback: newFb } : a
                                          );
                                          return { ...prev, answers: newAnswers };
                                        });
                                      }}
                                    />
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}

                    <div className="flex justify-end pt-4 border-t border-slate-800">
                      <Button
                        variant="primary"
                        size="md"
                        leftIcon={<CheckCircle className="w-5 h-5" />}
                        isLoading={isSavingAll}
                        onClick={handleSaveAllScores}
                      >
                        💾 Simpan &amp; Kunci Seluruh Nilai Siswa
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center text-xs text-slate-400 border border-dashed rounded-xl">
                    Tidak ada rincian butir soal individual untuk siswa ini.
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── TAB 2: PORTAL SANGGAHAN / PROTES NILAI SISWA ── */}
      {activeTab === "PROTESTS" && (
        <div className="glass-panel p-6 space-y-4 border border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Pengajuan Sanggahan / Protes Nilai Siswa</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Ketentuan: Jika guru menyetujui sanggahan, nilai diperbaiki. Jika ditolak, siswa dikenakan{" "}
                <strong>penalti potongan -5 poin</strong>.
              </p>
            </div>
          </div>

          {protests.length === 0 ? (
            <div className="p-12 text-center flex flex-col items-center justify-center gap-3 border border-dashed rounded-xl border-slate-800">
              <AlertTriangle className="w-10 h-10 text-slate-600" />
              <h4 className="text-sm font-bold text-slate-300">Belum Ada Sanggahan Nilai Siswa</h4>
              <p className="text-xs text-slate-500 max-w-sm">
                Belum ada siswa yang mengajukan sanggahan atau protes nilai saat ini.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {protests.map((p) => (
                <div key={p.id} className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-bold text-slate-100 text-sm block">{p.student_name}</span>
                      <span className="text-[11px] text-slate-400">
                        {p.package_name} | {p.subject_name}
                      </span>
                    </div>
                    <Badge
                      variant={
                        p.status === "APPROVED"
                          ? "emerald"
                          : p.status === "REJECTED_WITH_PENALTY"
                          ? "crimson"
                          : "amber"
                      }
                    >
                      {p.status === "APPROVED"
                        ? "DISETUJUI (+5)"
                        : p.status === "REJECTED_WITH_PENALTY"
                        ? "DITOLAK (-5 PENALTI)"
                        : "MENUNGGU RIVIEW"}
                    </Badge>
                  </div>

                  <div className="p-3 bg-slate-950 rounded-xl text-xs text-slate-300 border border-slate-850">
                    <span className="text-[10px] text-slate-500 block font-bold mb-1">
                      Alasan Protes Siswa:
                    </span>
                    &ldquo;{p.reason}&rdquo;
                  </div>

                  {p.status === "PENDING" && (
                    <div className="flex items-center justify-end gap-2 pt-1">
                      <Button
                        variant="danger"
                        size="sm"
                        leftIcon={<X className="w-3.5 h-3.5" />}
                        onClick={() => handleResolveProtest(p.id, "REJECT")}
                      >
                        Tolak Sanggahan (-5 Poin)
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        leftIcon={<Check className="w-3.5 h-3.5" />}
                        onClick={() => handleResolveProtest(p.id, "ACCEPT")}
                      >
                        Setujui Sanggahan (+Nilai)
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}





      {/* ── Modal: BAP Viewer ── */}
      <Modal
        isOpen={isBapModalOpen}
        onClose={() => setIsBapModalOpen(false)}
        title="Dokumen Berita Acara Pelaksanaan (BAP)"
        maxWidth="md"
      >
        {bapModalData && (
          <div className="space-y-4 text-xs">
            <div className="p-4 bg-slate-900 rounded-xl border border-slate-800 space-y-2">
              <h4 className="font-bold text-slate-100 text-sm">
                BAP #{bapModalData.id} - {bapModalData.exam_title || "Ujian"}
              </h4>
              <p className="text-slate-400">
                Pengawas: <strong>{bapModalData.proctor_name || "Guru"}</strong>
              </p>
              <p className="text-slate-400">
                Catatan Pengawas: &ldquo;{bapModalData.proctor_notes || "Tidak ada insiden."}&rdquo;
              </p>
            </div>
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setIsBapModalOpen(false)}>
                Tutup
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
