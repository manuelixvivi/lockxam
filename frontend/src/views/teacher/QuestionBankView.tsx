import React, { useState, useEffect, useRef } from "react";
import {
  BookOpen,
  Plus,
  Trash2,
  Edit2,
  FileText,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Search,
  Download,
  Upload,
  Loader2,
  FileSpreadsheet,
  AlertCircle,
  RefreshCw,
  Image,
  Sparkles,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Modal } from "../../components/ui/Modal";
import { MessageBox } from "../../components/ui/MessageBox";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { teacherContentApi } from "../../api/teacherContent";
import { LaTeXText } from "../../components/ui/LaTeXText";
import type { Question, QuestionType } from "../../api/teacherContent";
import { downloadMultiSheetXlsxTemplate, readMultiSheetXlsxFile, extractEmbeddedImagesFromXlsx } from "../../utils/xlsx";
import { AddDataChoiceModal } from "../../components/ui/AddDataChoiceModal";
import { getTeacherAssignedSubjectOptions } from "../../utils/subjects";
import { getGradeOptionsForSchool, normalizeRubricWeights } from "../../utils/gradeLevels";

interface QuestionBankViewProps {
  onNavigate?: (href: string) => void;
}

export function QuestionBankView({}: QuestionBankViewProps) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("");
  const [filterSubject, setFilterSubject] = useState<string>("");
  const [filterClassLevel, setFilterClassLevel] = useState<string>("");

  // Modal states
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState(false);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<Question | null>(null);

  const gradeOptions = React.useMemo(() => {
    return getGradeOptionsForSchool(user?.school_level_code);
  }, [user?.school_level_code]);
  const defaultGrade = gradeOptions[0]?.value || "VII";

  // Form states
  const [type, setType] = useState<QuestionType>("PG");
  const [content, setContent] = useState("");
  const [answerKey, setAnswerKey] = useState("");
  const [subject, setSubject] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [aiGrading, setAiGrading] = useState(false);
  const [options, setOptions] = useState<string[]>(["", "", "", ""]);
  const [rubrics, setRubrics] = useState<{ criteria: string; max_score: number }[]>([
    { criteria: "Pemahaman Masalah", max_score: 50 },
    { criteria: "Langkah Penyelesaian", max_score: 50 },
  ]);
  const [isGeneratingAiRubric, setIsGeneratingAiRubric] = useState(false);

  const handleGenerateAiRubric = async () => {
    if (!content.trim() || !answerKey.trim()) {
      showToast({
        type: "error",
        title: "Pertanyaan & Kunci Jawaban Wajib Diisi",
        message: "Silakan isi pertanyaan dan kunci jawaban terlebih dahulu sebelum menggenerasi rubrik AI.",
      });
      return;
    }

    setIsGeneratingAiRubric(true);
    try {
      const res = await teacherContentApi.generateAiRubric({
        question_text: content,
        answer_key: answerKey,
        education_level: user?.school_level_code || "SMA",
        education_class: classLevel || "Kelas 11",
      });

      if (res.status === "success" && res.rubrics && Array.isArray(res.rubrics) && res.rubrics.length > 0) {
        const generated = normalizeRubricWeights(res.rubrics, answerKey);
        setRubrics(generated);
        setAiGrading(true);
        showToast({
          type: "success",
          title: "Rubrik AI Berhasil Digenerate",
          message: `${generated.length} kriteria rubrik & persentase bobot telah dibuat oleh AI. Anda tetap dapat mengeditnya.`,
        });
      } else {
        throw new Error(res.error || "Gagal menghasilkan rubrik dari AI.");
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Generate Rubrik AI",
        message: err?.message || "Terjadi kesalahan saat menghubungi service AI.",
      });
    } finally {
      setIsGeneratingAiRubric(false);
    }
  };

  // Image Upload States
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const questionImgInputRef = useRef<HTMLInputElement>(null);

  const handleUploadImageToContent = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingImage(true);
    try {
      const res = await teacherContentApi.uploadQuestionImage(file);
      setContent((prev) => (prev ? prev + `\n![Gambar Soal](${res.url})` : `![Gambar Soal](${res.url})`));
      showToast({ type: "success", title: "Gambar Berhasil Diunggah", message: "Tag gambar telah disisipkan ke pertanyaan." });
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Mengunggah Gambar", message: err?.message });
    } finally {
      setIsUploadingImage(false);
      e.target.value = "";
    }
  };

  const handleUploadImageToOption = async (index: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingImage(true);
    try {
      const res = await teacherContentApi.uploadQuestionImage(file);
      const newOpts = [...options];
      newOpts[index] = (newOpts[index] || "").trim() ? `${newOpts[index].trim()} ![Opsi](${res.url})` : `![Opsi](${res.url})`;
      setOptions(newOpts);
      showToast({ type: "success", title: "Gambar Opsi Diunggah", message: `Gambar disisipkan ke Opsi ${String.fromCharCode(65 + index)}.` });
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Mengunggah Gambar", message: err?.message });
    } finally {
      setIsUploadingImage(false);
      e.target.value = "";
    }
  };

  // Import states
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importSubject, setImportSubject] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);
  const [importReport, setImportReport] = useState<{
    success: number;
    skipped: { row: number; sheet: string; identifier: string; reason: string }[];
    failed: { row: number; sheet: string; identifier: string; reason: string }[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Get subjects strictly assigned to current teacher
  const subjectsTaught = user?.subjects_taught || [];
  const assignedSubjectOptions = getTeacherAssignedSubjectOptions(subjectsTaught);

  // Set default subject and grade level if not set
  useEffect(() => {
    if (!subject && subjectsTaught.length > 0) {
      setSubject(subjectsTaught[0]);
    }
    if (!importSubject && subjectsTaught.length > 0) {
      setImportSubject(subjectsTaught[0]);
    }
    if (!classLevel || classLevel === "X") {
      setClassLevel(defaultGrade);
    }
  }, [subjectsTaught, defaultGrade]);

  // UI States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [expandedQuestionId, setExpandedQuestionId] = useState<number | null>(null);

  const fetchQuestions = async () => {
    setIsLoading(true);
    try {
      const data = await teacherContentApi.listQuestions();
      setQuestions(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Bank Soal",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestions();
  }, []);

  const handleOpenAdd = () => {
    setEditingQuestion(null);
    setType("PG");
    setContent("");
    setAnswerKey("");
    setAiGrading(false);
    setSubject(subjectsTaught.length > 0 ? subjectsTaught[0] : "");
    setClassLevel(defaultGrade);
    setOptions(["", "", "", ""]);
    setRubrics([{ criteria: "Kriteria Utama", max_score: 10 }]);
    setIsAddModalOpen(true);
  };

  const handleOpenEdit = (q: Question) => {
    setEditingQuestion(q);
    setType(q.type);
    setContent(q.content);
    setAnswerKey(q.answer_key);
    setAiGrading(q.ai_grading || false);
    setSubject(q.subject || (subjectsTaught.length > 0 ? subjectsTaught[0] : ""));
    setClassLevel(q.class_level || "X");
    setOptions(q.options || ["", "", "", ""]);
    setRubrics(q.rubrics || [{ criteria: "Kriteria Utama", max_score: 10 }]);
    setIsAddModalOpen(true);
  };

  // Delete confirm state
  const [deletingQuestionId, setDeletingQuestionId] = useState<number | null>(null);
  const [isDeletingQuestion, setIsDeletingQuestion] = useState(false);

  const handleDelete = (id: number) => {
    setDeletingQuestionId(id);
  };

  const handleConfirmDeleteQuestion = async () => {
    if (!deletingQuestionId) return;
    setIsDeletingQuestion(true);
    try {
      await teacherContentApi.deleteQuestion(deletingQuestionId);
      showToast({ type: "success", title: "Soal berhasil dihapus dari Bank Soal." });
      setDeletingQuestionId(null);
      fetchQuestions();
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menghapus Soal",
        message: err?.message || "Soal mungkin sedang digunakan di paket soal aktif.",
      });
    } finally {
      setIsDeletingQuestion(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Mata pelajaran wajib dipilih." });
      return;
    }

    if (!content.trim() || !answerKey.trim()) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Pertanyaan dan Kunci Jawaban wajib diisi." });
      return;
    }

    let finalOptions: string[] | null = null;
    if (type === "PG") {
      const filteredOptions = options.map((o) => o.trim()).filter(Boolean);
      if (filteredOptions.length < 2) {
        showToast({ type: "warning", title: "Validasi Gagal", message: "Soal Pilihan Ganda minimal membutuhkan 2 opsi." });
        return;
      }
      if (filteredOptions.length > 6) {
        showToast({ type: "warning", title: "Validasi Gagal", message: "Soal Pilihan Ganda maksimal 6 opsi (A-F)." });
        return;
      }
      finalOptions = filteredOptions;
      if (!finalOptions.includes(answerKey.trim())) {
        showToast({
          type: "warning",
          title: "Validasi Gagal",
          message: "Kunci jawaban harus sama persis dengan salah satu opsi pilihan ganda.",
        });
        return;
      }
    }

    let finalRubrics = type === "ES" ? rubrics : [];
    if (type === "ES" && !aiGrading) {
      const validRubrics = rubrics.filter((r) => r.criteria.trim() && r.max_score > 0);
      if (validRubrics.length === 0) {
        showToast({
          type: "warning",
          title: "Validasi Gagal",
          message: "Rubrik manual minimal harus memiliki 1 kriteria penilaian dengan skor positif.",
        });
        return;
      }
      if (validRubrics.length > 5) {
        showToast({
          type: "warning",
          title: "Validasi Gagal",
          message: "Rubrik manual maksimal 5 kriteria penilaian.",
        });
        return;
      }
      finalRubrics = validRubrics;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        type,
        content: content.trim(),
        options: finalOptions,
        answer_key: answerKey.trim(),
        rubrics: finalRubrics,
        subject,
        class_level: classLevel,
        ai_grading: type === "ES" ? aiGrading : false,
      };

      if (editingQuestion) {
        await teacherContentApi.updateQuestion(editingQuestion.id, payload);
        showToast({ type: "success", title: "Soal berhasil diperbarui." });
      } else {
        await teacherContentApi.createQuestion(payload);
        showToast({ type: "success", title: "Soal baru berhasil ditambahkan." });
      }
      setIsAddModalOpen(false);
      fetchQuestions();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal menyimpan soal", message: err?.message });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Option handlers (Max 6 options: A, B, C, D, E, F)
  const handleAddOptionField = () => {
    if (options.length >= 6) {
      showToast({ type: "warning", title: "Batas Opsi Terpenuhi", message: "Soal Pilihan Ganda maksimal 6 opsi (A-F)." });
      return;
    }
    setOptions((prev) => [...prev, ""]);
  };

  const handleRemoveOptionField = (index: number) => {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  };

  const handleOptionChange = (index: number, val: string) => {
    setOptions((prev) => {
      const copy = [...prev];
      copy[index] = val;
      return copy;
    });
  };

  // Rubric handlers
  const handleAddRubricField = () => {
    if (rubrics.length >= 5) {
      showToast({ type: "warning", title: "Batas Rubrik Terpenuhi", message: "Essay maksimal 5 kriteria penilaian." });
      return;
    }
    setRubrics((prev) => [...prev, { criteria: "", max_score: 5 }]);
  };

  const handleRemoveRubricField = (index: number) => {
    setRubrics((prev) => prev.filter((_, i) => i !== index));
  };

  const handleRubricChange = (index: number, key: "criteria" | "max_score", val: any) => {
    setRubrics((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [key]: val };
      return copy;
    });
  };

  // Download Multi-Sheet Excel Template (with Opsi A - Opsi F & Tingkat Kelas)
  const handleDownloadTemplate = () => {
    const sheets = [
      {
        name: "Pilihan Ganda",
        headers: ["Mata Pelajaran", "Tingkat Kelas (X/XI/XII)", "Pertanyaan", "Kunci Jawaban", "Opsi A", "Opsi B", "Opsi C", "Opsi D", "Opsi E", "Opsi F"],
        samples: [
          {
            "Mata Pelajaran": "Matematika",
            "Tingkat Kelas (X/XI/XII)": "X",
            "Pertanyaan": "Siapakah penemu lampu pijar?",
            "Kunci Jawaban": "Thomas Alva Edison",
            "Opsi A": "Thomas Alva Edison",
            "Opsi B": "Albert Einstein",
            "Opsi C": "Nikola Tesla",
            "Opsi D": "Isaac Newton",
            "Opsi E": "Galileo Galilei",
            "Opsi F": ""
          }
        ]
      },
      {
        name: "Isian Singkat",
        headers: ["Mata Pelajaran", "Tingkat Kelas (X/XI/XII)", "Pertanyaan", "Kunci Jawaban"],
        samples: [
          {
            "Mata Pelajaran": "Biologi",
            "Tingkat Kelas (X/XI/XII)": "X",
            "Pertanyaan": "Proses tumbuhan hijau membuat makanan sendiri dinamakan...",
            "Kunci Jawaban": "Fotosintesis"
          }
        ]
      },
      {
        name: "Essay",
        headers: [
          "Mata Pelajaran", "Tingkat Kelas (X/XI/XII)", "Pertanyaan", "Kunci Jawaban", "AI Grading (YA/TIDAK)",
          "Rubrik 1 Kriteria", "Rubrik 1 Skor Maks",
          "Rubrik 2 Kriteria", "Rubrik 2 Skor Maks",
          "Rubrik 3 Kriteria", "Rubrik 3 Skor Maks",
          "Rubrik 4 Kriteria", "Rubrik 4 Skor Maks",
          "Rubrik 5 Kriteria", "Rubrik 5 Skor Maks"
        ],
        samples: [
          {
            "Mata Pelajaran": "Fisika",
            "Tingkat Kelas (X/XI/XII)": "XI",
            "Pertanyaan": "Jelaskan perbedaan antara konduksi, konveksi, dan radiasi!",
            "Kunci Jawaban": "Konduksi hantaran langsung, konveksi aliran materi, radiasi pancaran...",
            "AI Grading (YA/TIDAK)": "YA",
            "Rubrik 1 Kriteria": "", "Rubrik 1 Skor Maks": "",
            "Rubrik 2 Kriteria": "", "Rubrik 2 Skor Maks": "",
            "Rubrik 3 Kriteria": "", "Rubrik 3 Skor Maks": "",
            "Rubrik 4 Kriteria": "", "Rubrik 4 Skor Maks": "",
            "Rubrik 5 Kriteria": "", "Rubrik 5 Skor Maks": ""
          },
          {
            "Mata Pelajaran": "Fisika",
            "Tingkat Kelas (X/XI/XII)": "XI",
            "Pertanyaan": "Sebutkan dan jelaskan hukum Newton 1, 2, dan 3!",
            "Kunci Jawaban": "Hukum 1 inersia, hukum 2 F=ma, hukum 3 aksi-reaksi...",
            "AI Grading (YA/TIDAK)": "TIDAK",
            "Rubrik 1 Kriteria": "Hukum Newton 1", "Rubrik 1 Skor Maks": "5",
            "Rubrik 2 Kriteria": "Hukum Newton 2", "Rubrik 2 Skor Maks": "5",
            "Rubrik 3 Kriteria": "Hukum Newton 3", "Rubrik 3 Skor Maks": "5",
            "Rubrik 4 Kriteria": "", "Rubrik 4 Skor Maks": "",
            "Rubrik 5 Kriteria": "", "Rubrik 5 Skor Maks": ""
          }
        ]
      }
    ];
    downloadMultiSheetXlsxTemplate(sheets, "Template_Bank_Soal");
    showToast({ type: "success", title: "Template berhasil diunduh." });
  };

  // Import XLSX Handler with Validation & Deduplication check (Opsi A - F & Tingkat Kelas)
  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ""; // reset

    if (!importSubject) {
      showToast({ type: "warning", title: "Subjek Kosong", message: "Harap pilih mata pelajaran untuk diimpor." });
      return;
    }

    setIsImporting(true);
    setImportReport(null);
    setImportProgress(null);

    try {
      const sheetsData = await readMultiSheetXlsxFile(file);

      // Method 2: Extract embedded drawings pasted directly into cells of XLSX
      let embeddedImages: any[] = [];
      try {
        embeddedImages = await extractEmbeddedImagesFromXlsx(file);
      } catch (e) {
        console.warn("Notice on cell drawing extraction:", e);
      }

      const rowToUploadedImgUrl: Record<number, string> = {};
      for (const imgItem of embeddedImages) {
        try {
          const res = await teacherContentApi.uploadQuestionImage(imgItem.file);
          const rKey = imgItem.row >= 1 ? imgItem.row : 1;
          rowToUploadedImgUrl[rKey] = res.url;
        } catch (err) {
          console.warn("Failed pre-uploading cell image:", err);
        }
      }
      
      const skipped: { row: number; sheet: string; identifier: string; reason: string }[] = [];
      const failed: { row: number; sheet: string; identifier: string; reason: string }[] = [];
      let successCount = 0;

      // 1. Gather all rows from PG, IS, Essay sheets
      const jobs: { type: QuestionType; row: Record<string, string>; rowIndex: number; sheet: string }[] = [];
      
      if (sheetsData["Pilihan Ganda"]) {
        sheetsData["Pilihan Ganda"].forEach((r, idx) => {
          jobs.push({ type: "PG", row: r, rowIndex: idx + 2, sheet: "Pilihan Ganda" });
        });
      }
      if (sheetsData["Isian Singkat"]) {
        sheetsData["Isian Singkat"].forEach((r, idx) => {
          jobs.push({ type: "IS", row: r, rowIndex: idx + 2, sheet: "Isian Singkat" });
        });
      }
      if (sheetsData["Essay"]) {
        sheetsData["Essay"].forEach((r, idx) => {
          jobs.push({ type: "ES", row: r, rowIndex: idx + 2, sheet: "Essay" });
        });
      }

      setImportProgress({ current: 0, total: jobs.length });

      for (let i = 0; i < jobs.length; i++) {
        const job = jobs[i];
        const { type, row, rowIndex, sheet } = job;
        let qContent = (row["Pertanyaan"] || "").trim();
        const cellImgUrl = rowToUploadedImgUrl[rowIndex] || rowToUploadedImgUrl[rowIndex - 1];
        if (cellImgUrl) {
          qContent += `\n![Gambar Soal](${cellImgUrl})`;
        } else if (row["Gambar Pertanyaan"]) {
          const gUrl = row["Gambar Pertanyaan"].trim();
          if (gUrl) qContent += `\n![Gambar Soal](${gUrl})`;
        }
        const qAnswer = (row["Kunci Jawaban"] || "").trim();
        const rowSubject = (row["Mata Pelajaran"] || importSubject || "").trim();
        const rowClassLevel = (row["Tingkat Kelas (X/XI/XII)"] || row["Tingkat Kelas"] || row["Tingkat"] || row["Grade Level"] || "X").trim();

        if (!qContent) {
          failed.push({ row: rowIndex, sheet, identifier: `Baris ${rowIndex}`, reason: "Kolom Pertanyaan kosong." });
          continue;
        }
        if (!qAnswer) {
          failed.push({ row: rowIndex, sheet, identifier: qContent, reason: "Kolom Kunci Jawaban kosong." });
          continue;
        }

        // Verification: check if question already exists in database
        const existing = questions.find(
          (q) => q.content.trim().toLowerCase() === qContent.toLowerCase() && q.type === type
        );

        if (existing) {
          skipped.push({
            row: rowIndex,
            sheet,
            identifier: qContent,
            reason: `Soal sudah ada di bank soal dengan ID #${existing.id}.`
          });
          continue;
        }

        // Build type specific fields
        let finalOptions: string[] | null = null;
        let finalRubrics: any[] = [];
        let isAi = false;

        if (type === "PG") {
          const optA = (row["Opsi A"] || "").trim();
          const optB = (row["Opsi B"] || "").trim();
          const optC = (row["Opsi C"] || "").trim();
          const optD = (row["Opsi D"] || "").trim();
          const optE = (row["Opsi E"] || "").trim();
          const optF = (row["Opsi F"] || "").trim();

          // Validation: min 2 options, max 6 options
          if (!optA || !optB) {
            failed.push({
              row: rowIndex,
              sheet,
              identifier: qContent,
              reason: "Soal PG wajib mencantumkan Opsi A dan Opsi B (minimal 2 opsi)."
            });
            continue;
          }

          finalOptions = [optA, optB, optC, optD, optE, optF].filter(Boolean);
          if (!finalOptions.includes(qAnswer)) {
            failed.push({
              row: rowIndex,
              sheet,
              identifier: qContent,
              reason: `Kunci Jawaban "${qAnswer}" tidak cocok dengan opsi mana pun.`
            });
            continue;
          }
        } else if (type === "ES") {
          const aiGradingText = (row["AI Grading (YA/TIDAK)"] || "").trim().toUpperCase();
          isAi = aiGradingText === "YA" || aiGradingText === "YES";

          if (isAi) {
            finalRubrics = [];
          } else {
            // Rubrics validation
            for (let rIdx = 1; rIdx <= 5; rIdx++) {
              const crit = (row[`Rubrik ${rIdx} Kriteria`] || "").trim();
              const scoreText = (row[`Rubrik ${rIdx} Skor Maks`] || "").trim();
              if (crit) {
                const maxS = parseInt(scoreText, 10) || 0;
                if (maxS <= 0) {
                  failed.push({
                    row: rowIndex,
                    sheet,
                    identifier: qContent,
                    reason: `Rubrik ${rIdx} Skor Maks harus angka positif.`
                  });
                  break;
                }
                finalRubrics.push({ criteria: crit, max_score: maxS });
              }
            }

            if (finalRubrics.length === 0) {
              failed.push({
                row: rowIndex,
                sheet,
                identifier: qContent,
                reason: "Untuk AI Grading = TIDAK, rubrik manual wajib diisi minimal 1 kriteria."
              });
              continue;
            }
          }
        }

        // Upload to backend
        try {
          await teacherContentApi.createQuestion({
            type,
            content: qContent,
            options: finalOptions,
            answer_key: qAnswer,
            rubrics: finalRubrics,
            subject: rowSubject,
            class_level: rowClassLevel,
            ai_grading: isAi,
          });
          successCount++;
        } catch (err: any) {
          failed.push({
            row: rowIndex,
            sheet,
            identifier: qContent,
            reason: err?.message || "Gagal menyimpan ke server."
          });
        }

        setImportProgress({ current: i + 1, total: jobs.length });
      }

      setImportReport({ success: successCount, skipped, failed });
      fetchQuestions();
      showToast({
        type: "success",
        title: "Impor Selesai",
        message: `Berhasil mengimpor ${successCount} soal baru.`,
      });
    } catch (err: any) {
      showToast({ type: "error", title: "Impor Gagal", message: err?.message || "Format file tidak valid." });
    } finally {
      setIsImporting(false);
      setImportProgress(null);
    }
  };

  // Collect all distinct subjects present in the bank questions
  const distinctBankSubjects = Array.from(
    new Set([...subjectsTaught, ...questions.map((q) => q.subject).filter((s): s is string => Boolean(s))])
  );

  const filteredQuestions = questions.filter((q) => {
    const matchesSearch =
      q.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      q.answer_key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (q.subject && q.subject.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesType = filterType ? q.type === filterType : true;
    const matchesSubject = filterSubject ? q.subject === filterSubject : true;
    const matchesClassLevel = filterClassLevel ? q.class_level === filterClassLevel : true;
    return matchesSearch && matchesType && matchesSubject && matchesClassLevel;
  });

  const getQuestionTypeBadge = (t: QuestionType) => {
    switch (t) {
      case "PG":
        return <Badge variant="emerald">Pilihan Ganda</Badge>;
      case "IS":
        return <Badge variant="indigo">Isian Singkat</Badge>;
      case "ES":
        return <Badge variant="amber">Essay / Uraian</Badge>;
    }
  };

  const hasAssignedSubjects = subjectsTaught.length > 0;

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-indigo-400" />
            Bank Soal Pribadi
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Simpan, kelola, dan susun butir-butir soal ujian Anda berdasarkan mata pelajaran dan tingkat kelas.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="md"
            leftIcon={<Upload className="w-4 h-4 text-amber-400" />}
            onClick={() => {
              setImportReport(null);
              setIsImportModalOpen(true);
            }}
          >
            Impor XLSX
          </Button>
          <Button
            variant="primary"
            size="md"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={() => setIsAddChoiceOpen(true)}
          >
            Buat Soal Baru
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="flex items-center gap-2 flex-1 w-full md:max-w-md">
          <div className="flex-1">
            <Input
              placeholder="Cari konten pertanyaan atau kunci jawaban..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>
          <Button
            variant="ghost"
            size="md"
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={fetchQuestions}
            isLoading={isLoading}
            className="shrink-0"
          >
            Refresh
          </Button>
        </div>

        <div className="flex gap-2 w-full md:w-auto flex-wrap">
          {/* Subject Filter */}
          <div className="w-44">
            <Select
              options={[
                { value: "", label: "Semua Mapel" },
                ...distinctBankSubjects.map((s) => ({ value: s, label: s })),
              ]}
              value={filterSubject}
              onChange={(e) => setFilterSubject(e.target.value)}
            />
          </div>
          {/* Class Level Filter */}
          <div className="w-40">
            <Select
              options={[
                { value: "", label: "Semua Tingkat" },
                ...getGradeOptionsForSchool(user?.school_level_code),
              ]}
              value={filterClassLevel}
              onChange={(e) => setFilterClassLevel(e.target.value)}
            />
          </div>
          {/* Type Filter */}
          <div className="w-36">
            <Select
              options={[
                { value: "", label: "Semua Tipe" },
                { value: "PG", label: "Pilihan Ganda" },
                { value: "IS", label: "Isian Singkat" },
                { value: "ES", label: "Essay" },
              ]}
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Questions list */}
      <div className="glass-panel p-6 space-y-4">
        <h3 className="font-semibold text-slate-300 flex items-center gap-2 text-sm">
          <FileText className="w-4 h-4 text-indigo-400" />
          <span>Daftar Butir Soal ({filteredQuestions.length})</span>
        </h3>

        {isLoading ? (
          <p className="text-center text-xs text-slate-500 py-10">Memuat bank soal...</p>
        ) : filteredQuestions.length === 0 ? (
          <p className="text-center text-xs text-slate-500 py-10">
            {searchQuery || filterType || filterSubject
              ? "Tidak ada soal yang memenuhi kriteria pencarian/filter."
              : "Bank soal Anda masih kosong. Klik 'Buat Soal Baru' untuk memulai."}
          </p>
        ) : (
          <div className="space-y-3">
            {filteredQuestions.map((q) => {
              const isExpanded = expandedQuestionId === q.id;
              return (
                <div
                  key={q.id}
                  className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition-all duration-200"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded bg-slate-800/80 border border-slate-700 flex items-center justify-center text-[10px] font-mono text-slate-400 mt-0.5 shrink-0">
                        {q.id}
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {getQuestionTypeBadge(q.type)}
                          {q.subject && (
                            <Badge variant="indigo" size="sm">
                              {q.subject}
                            </Badge>
                          )}
                          <Badge variant="indigo" size="sm">
                            Tingkat {q.class_level || "X"}
                          </Badge>
                          {q.type === "ES" && (
                            <Badge variant={q.ai_grading ? "emerald" : "indigo"} size="sm">
                              {q.ai_grading ? "⚡ AI GRADING ACTIVE" : "MANUAL GRADING"}
                            </Badge>
                          )}
                          <span className="text-[10px] text-slate-500 font-mono">
                            Dibuat: {q.created_at ? new Date(q.created_at).toLocaleDateString("id-ID") : "—"}
                          </span>
                        </div>
                        <LaTeXText
                          content={q.content}
                          className="text-sm font-semibold text-slate-200 leading-relaxed mt-2.5 break-words"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        onClick={() => setExpandedQuestionId(isExpanded ? null : q.id)}
                      >
                        Detail
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Edit2 className="w-3.5 h-3.5" />}
                        onClick={() => handleOpenEdit(q)}
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                        onClick={() => handleDelete(q.id)}
                      />
                    </div>
                  </div>

                  {/* Expanded Detail Panel */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-slate-800 space-y-3.5 animate-fade-in text-xs">
                      {/* Options for Multiple Choice */}
                      {q.type === "PG" && q.options && (
                        <div className="space-y-1.5 bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                          <span className="font-semibold text-slate-400 block mb-1">Opsi Jawaban:</span>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {q.options.map((opt, i) => {
                              const isAnswer = opt === q.answer_key;
                              return (
                                <div
                                  key={opt}
                                  className={`p-2 rounded-lg border flex items-center gap-2 ${
                                    isAnswer
                                      ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-300 font-medium"
                                      : "bg-slate-900 border-slate-800 text-slate-400"
                                  }`}
                                >
                                  <div
                                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                                      isAnswer
                                        ? "bg-emerald-500/20 text-emerald-400"
                                        : "bg-slate-800 text-slate-500"
                                    }`}
                                  >
                                    {String.fromCharCode(65 + i)}
                                  </div>
                                  <LaTeXText content={opt} inline className="truncate" />
                                  {isAnswer && <CheckCircle className="w-3.5 h-3.5 ml-auto text-emerald-400 shrink-0" />}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Answer Key block */}
                      <div className="flex flex-col sm:flex-row gap-2 items-start justify-between bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                        <div>
                          <span className="font-semibold text-slate-400 block mb-1">Kunci Jawaban Resmi:</span>
                          <p className="font-mono text-indigo-300 font-semibold break-all bg-slate-900/60 py-1.5 px-3 rounded-lg border border-slate-800 mt-1 inline-block">
                            {q.answer_key}
                          </p>
                        </div>
                      </div>

                      {/* Rubrics (For Essay Questions) */}
                      {q.type === "ES" && (
                        <div className="space-y-2 bg-slate-950/40 p-3 rounded-lg border border-slate-900">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-400 block">Rubrik Penilaian & Bobot Persentase:</span>
                            {q.ai_grading && <Badge variant="indigo">⚡ AI Grading Active</Badge>}
                          </div>
                          {q.rubrics && q.rubrics.length > 0 ? (
                            <div className="space-y-1.5 mt-1">
                              {q.rubrics.map((r: any, i: number) => (
                                <div
                                  key={i}
                                  className="flex justify-between items-center p-2 rounded-lg bg-slate-900 border border-slate-800"
                                >
                                  <span className="text-slate-300 font-medium">{r.criteria || r.text || "Kriteria"}</span>
                                  <Badge variant="indigo">Bobot: {r.max_score || r.weight || 0}%</Badge>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-slate-400 text-xs italic">Belum ada kriteria rubrik terdaftar.</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Choice Add Data Modal */}
      <AddDataChoiceModal
        isOpen={isAddChoiceOpen}
        onClose={() => setIsAddChoiceOpen(false)}
        entityName="Soal Bank Soal"
        onSelectManual={() => {
          setIsAddChoiceOpen(false);
          handleOpenAdd();
        }}
        onDownloadTemplate={handleDownloadTemplate}
        onImportXlsx={async (_file: File) => {
          // QuestionBank uses its own import modal (with subject selection); redirect there
          setIsAddChoiceOpen(false);
          setImportReport(null);
          setIsImportModalOpen(true);
        }}
      />

      {/* Add / Edit Question Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title={editingQuestion ? "Edit Soal" : "Buat Soal Baru"}
        maxWidth="lg"
      >
        <form onSubmit={handleSubmit} className="space-y-5">
          {!hasAssignedSubjects && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-200">
                <span className="font-bold block mb-0.5">Belum Ada Mata Pelajaran yang Di-Assign</span>
                Akun guru Anda belum memiliki mata pelajaran ampu yang di-assign oleh Admin Sekolah. Silakan hubungi Admin Sekolah untuk menambahkan mata pelajaran ke profil guru Anda.
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <Select
                label="Tipe Soal"
                options={[
                  { value: "PG", label: "Pilihan Ganda" },
                  { value: "IS", label: "Isian Singkat" },
                  { value: "ES", label: "Essay (Uraian)" },
                ]}
                value={type}
                onChange={(e) => setType(e.target.value as QuestionType)}
                disabled={!!editingQuestion}
              />
            </div>
            <div>
              <Select
                label="Mata Pelajaran (Subject)"
                placeholder={hasAssignedSubjects ? "-- Pilih Mapel --" : "Belum ada mapel"}
                options={assignedSubjectOptions}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                disabled={!hasAssignedSubjects}
                required
              />
            </div>
            <div>
              <Select
                label="Tingkat Kelas"
                options={getGradeOptionsForSchool(user?.school_level_code)}
                value={classLevel}
                onChange={(e) => setClassLevel(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-semibold text-slate-300 block">
                Pertanyaan / Soal (Wajib)
              </label>
              <input
                type="file"
                ref={questionImgInputRef}
                className="hidden"
                accept="image/*"
                onChange={handleUploadImageToContent}
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                leftIcon={<Image className="w-3.5 h-3.5 text-indigo-400" />}
                onClick={() => questionImgInputRef.current?.click()}
                isLoading={isUploadingImage}
              >
                🖼️ Sisipkan Gambar Soal
              </Button>
            </div>
            <textarea
              className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 min-h-[100px]"
              placeholder="Ketikkan pertanyaan di sini..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
            />
          </div>

          {/* Multiple Choice Options Builder (Max 6 options) */}
          {type === "PG" && (
            <div className="space-y-2 bg-slate-950/40 p-4 rounded-xl border border-slate-900">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold text-slate-300">Pilihan Opsi Jawaban (Min 2 Opsi, Max 6)</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  leftIcon={<Plus className="w-3.5 h-3.5" />}
                  onClick={handleAddOptionField}
                  disabled={options.length >= 6}
                >
                  Tambah Opsi
                </Button>
              </div>

              <div className="space-y-2">
                {options.map((opt, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <div className="w-6 h-6 rounded-full bg-slate-800 text-xs font-bold text-slate-400 flex items-center justify-center shrink-0">
                      {String.fromCharCode(65 + idx)}
                    </div>
                    <div className="flex-1">
                      <Input
                        placeholder={`Ketikkan teks opsi ${String.fromCharCode(65 + idx)} ${idx < 2 ? "(Wajib)" : "(Opsional)"}`}
                        value={opt}
                        onChange={(e) => handleOptionChange(idx, e.target.value)}
                        required={idx < 2}
                      />
                    </div>
                    <input
                      type="file"
                      id={`opt-img-input-${idx}`}
                      className="hidden"
                      accept="image/*"
                      onChange={(e) => handleUploadImageToOption(idx, e)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      leftIcon={<Image className="w-3.5 h-3.5 text-indigo-400" />}
                      onClick={() => document.getElementById(`opt-img-input-${idx}`)?.click()}
                      title={`Sisipkan gambar ke Opsi ${String.fromCharCode(65 + idx)}`}
                    />
                    {options.length > 2 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                        onClick={() => handleRemoveOptionField(idx)}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Official Answer Key */}
          {type === "PG" ? (
            <div>
              <Select
                label="Kunci Jawaban Resmi (Pilih dari Opsi di atas)"
                placeholder="-- Pilih Salah Satu Opsi Sebagai Kunci --"
                options={options.map((opt) => opt.trim()).filter(Boolean).map((opt) => ({ value: opt, label: opt }))}
                value={answerKey}
                onChange={(e) => setAnswerKey(e.target.value)}
                required
              />
            </div>
          ) : (
            <div>
              <Input
                label="Kunci Jawaban Resmi / Pedoman Jawaban"
                placeholder={type === "IS" ? "Ketikkan kata/frasa kunci jawaban persis..." : "Ketikkan inti ringkasan jawaban benar..."}
                value={answerKey}
                onChange={(e) => setAnswerKey(e.target.value)}
                required
              />
            </div>
          )}

          {/* Essay AI Rubric Generator & Rubric Editor */}
          {type === "ES" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                  <span className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    Generate Rubrik Penilaian dengan AI
                  </span>
                  <p className="text-[11px] text-slate-300 mt-0.5">
                    Otomatis buatkan kriteria rubrik & persentase bobot dari Kunci Jawaban. Hasil generat AI tetap dapat Anda edit secara bebas di bawah.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  isLoading={isGeneratingAiRubric}
                  disabled={!content.trim() || !answerKey.trim()}
                  onClick={handleGenerateAiRubric}
                  leftIcon={<Sparkles className="w-3.5 h-3.5 text-amber-400" />}
                  className="shrink-0"
                >
                  {rubrics.length > 0 && aiGrading ? "Re-Generate Rubrik AI" : "Generate Rubrik AI"}
                </Button>
              </div>

              <div className="space-y-3 bg-slate-950/40 p-4 rounded-xl border border-slate-900">
                <div className="flex justify-between items-center mb-1">
                  <div>
                    <span className="text-xs font-bold text-slate-200 block">Rubrik & Bobot Penilaian Essay</span>
                    <p className="text-[10px] text-slate-400">
                      Tentukan kriteria dan bobot (%) penilaian. AI akan menggunakan rubrik ini untuk mengoreksi jawaban siswa pada semua jadwal ujian.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    leftIcon={<Plus className="w-3.5 h-3.5" />}
                    onClick={handleAddRubricField}
                    disabled={rubrics.length >= 5}
                  >
                    Tambah Rubrik
                  </Button>
                </div>

                <div className="space-y-2">
                  {rubrics.map((r, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <div className="flex-1">
                        <Input
                          placeholder={`Kriteria Rubrik #${idx + 1}`}
                          value={r.criteria}
                          onChange={(e) => handleRubricChange(idx, "criteria", e.target.value)}
                          required
                        />
                      </div>
                      <div className="w-32">
                        <Input
                          type="number"
                          min="1"
                          max="100"
                          placeholder="Bobot (%)"
                          value={r.max_score}
                          onChange={(e) => handleRubricChange(idx, "max_score", parseInt(e.target.value, 10) || 0)}
                          required
                        />
                      </div>
                      {rubrics.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                          onClick={() => handleRemoveRubricField(idx)}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsAddModalOpen(false)}
            >
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              leftIcon={<Plus className="w-4 h-4" />}
              isLoading={isSubmitting}
              disabled={!hasAssignedSubjects}
            >
              {editingQuestion ? "Simpan Perubahan" : "Tambah ke Bank Soal"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Import XLSX Modal */}
      <Modal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        title="Impor Bank Soal dari Excel (.xlsx)"
        maxWidth="lg"
      >
        <div className="space-y-5">
          <div className="flex justify-between items-center bg-slate-900/60 p-4 rounded-xl border border-slate-800">
            <div>
              <h4 className="text-xs font-bold text-slate-200">Template Multi-Sheet Resmi</h4>
              <p className="text-[10px] text-slate-400">Sheet terpisah untuk PG (hingga Opsi F), Isian Singkat, dan Essay.</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<Download className="w-4 h-4 text-indigo-400" />}
              onClick={handleDownloadTemplate}
            >
              Unduh Template
            </Button>
          </div>

          <div className="space-y-4">
            {!hasAssignedSubjects && (
              <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-200">
                  <span className="font-bold block mb-0.5">Belum Ada Mata Pelajaran yang Di-Assign</span>
                  Akun guru Anda belum memiliki mata pelajaran ampu yang di-assign oleh Admin Sekolah.
                </div>
              </div>
            )}

            <Select
              label="Mata Pelajaran Soal Impor"
              placeholder={hasAssignedSubjects ? "-- Pilih Mata Pelajaran --" : "Belum ada mapel di-assign"}
              options={assignedSubjectOptions}
              value={importSubject}
              onChange={(e) => setImportSubject(e.target.value)}
              disabled={!hasAssignedSubjects}
              required
            />

            <div
              className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors relative ${
                hasAssignedSubjects
                  ? "border-slate-700/60 hover:border-indigo-500/50 cursor-pointer"
                  : "border-slate-800 opacity-50 cursor-not-allowed"
              }`}
              onClick={() => {
                if (hasAssignedSubjects) fileInputRef.current?.click();
              }}
            >
              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept=".xlsx, .xls"
                onChange={handleFileImport}
                disabled={isImporting || !hasAssignedSubjects}
              />
              {isImporting ? (
                <div className="space-y-3">
                  <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto" />
                  <p className="text-xs text-slate-300 font-semibold">Sedang mengimpor...</p>
                  {importProgress && (
                    <div className="text-[10px] text-slate-500">
                      Proses: {importProgress.current} / {importProgress.total} soal
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <FileSpreadsheet className="w-8 h-8 text-emerald-400 mx-auto" />
                  <p className="text-xs text-slate-300 font-semibold">Klik untuk memilih file Excel (.xlsx)</p>
                  <p className="text-[10px] text-slate-500">Pastikan lembar sheet diisi sesuai format template.</p>
                </div>
              )}
            </div>
          </div>

          {/* Import report results */}
          {importReport && (
            <div className="space-y-3.5 bg-slate-950/40 p-4 rounded-xl border border-slate-900 text-xs">
              <h4 className="font-bold text-slate-300 border-b border-slate-800 pb-1.5">Laporan Impor</h4>
              
              <div className="flex gap-4 font-semibold text-slate-400">
                <span>Sukses: <strong className="text-emerald-400">{importReport.success} Soal</strong></span>
                <span>Dilewati (Sudah Ada): <strong className="text-indigo-400">{importReport.skipped.length} Soal</strong></span>
                <span>Gagal: <strong className="text-red-400">{importReport.failed.length} Soal</strong></span>
              </div>

              {/* Skipped rows check */}
              {importReport.skipped.length > 0 && (
                <div className="space-y-1 bg-indigo-950/10 p-2.5 rounded-lg border border-indigo-500/20 max-h-40 overflow-y-auto">
                  <span className="font-bold text-indigo-300 block mb-1">Daftar Baris Dilewati (Sudah ada di Bank Soal):</span>
                  {importReport.skipped.map((s, idx) => (
                    <div key={idx} className="text-[10px] text-slate-400">
                      ● [Sheet: {s.sheet}] Baris #{s.row}: <span className="font-mono text-indigo-200">"{s.identifier.substring(0, 40)}..."</span> - {s.reason}
                    </div>
                  ))}
                </div>
              )}

              {/* Failed rows check */}
              {importReport.failed.length > 0 && (
                <div className="space-y-1 bg-red-950/10 p-2.5 rounded-lg border border-red-500/20 max-h-40 overflow-y-auto">
                  <span className="font-bold text-red-300 block mb-1 text-red-400">Daftar Baris Gagal (Ditolak Validasi):</span>
                  {importReport.failed.map((f, idx) => (
                    <div key={idx} className="text-[10px] text-slate-400">
                      ● [Sheet: {f.sheet}] Baris #{f.row}: <span className="font-mono text-red-300">"{f.identifier.substring(0, 40)}..."</span> - <strong className="text-red-400">{f.reason}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end pt-3 border-t border-slate-800">
            <Button variant="ghost" onClick={() => setIsImportModalOpen(false)}>
              Selesai & Tutup
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Custom Confirmation MessageBox: Delete Question ── */}
      <MessageBox
        isOpen={deletingQuestionId !== null}
        onClose={() => setDeletingQuestionId(null)}
        type="warning"
        title="Hapus Soal dari Bank Soal"
        message={
          <div>
            Apakah Anda yakin ingin menghapus <strong>Soal #{deletingQuestionId}</strong> secara permanen dari Bank Soal?
            <p className="text-[11px] text-slate-400 mt-1">
              Tindakan ini tidak dapat dibatalkan. Soal yang terhapus dari bank soal tidak lagi dapat digunakan untuk paket soal baru.
            </p>
          </div>
        }
        confirmText="Hapus Soal"
        cancelText="Batal"
        onConfirm={handleConfirmDeleteQuestion}
        isLoading={isDeletingQuestion}
        confirmVariant="danger"
      />
    </div>
  );
}
