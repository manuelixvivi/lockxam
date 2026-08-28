import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  FolderOpen,
  ArrowLeft,
  Plus,
  ArrowUp,
  ArrowDown,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Search,
  Link,
  PlusCircle,
  Upload,
  Download,
  Loader2,
  Edit2,
  Trash2,
  RefreshCw,
  FileSpreadsheet,
  Sparkles,
  Image,
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
import type { QuestionPackageDetail, Question, QuestionType, PackageQuestion } from "../../api/teacherContent";
import { downloadMultiSheetXlsxTemplate, readMultiSheetXlsxFile } from "../../utils/xlsx";
import { LaTeXText } from "../../components/ui/LaTeXText";
import { getGradeOptionsForSchool, normalizeRubricWeights } from "../../utils/gradeLevels";

interface QuestionPackageDetailViewProps {
  packageId: number;
  onBack: () => void;
  onNavigate?: (href: string) => void;
}

export function QuestionPackageDetailView({ packageId, onBack }: QuestionPackageDetailViewProps) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [detail, setDetail] = useState<QuestionPackageDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Bank search/add states
  const [isBankModalOpen, setIsBankModalOpen] = useState(false);
  const [bankQuestions, setBankQuestions] = useState<Question[]>([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [bankSearch, setBankSearch] = useState("");
  const [bankFilterType, setBankFilterType] = useState("");
  const [bankFilterClassLevel, setBankFilterClassLevel] = useState("");
  const [bankStep, setBankStep] = useState<1 | 2>(1);
  const [selectedBankQIds, setSelectedBankQIds] = useState<number[]>([]);
  const [selectedScores, setSelectedScores] = useState<Record<number, string>>({});
  const [batchScoreInput, setBatchScoreInput] = useState("10");
  const [isSubmittingBulkBank, setIsSubmittingBulkBank] = useState(false);

  // Create & Add New Question Inline
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newType, setNewType] = useState<QuestionType>("PG");
  const [newContent, setNewContent] = useState("");
  const [newAnswerKey, setNewAnswerKey] = useState("");
  const [newScore, setNewScore] = useState("10");
  const [newAiGrading, setNewAiGrading] = useState(false);
  const [newOptions, setNewOptions] = useState<string[]>(["", "", "", ""]);
  const [newRubrics, setNewRubrics] = useState<{ criteria: string; max_score: number }[]>([
    { criteria: "Pemahaman Masalah", max_score: 50 },
    { criteria: "Langkah Penyelesaian", max_score: 50 },
  ]);
  const [isCreatingQuestion, setIsCreatingQuestion] = useState(false);
  const [isGeneratingInlineAiRubric, setIsGeneratingInlineAiRubric] = useState(false);

  const handleGenerateInlineAiRubric = async () => {
    if (!newContent.trim() || !newAnswerKey.trim()) {
      showToast({
        type: "error",
        title: "Pertanyaan & Kunci Jawaban Wajib Diisi",
        message: "Silakan isi pertanyaan dan kunci jawaban terlebih dahulu sebelum menggenerasi rubrik AI.",
      });
      return;
    }

    setIsGeneratingInlineAiRubric(true);
    try {
      const res = await teacherContentApi.generateAiRubric({
        question_text: newContent,
        answer_key: newAnswerKey,
        education_level: user?.school_level_code || "SMA",
        education_class: detail?.class_level || "Kelas 11",
      });

      if (res.status === "success" && res.rubrics && Array.isArray(res.rubrics) && res.rubrics.length > 0) {
        const generated = normalizeRubricWeights(res.rubrics, newAnswerKey);
        setNewRubrics(generated);
        setNewAiGrading(true);
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
      setIsGeneratingInlineAiRubric(false);
    }
  };

  // Image Upload State & Handlers
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const questionImgInputRef = useRef<HTMLInputElement>(null);

  const handleUploadImageToContent = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingImage(true);
    try {
      const res = await teacherContentApi.uploadQuestionImage(file);
      const imgMarkdown = `\n![Gambar Soal](${res.url})\n`;
      setNewContent((prev) => prev + imgMarkdown);
      showToast({
        type: "success",
        title: "Gambar Berhasil Diunggah",
        message: "Tag gambar telah disisipkan ke dalam teks soal.",
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Upload Gambar",
        message: err?.message || "Terjadi kesalahan saat mengunggah gambar.",
      });
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
      const imgMarkdown = ` ![Opsi](${res.url})`;
      setNewOptions((prev) => {
        const copy = [...prev];
        copy[index] = (copy[index] || "").trim() + imgMarkdown;
        return copy;
      });
      showToast({
        type: "success",
        title: "Gambar Opsi Berhasil Diunggah",
        message: `Gambar disisipkan ke Opsi ${String.fromCharCode(65 + index)}.`,
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Upload Gambar",
        message: err?.message || "Terjadi kesalahan saat mengunggah gambar.",
      });
    } finally {
      setIsUploadingImage(false);
      e.target.value = "";
    }
  };

  // Edit Rubrics for Essay Questions Inline
  const [editingQuestion, setEditingQuestion] = useState<PackageQuestion | null>(null);
  const [isEditRubricModalOpen, setIsEditRubricModalOpen] = useState(false);
  const [editRubrics, setEditRubrics] = useState<{ criteria: string; max_score: number }[]>([]);
  const [isUpdatingRubrics, setIsUpdatingRubrics] = useState(false);

  // Replace / Swap Question state
  const [replacingQuestion, setReplacingQuestion] = useState<PackageQuestion | null>(null);
  const [isReplaceModalOpen, setIsReplaceModalOpen] = useState(false);
  const [replaceSearch, setReplaceSearch] = useState("");
  const [selectedNewQId, setSelectedNewQId] = useState<number | null>(null);
  const [replaceScore, setReplaceScore] = useState<string>("10");
  const [isSubmittingReplace, setIsSubmittingReplace] = useState(false);

  // Import states
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState<{ current: number; total: number } | null>(null);
  const [importReport, setImportReport] = useState<{
    success: number;
    skipped: { row: number; sheet: string; identifier: string; reason: string }[];
    failed: { row: number; sheet: string; identifier: string; reason: string }[];
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDetail = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await teacherContentApi.getPackageDetail(packageId);
      setDetail(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal memuat detail paket",
        message: err?.message || "Terjadi kesalahan.",
      });
      onBack();
    } finally {
      setIsLoading(false);
    }
  }, [packageId, onBack, showToast]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const loadBank = async () => {
    if (!detail) return;
    setBankLoading(true);
    try {
      const data = await teacherContentApi.listQuestions(detail.subject);
      setBankQuestions(data);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memuat bank soal", message: err?.message });
    } finally {
      setBankLoading(false);
    }
  };

  const handleOpenBank = () => {
    loadBank();
    setBankStep(1);
    setSelectedBankQIds([]);
    setSelectedScores({});
    setBatchScoreInput("10");
    setBankFilterClassLevel(detail?.class_level || "");
    setIsBankModalOpen(true);
  };

  const handleToggleSelectBankQ = (qId: number) => {
    const q = bankQuestions.find((b) => b.id === qId);
    if (!q) return;

    const isSelected = selectedBankQIds.includes(qId);
    if (isSelected) {
      setSelectedBankQIds((prev) => prev.filter((id) => id !== qId));
      return;
    }

    // Calculate quota limits for each question type
    const targetPG = detail?.target_counts?.PG || 0;
    const targetIS = detail?.target_counts?.IS || 0;
    const targetES = detail?.target_counts?.ES || 0;

    const actualPG = getActualCount("PG");
    const actualIS = getActualCount("IS");
    const actualES = getActualCount("ES");

    const remPG = Math.max(0, targetPG - actualPG);
    const remIS = Math.max(0, targetIS - actualIS);
    const remES = Math.max(0, targetES - actualES);

    const selPG = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "PG"
    ).length;
    const selIS = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "IS"
    ).length;
    const selES = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "ES"
    ).length;

    if (q.type === "PG" && selPG >= remPG) {
      showToast({
        type: "warning",
        title: "Kuota PG Terpenuhi",
        message: remPG > 0
          ? `Sisa kuota Pilihan Ganda (PG) hanya tersisa ${remPG} soal.`
          : `Kuota Pilihan Ganda (PG) untuk paket ini sudah terpenuhi (${actualPG}/${targetPG}).`,
      });
      return;
    }

    if (q.type === "IS" && selIS >= remIS) {
      showToast({
        type: "warning",
        title: "Kuota IS Terpenuhi",
        message: remIS > 0
          ? `Sisa kuota Isian Singkat (IS) hanya tersisa ${remIS} soal.`
          : `Kuota Isian Singkat (IS) untuk paket ini sudah terpenuhi (${actualIS}/${targetIS}).`,
      });
      return;
    }

    if (q.type === "ES" && selES >= remES) {
      showToast({
        type: "warning",
        title: "Kuota ES Terpenuhi",
        message: remES > 0
          ? `Sisa kuota Essay (ES) hanya tersisa ${remES} soal.`
          : `Kuota Essay (ES) untuk paket ini sudah terpenuhi (${actualES}/${targetES}).`,
      });
      return;
    }

    setSelectedBankQIds((prev) => [...prev, qId]);
  };

  const handleToggleSelectAllFiltered = (filteredList: Question[]) => {
    const availableIds = filteredList.map((q) => q.id);
    const allSelected = availableIds.length > 0 && availableIds.every((id) => selectedBankQIds.includes(id));

    if (allSelected) {
      setSelectedBankQIds((prev) => prev.filter((id) => !availableIds.includes(id)));
      return;
    }

    const targetPG = detail?.target_counts?.PG || 0;
    const targetIS = detail?.target_counts?.IS || 0;
    const targetES = detail?.target_counts?.ES || 0;

    const actualPG = getActualCount("PG");
    const actualIS = getActualCount("IS");
    const actualES = getActualCount("ES");

    const remPG = Math.max(0, targetPG - actualPG);
    const remIS = Math.max(0, targetIS - actualIS);
    const remES = Math.max(0, targetES - actualES);

    let selPG = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "PG"
    ).length;
    let selIS = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "IS"
    ).length;
    let selES = selectedBankQIds.filter(
      (id) => bankQuestions.find((b) => b.id === id)?.type === "ES"
    ).length;

    const newSelections = [...selectedBankQIds];
    let addedCount = 0;
    let skippedCount = 0;

    for (const q of filteredList) {
      if (newSelections.includes(q.id)) continue;

      if (q.type === "PG") {
        if (selPG < remPG) {
          newSelections.push(q.id);
          selPG++;
          addedCount++;
        } else {
          skippedCount++;
        }
      } else if (q.type === "IS") {
        if (selIS < remIS) {
          newSelections.push(q.id);
          selIS++;
          addedCount++;
        } else {
          skippedCount++;
        }
      } else if (q.type === "ES") {
        if (selES < remES) {
          newSelections.push(q.id);
          selES++;
          addedCount++;
        } else {
          skippedCount++;
        }
      }
    }

    setSelectedBankQIds(newSelections);

    if (skippedCount > 0) {
      showToast({
        type: "info",
        title: "Pemilihan Sesuai Kuota Paket",
        message: `Dipilih ${addedCount} soal. ${skippedCount} soal dilewati karena kuota target jenis soal pada paket telah terpenuhi.`,
      });
    }
  };

  const handleProceedToScores = () => {
    if (selectedBankQIds.length === 0) {
      showToast({ type: "warning", title: "Pilih Soal", message: "Harap pilih minimal 1 soal dari Bank Soal." });
      return;
    }

    const initialScores = { ...selectedScores };
    selectedBankQIds.forEach((id) => {
      if (!initialScores[id]) {
        initialScores[id] = batchScoreInput || "10";
      }
    });
    setSelectedScores(initialScores);
    setBankStep(2);
  };

  const handleApplyBatchScore = () => {
    const val = batchScoreInput.trim();
    if (!val || parseFloat(val) <= 0) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Masukkan bobot skor positif." });
      return;
    }
    const updatedScores = { ...selectedScores };
    selectedBankQIds.forEach((id) => {
      updatedScores[id] = val;
    });
    setSelectedScores(updatedScores);
    showToast({ type: "info", title: "Skor Diperbarui", message: `Skor ${val} diterapkan ke seluruh ${selectedBankQIds.length} soal.` });
  };

  const handleConfirmAddBulkFromBank = async () => {
    if (!detail || selectedBankQIds.length === 0) return;

    for (const qId of selectedBankQIds) {
      const scoreVal = parseFloat(selectedScores[qId] || "0");
      if (isNaN(scoreVal) || scoreVal <= 0) {
        showToast({
          type: "warning",
          title: "Validasi Gagal",
          message: "Setiap soal terpilih wajib memiliki bobot skor positif (> 0).",
        });
        return;
      }
    }

    setIsSubmittingBulkBank(true);
    let successCount = 0;
    const failedList: string[] = [];

    try {
      for (const qId of selectedBankQIds) {
        const scoreVal = parseFloat(selectedScores[qId] || "10");
        try {
          await teacherContentApi.addQuestionToPackage(detail.id, qId, scoreVal);
          successCount++;
        } catch (err: any) {
          const qObj = bankQuestions.find((b) => b.id === qId);
          failedList.push(qObj ? `#${qObj.id} (${qObj.type})` : `#${qId}`);
        }
      }

      const updatedData = await teacherContentApi.getPackageDetail(detail.id);
      setDetail(updatedData);

      if (failedList.length === 0) {
        showToast({
          type: "success",
          title: "Berhasil Menambahkan Soal",
          message: `Berhasil menambahkan ${successCount} soal dari Bank Soal ke paket ujian.`,
        });
        setIsBankModalOpen(false);
      } else {
        showToast({
          type: "warning",
          title: "Proses Selesai Ditambahkan",
          message: `${successCount} soal berhasil ditambahkan. ${failedList.length} soal gagal (${failedList.join(", ")}), mungkin limit target jenis soal telah terpenuhi.`,
        });
        setIsBankModalOpen(false);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menambahkan Soal",
        message: err?.message || "Terjadi kesalahan saat menyematkan soal.",
      });
    } finally {
      setIsSubmittingBulkBank(false);
    }
  };

  const handleOpenReplaceModal = (item: PackageQuestion) => {
    loadBank();
    setReplacingQuestion(item);
    setSelectedNewQId(null);
    setReplaceSearch("");
    setReplaceScore(item.score.toString());
    setIsReplaceModalOpen(true);
  };

  const handleConfirmReplace = async () => {
    if (!detail || !replacingQuestion || selectedNewQId === null) return;
    const sVal = parseFloat(replaceScore) || replacingQuestion.score;

    setIsSubmittingReplace(true);
    try {
      const updated = await teacherContentApi.replaceQuestionInPackage(
        detail.id,
        replacingQuestion.id,
        selectedNewQId,
        sVal
      );
      setDetail(updated);
      setIsReplaceModalOpen(false);
      setReplacingQuestion(null);
      setSelectedNewQId(null);
      showToast({
        type: "success",
        title: "Penggantian Soal Berhasil",
        message: `Soal ID #${replacingQuestion.id} berhasil digantikan dengan Soal ID #${selectedNewQId}.`,
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengganti Soal",
        message: err?.message || "Terjadi kesalahan saat mengganti soal.",
      });
    } finally {
      setIsSubmittingReplace(false);
    }
  };

  // Custom MessageBox Confirmation States
  const [removingQuestionItem, setRemovingQuestionItem] = useState<PackageQuestion | null>(null);
  const [isRemovingFromPackage, setIsRemovingFromPackage] = useState(false);

  const [isRevertDraftConfirmOpen, setIsRevertDraftConfirmOpen] = useState(false);
  const [isRevertingDraft, setIsRevertingDraft] = useState(false);

  const handleOpenRemoveQuestionConfirm = (item: PackageQuestion) => {
    setRemovingQuestionItem(item);
  };

  const handleConfirmRemoveQuestion = async () => {
    if (!detail || !removingQuestionItem) return;
    setIsRemovingFromPackage(true);
    try {
      const updated = await teacherContentApi.removeQuestionFromPackage(detail.id, removingQuestionItem.id);
      setDetail(updated);
      setRemovingQuestionItem(null);
      showToast({
        type: "success",
        title: "Soal Dikeluarkan",
        message: `Soal #${removingQuestionItem.id} berhasil dikeluarkan dari paket ini.`,
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengeluarkan Soal",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsRemovingFromPackage(false);
    }
  };

  const handleConfirmRevertDraft = async () => {
    if (!detail) return;
    setIsRevertingDraft(true);
    try {
      const updated = await teacherContentApi.revertPackageToDraft(detail.id);
      setDetail(updated);
      setIsRevertDraftConfirmOpen(false);
      showToast({
        type: "success",
        title: "Status Dibatalkan",
        message: "Paket soal kini berstatus DRAFT dan dapat diubah kembali.",
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengubah Status",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsRevertingDraft(false);
    }
  };

  const [isPublishingPackage, setIsPublishingPackage] = useState(false);

  const handlePublishPackage = async () => {
    if (!detail) return;
    setIsPublishingPackage(true);
    try {
      const updated = await teacherContentApi.publishPackage(detail.id);
      setDetail(updated);
      showToast({
        type: "success",
        title: "Paket Soal Berhasil Dipost",
        message: "Status paket soal kini READY (Siap Ujian) dan dapat dijadwalkan oleh admin.",
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mem-Post Paket Soal",
        message: err?.message || "Terjadi kesalahan saat mem-post paket soal.",
      });
    } finally {
      setIsPublishingPackage(false);
    }
  };

  const handleCreateAndAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    if (!newContent.trim() || !newAnswerKey.trim()) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Pertanyaan dan Kunci Jawaban wajib diisi." });
      return;
    }

    const scoreVal = parseFloat(newScore) || 0.0;
    if (scoreVal <= 0) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Skor soal harus positif." });
      return;
    }

    let finalOptions: string[] | null = null;
    if (newType === "PG") {
      const filteredOptions = newOptions.map((o) => o.trim()).filter(Boolean);
      if (filteredOptions.length < 2) {
        showToast({ type: "warning", title: "Validasi Gagal", message: "Soal Pilihan Ganda minimal membutuhkan 2 opsi." });
        return;
      }
      if (filteredOptions.length > 6) {
        showToast({ type: "warning", title: "Validasi Gagal", message: "Soal Pilihan Ganda maksimal 6 opsi (A-F)." });
        return;
      }
      finalOptions = filteredOptions;
      if (!finalOptions.includes(newAnswerKey.trim())) {
        showToast({
          type: "warning",
          title: "Validasi Gagal",
          message: "Kunci jawaban harus sama persis dengan salah satu opsi pilihan ganda.",
        });
        return;
      }
    }

    let finalRubrics = newType === "ES" ? newRubrics : [];
    if (newType === "ES" && !newAiGrading) {
      const validRubrics = newRubrics.filter((r) => r.criteria.trim() && r.max_score > 0);
      if (validRubrics.length === 0) {
        showToast({ type: "warning", title: "Validasi Gagal", message: "Rubrik manual wajib memiliki minimal 1 kriteria." });
        return;
      }
      finalRubrics = validRubrics;
    }

    setIsCreatingQuestion(true);
    try {
      // 1. Create in bank with package's subject
      const newQ = await teacherContentApi.createQuestion({
        type: newType,
        content: newContent.trim(),
        options: finalOptions,
        answer_key: newAnswerKey.trim(),
        rubrics: finalRubrics,
        subject: detail.subject || "",
        ai_grading: newType === "ES" ? newAiGrading : false,
      });

      // 2. Add to package
      const updated = await teacherContentApi.addQuestionToPackage(detail.id, newQ.id, scoreVal);
      setDetail(updated);
      showToast({ type: "success", title: "Soal baru berhasil dibuat dan dimasukkan ke paket." });
      setIsCreateModalOpen(false);
      
      // Reset form
      setNewContent("");
      setNewAnswerKey("");
      setNewScore("10");
      setNewAiGrading(false);
      setNewOptions(["", "", "", ""]);
      setNewRubrics([{ criteria: "Kriteria Utama", max_score: 10 }]);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal membuat dan menambahkan soal", message: err?.message });
    } finally {
      setIsCreatingQuestion(false);
    }
  };

  const handleOpenEditRubric = (q: PackageQuestion) => {
    setEditingQuestion(q);
    setEditRubrics(q.rubrics || []);
    setIsEditRubricModalOpen(true);
  };

  const handleSaveRubrics = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingQuestion || !detail) return;

    const validRubrics = editRubrics.filter((r) => r.criteria.trim() && r.max_score > 0);
    if (validRubrics.length === 0) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Kriteria rubrik minimal harus ada 1." });
      return;
    }

    setIsUpdatingRubrics(true);
    try {
      // Update in Question Bank
      await teacherContentApi.updateQuestion(editingQuestion.id, {
        rubrics: validRubrics,
      });
      showToast({ type: "success", title: "Rubrik penilaian berhasil diperbarui (tidak mempengaruhi riwayat ujian sebelumnya)." });
      setIsEditRubricModalOpen(false);
      fetchDetail();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memperbarui rubrik", message: err?.message });
    } finally {
      setIsUpdatingRubrics(false);
    }
  };

  const handleReorder = async (currentIndex: number, direction: "up" | "down") => {
    if (!detail) return;
    const questions = [...detail.questions];
    const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;

    if (targetIndex < 0 || targetIndex >= questions.length) return;

    // Build order map for backend reorder api
    const orderMap: Record<number, number> = {};
    questions.forEach((q, idx) => {
      if (idx === currentIndex) {
        orderMap[q.id] = targetIndex + 1;
      } else if (idx === targetIndex) {
        orderMap[q.id] = currentIndex + 1;
      } else {
        orderMap[q.id] = idx + 1;
      }
    });

    try {
      const updated = await teacherContentApi.reorderQuestions(detail.id, orderMap);
      setDetail(updated);
      showToast({ type: "success", title: "Urutan soal berhasil diperbarui." });
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal mengatur ulang urutan", message: err?.message });
    }
  };

  // Download Package Manual Import Excel Template
  const handleDownloadTemplate = () => {
    const sheets = [
      {
        name: "Pilihan Ganda",
        headers: ["Pertanyaan", "Kunci Jawaban", "Skor", "Opsi A", "Opsi B", "Opsi C", "Opsi D", "Opsi E", "Opsi F"],
        samples: [
          {
            "Pertanyaan": "Siapakah penemu lampu pijar?",
            "Kunci Jawaban": "Thomas Alva Edison",
            "Skor": "10",
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
        headers: ["Pertanyaan", "Kunci Jawaban", "Skor"],
        samples: [
          {
            "Pertanyaan": "Proses tumbuhan hijau membuat makanan sendiri dinamakan...",
            "Kunci Jawaban": "Fotosintesis",
            "Skor": "5"
          }
        ]
      },
      {
        name: "Essay",
        headers: [
          "Pertanyaan", "Kunci Jawaban", "Skor", "AI Grading (YA/TIDAK)",
          "Rubrik 1 Kriteria", "Rubrik 1 Skor Maks",
          "Rubrik 2 Kriteria", "Rubrik 2 Skor Maks",
          "Rubrik 3 Kriteria", "Rubrik 3 Skor Maks",
          "Rubrik 4 Kriteria", "Rubrik 4 Skor Maks",
          "Rubrik 5 Kriteria", "Rubrik 5 Skor Maks"
        ],
        samples: [
          {
            "Pertanyaan": "Jelaskan perbedaan antara konduksi, konveksi, dan radiasi!",
            "Kunci Jawaban": "Konduksi hantaran langsung, konveksi aliran materi, radiasi pancaran...",
            "Skor": "20",
            "AI Grading (YA/TIDAK)": "YA",
            "Rubrik 1 Kriteria": "", "Rubrik 1 Skor Maks": "",
            "Rubrik 2 Kriteria": "", "Rubrik 2 Skor Maks": "",
            "Rubrik 3 Kriteria": "", "Rubrik 3 Skor Maks": "",
            "Rubrik 4 Kriteria": "", "Rubrik 4 Skor Maks": "",
            "Rubrik 5 Kriteria": "", "Rubrik 5 Skor Maks": ""
          }
        ]
      }
    ];
    downloadMultiSheetXlsxTemplate(sheets, `Template_Manual_Paket_${detail?.name.replace(/\s+/g, "_")}`);
    showToast({ type: "success", title: "Template manual berhasil diunduh." });
  };

  // Import XLSX to Package Manual (with score column)
  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ""; // reset

    if (!detail) return;

    setIsImporting(true);
    setImportReport(null);
    setImportProgress(null);

    try {
      const sheetsData = await readMultiSheetXlsxFile(file);
      
      const skipped: { row: number; sheet: string; identifier: string; reason: string }[] = [];
      const failed: { row: number; sheet: string; identifier: string; reason: string }[] = [];
      let successCount = 0;

      // 1. Gather all questions inside Question Bank to check existing
      const bankQs = await teacherContentApi.listQuestions(detail.subject);

      // 2. Gather import jobs
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
        const qContent = (row["Pertanyaan"] || "").trim();
        const qAnswer = (row["Kunci Jawaban"] || "").trim();
        const qScore = parseFloat(row["Skor"] || "") || 0.0;

        if (!qContent) {
          failed.push({ row: rowIndex, sheet, identifier: `Baris ${rowIndex}`, reason: "Kolom Pertanyaan kosong." });
          continue;
        }
        if (!qAnswer) {
          failed.push({ row: rowIndex, sheet, identifier: qContent, reason: "Kolom Kunci Jawaban kosong." });
          continue;
        }
        if (qScore <= 0) {
          failed.push({ row: rowIndex, sheet, identifier: qContent, reason: "Kolom Skor harus angka positif (>0)." });
          continue;
        }

        // Check if question is already inside this specific package to avoid duplicates
        const alreadyInPkg = detail.questions.find(
          (pq) => pq.content.trim().toLowerCase() === qContent.toLowerCase() && pq.type === type
        );
        if (alreadyInPkg) {
          skipped.push({
            row: rowIndex,
            sheet,
            identifier: qContent,
            reason: "Soal ini sudah berada di dalam susunan paket ujian."
          });
          continue;
        }

        // Check if question exists in bank
        let targetQuestionId: number;
        const existingInBank = bankQs.find(
          (bq) => bq.content.trim().toLowerCase() === qContent.toLowerCase() && bq.type === type
        );

        if (existingInBank) {
          targetQuestionId = existingInBank.id;
        } else {
          // Parse options & rubrics to create new Question in bank
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

            if (!optA || !optB) {
              failed.push({
                row: rowIndex,
                sheet,
                identifier: qContent,
                reason: "Opsi A dan Opsi B wajib diisi untuk Pilihan Ganda (minimal 2 opsi)."
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

            if (!isAi) {
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

          // Create new in bank
          try {
            const created = await teacherContentApi.createQuestion({
              type,
              content: qContent,
              options: finalOptions,
              answer_key: qAnswer,
              rubrics: finalRubrics,
              subject: detail.subject || "",
              ai_grading: isAi,
            });
            targetQuestionId = created.id;
          } catch (err: any) {
            failed.push({
              row: rowIndex,
              sheet,
              identifier: qContent,
              reason: `Gagal mendaftarkan soal baru ke bank: ${err?.message}`
            });
            continue;
          }
        }

        // Link question to package with Excel score
        try {
          await teacherContentApi.addQuestionToPackage(detail.id, targetQuestionId, qScore);
          successCount++;
        } catch (err: any) {
          failed.push({
            row: rowIndex,
            sheet,
            identifier: qContent,
            reason: `Gagal menyematkan soal ke paket (mungkin target terpenuhi): ${err?.message}`
          });
        }

        setImportProgress({ current: i + 1, total: jobs.length });
      }

      setImportReport({ success: successCount, skipped, failed });
      // Reload details
      const updatedData = await teacherContentApi.getPackageDetail(packageId);
      setDetail(updatedData);
      showToast({
        type: "success",
        title: "Impor Manual Selesai",
        message: `Berhasil menambahkan ${successCount} soal ke paket ujian.`,
      });
    } catch (err: any) {
      showToast({ type: "error", title: "Impor Gagal", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsImporting(false);
      setImportProgress(null);
    }
  };

  const getActualCount = (type: string) => {
    if (!detail) return 0;
    return detail.questions.filter((q) => q.type === type).length;
  };

  const getQuestionTypeColor = (type: QuestionType) => {
    switch (type) {
      case "PG":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "IS":
        return "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
      case "ES":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
    }
  };

  const filteredBank = bankQuestions.filter((q) => {
    const matchesSearch = q.content.toLowerCase().includes(bankSearch.toLowerCase()) ||
      q.answer_key.toLowerCase().includes(bankSearch.toLowerCase());
    const matchesType = bankFilterType ? q.type === bankFilterType : true;
    const matchesClassLevel = bankFilterClassLevel
      ? (q.class_level === bankFilterClassLevel || (!q.class_level && detail?.class_level === bankFilterClassLevel))
      : true;
    
    // Do not show questions already in package
    const alreadyInPackage = detail ? detail.questions.some((pq) => pq.id === q.id) : false;

    return matchesSearch && matchesType && matchesClassLevel && !alreadyInPackage;
  });

  if (isLoading || !detail) {
    return (
      <div className="glass-panel p-10 text-center text-slate-500">
        Memuat detail paket soal...
      </div>
    );
  }

  const targetPG = detail.target_counts.PG || 0;
  const targetIS = detail.target_counts.IS || 0;
  const targetES = detail.target_counts.ES || 0;

  const actualPG = getActualCount("PG");
  const actualIS = getActualCount("IS");
  const actualES = getActualCount("ES");

  const totalTarget = targetPG + targetIS + targetES;
  const totalActual = actualPG + actualIS + actualES;

  const percentProgress = totalTarget > 0 ? (totalActual / totalTarget) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header breadcrumb & back button */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="w-4 h-4" />} onClick={onBack}>
          Kembali ke Daftar
        </Button>
        <span className="text-slate-600">/</span>
        <span className="text-xs text-slate-400 font-mono">ID Paket: #{detail.id}</span>
      </div>

      {/* Main Title & Action Bar */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <FolderOpen className="w-6 h-6 text-indigo-400 shrink-0" />
            <span>{detail.name}</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Mata Pelajaran: <span className="font-semibold text-emerald-300">{detail.subject || "-"}</span> | Kelas:{" "}
            <span className="font-semibold text-indigo-300">Kelas {detail.class_level}</span> | Status:{" "}
            {detail.status === "READY" ? (
              <span className="text-emerald-400 font-bold">READY (Siap Ujian)</span>
            ) : (
              <span className="text-amber-400 font-bold">INCOMPLETE (Kurang Soal)</span>
            )}
          </p>
        </div>

        <div className="flex gap-2 w-full sm:w-auto flex-wrap">
          {detail.status === "READY" ? (
            <Button
              variant="ghost"
              size="md"
              leftIcon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
              onClick={() => setIsRevertDraftConfirmOpen(true)}
            >
              Ubah ke Draft (Edit Soal)
            </Button>
          ) : (
            <Button
              variant="primary"
              size="md"
              isLoading={isPublishingPackage}
              leftIcon={<CheckCircle2 className="w-4 h-4 text-emerald-300" />}
              onClick={handlePublishPackage}
            >
              Post / Simpan Paket (Siap Ujian)
            </Button>
          )}
          <Button
            variant="ghost"
            size="md"
            leftIcon={<Upload className="w-4 h-4 text-amber-400" />}
            onClick={() => {
              setImportReport(null);
              setIsImportModalOpen(true);
            }}
          >
            Impor XLSX Manual
          </Button>
          <Button
            variant="ghost"
            size="md"
            leftIcon={<Link className="w-4 h-4 text-indigo-400" />}
            onClick={handleOpenBank}
          >
            Ambil dari Bank Soal
          </Button>
          <Button
            variant="primary"
            size="md"
            leftIcon={<PlusCircle className="w-4 h-4" />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Buat & Tambah Soal
          </Button>
        </div>
      </div>

      {/* Main Two-Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Side: Summary & Targets Dashboard */}
        <div className="space-y-6">
          <div className="glass-panel p-5 space-y-4">
            <h3 className="text-xs font-bold text-slate-400 tracking-wider uppercase border-b border-slate-800 pb-2">
              Status Kelengkapan Soal
            </h3>

            {/* Overall progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-300 font-mono">
                <span>Total Butir Soal</span>
                <span className="font-bold">
                  {totalActual} / {totalTarget}
                </span>
              </div>
              <div className="h-2 rounded-full bg-slate-950 border border-slate-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    detail.status === "READY" ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                  style={{ width: `${percentProgress}%` }}
                />
              </div>
            </div>

            {/* Individual targets cards */}
            <div className="space-y-3 pt-2">
              {/* PG */}
              <div className="flex justify-between items-center p-3 rounded-xl bg-slate-950/40 border border-slate-900">
                <div>
                  <span className="text-xs text-slate-300 font-semibold block">Pilihan Ganda (PG)</span>
                  <span className="text-[10px] text-slate-500 font-mono">Target: {targetPG} butir</span>
                </div>
                <div className="text-right">
                  <span
                    className={`text-sm font-black font-mono ${
                      actualPG === targetPG ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {actualPG} / {targetPG}
                  </span>
                  {actualPG === targetPG && (
                    <Badge variant="emerald" size="sm">
                      PAS
                    </Badge>
                  )}
                </div>
              </div>

              {/* IS */}
              <div className="flex justify-between items-center p-3 rounded-xl bg-slate-950/40 border border-slate-900">
                <div>
                  <span className="text-xs text-slate-300 font-semibold block">Isian Singkat (IS)</span>
                  <span className="text-[10px] text-slate-500 font-mono">Target: {targetIS} butir</span>
                </div>
                <div className="text-right">
                  <span
                    className={`text-sm font-black font-mono ${
                      actualIS === targetIS ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {actualIS} / {targetIS}
                  </span>
                  {actualIS === targetIS && (
                    <Badge variant="emerald" size="sm">
                      PAS
                    </Badge>
                  )}
                </div>
              </div>

              {/* ES */}
              <div className="flex justify-between items-center p-3 rounded-xl bg-slate-950/40 border border-slate-900">
                <div>
                  <span className="text-xs text-slate-300 font-semibold block">Essay / Uraian (ES)</span>
                  <span className="text-[10px] text-slate-500 font-mono">Target: {targetES} butir</span>
                </div>
                <div className="text-right">
                  <span
                    className={`text-sm font-black font-mono ${
                      actualES === targetES ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {actualES} / {targetES}
                  </span>
                  {actualES === targetES && (
                    <Badge variant="emerald" size="sm">
                      PAS
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Validation Banner info */}
            {detail.status === "READY" ? (
              <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/30 flex items-start gap-2.5 text-[11px] text-emerald-300">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                <span>
                  Paket soal ini sudah **LENGKAP** dan berstatus **READY**. Paket soal ini sudah dapat disematkan ke jadwal ujian.
                </span>
              </div>
            ) : (
              <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 flex items-start gap-2.5 text-[11px] text-amber-300">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                <span>
                  Paket belum lengkap. Harap sesuaikan jumlah butir soal dengan target yang ditentukan di atas agar status berubah menjadi **READY**.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Ordered List of added Questions */}
        <div className="lg:col-span-2 space-y-4">
          <div className="glass-panel p-6">
            <h3 className="font-semibold text-slate-300 flex items-center gap-2 text-sm mb-4 border-b border-slate-800 pb-3">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span>Susunan Soal Paket ({detail.questions.length})</span>
            </h3>

            {detail.questions.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                Belum ada butir soal dimasukkan ke dalam paket ini. <br />
                Pilih <strong>Ambil dari Bank Soal</strong> atau <strong>Buat & Tambah Soal</strong> di atas.
              </div>
            ) : (
              <div className="space-y-2">
                {detail.questions.map((item, idx) => {
                  const isFirst = idx === 0;
                  const isLast = idx === detail.questions.length - 1;
                  return (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-colors flex items-start justify-between gap-3 text-xs"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-7 h-7 bg-slate-800 border border-slate-700 rounded-lg flex items-center justify-center font-mono font-bold text-slate-300 mt-0.5 shrink-0">
                          {item.canonical_order}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getQuestionTypeColor(
                                item.type
                              )}`}
                            >
                              {item.type}
                            </span>
                            <Badge variant="indigo" size="sm">
                              Skor: {item.score}
                            </Badge>
                            {item.type === "ES" && (
                              <Badge variant={item.ai_grading ? "emerald" : "indigo"} size="sm">
                                {item.ai_grading ? "⚡ AI Grading" : "Manual Rubrik"}
                              </Badge>
                            )}
                            <span className="text-[10px] text-slate-500 font-mono">Soal ID: #{item.id}</span>
                          </div>
                          <LaTeXText content={item.content} className="font-medium text-slate-200 leading-relaxed pt-1.5 break-words" />
                        </div>
                      </div>

                      {/* Actions & Reordering Controls */}
                      <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<RefreshCw className="w-3.5 h-3.5 text-indigo-400" />}
                          onClick={() => handleOpenReplaceModal(item)}
                          title="Ganti soal ini dengan soal lain dari Bank Soal"
                        >
                          <span className="hidden sm:inline">Ganti Soal</span>
                        </Button>
                        {item.type === "ES" && !item.ai_grading && (
                          <Button
                            variant="ghost"
                            size="sm"
                            leftIcon={<Edit2 className="w-3.5 h-3.5" />}
                            onClick={() => handleOpenEditRubric(item)}
                            title="Edit Rubrik Penilaian"
                          />
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<ArrowUp className="w-3.5 h-3.5" />}
                          onClick={() => handleReorder(idx, "up")}
                          disabled={isFirst}
                          title="Naikkan Urutan"
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<ArrowDown className="w-3.5 h-3.5" />}
                          onClick={() => handleReorder(idx, "down")}
                          disabled={isLast}
                          title="Turunkan Urutan"
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          leftIcon={<Trash2 className="w-3.5 h-3.5 text-rose-400" />}
                          onClick={() => handleOpenRemoveQuestionConfirm(item)}
                          title="Keluarkan Soal dari Paket"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Sub Modal: Add Question from Bank (Multi-Select & Bulk Score Entry) ── */}
      <Modal
        isOpen={isBankModalOpen}
        onClose={() => setIsBankModalOpen(false)}
        title={bankStep === 1 ? "Ambil Soal dari Bank Soal" : `Mengisi Skor untuk ${selectedBankQIds.length} Soal Terpilih`}
        maxWidth="lg"
      >
        {bankStep === 1 ? (
          /* STEP 1: SELECT QUESTIONS MULTI-CHOICE */
          <div className="space-y-4">
            {/* Target Quota Summary Banner */}
            {(() => {
              const targetPG = detail?.target_counts?.PG || 0;
              const targetIS = detail?.target_counts?.IS || 0;
              const targetES = detail?.target_counts?.ES || 0;

              const actualPG = getActualCount("PG");
              const actualIS = getActualCount("IS");
              const actualES = getActualCount("ES");

              const remPG = Math.max(0, targetPG - actualPG);
              const remIS = Math.max(0, targetIS - actualIS);
              const remES = Math.max(0, targetES - actualES);

              const selPG = selectedBankQIds.filter(id => bankQuestions.find(b => b.id === id)?.type === "PG").length;
              const selIS = selectedBankQIds.filter(id => bankQuestions.find(b => b.id === id)?.type === "IS").length;
              const selES = selectedBankQIds.filter(id => bankQuestions.find(b => b.id === id)?.type === "ES").length;

              const leftPG = Math.max(0, remPG - selPG);
              const leftIS = Math.max(0, remIS - selIS);
              const leftES = Math.max(0, remES - selES);

              return (
                <div className="p-2 sm:p-3 rounded-xl bg-slate-900 border border-slate-800 grid grid-cols-3 gap-1.5 sm:gap-2 text-center text-xs">
                  <div className={`p-1.5 sm:p-2 rounded-lg border ${leftPG === 0 ? "bg-amber-950/20 border-amber-500/30" : "bg-emerald-950/20 border-emerald-500/30"}`}>
                    <span className="text-[9px] sm:text-[10px] text-emerald-400 font-bold block truncate">PG (Pilihan Ganda)</span>
                    <span className="font-mono text-slate-300 text-[10px] sm:text-xs">
                      Sisa: <strong className={leftPG === 0 ? "text-amber-400 font-bold" : "text-emerald-400 font-bold"}>{leftPG}</strong>/{remPG}
                    </span>
                  </div>
                  <div className={`p-1.5 sm:p-2 rounded-lg border ${leftIS === 0 ? "bg-amber-950/20 border-amber-500/30" : "bg-indigo-950/20 border-indigo-500/30"}`}>
                    <span className="text-[9px] sm:text-[10px] text-indigo-400 font-bold block truncate">IS (Isian Singkat)</span>
                    <span className="font-mono text-slate-300 text-[10px] sm:text-xs">
                      Sisa: <strong className={leftIS === 0 ? "text-amber-400 font-bold" : "text-indigo-400 font-bold"}>{leftIS}</strong>/{remIS}
                    </span>
                  </div>
                  <div className={`p-1.5 sm:p-2 rounded-lg border ${leftES === 0 ? "bg-amber-950/20 border-amber-500/30" : "bg-amber-950/20 border-amber-500/30"}`}>
                    <span className="text-[9px] sm:text-[10px] text-amber-400 font-bold block truncate">ES (Essay/Uraian)</span>
                    <span className="font-mono text-slate-300 text-[10px] sm:text-xs">
                      Sisa: <strong className={leftES === 0 ? "text-amber-400 font-bold" : "text-amber-400 font-bold"}>{leftES}</strong>/{remES}
                    </span>
                  </div>
                </div>
              );
            })()}

            {/* Filter and Select All Bar */}
            <div className="flex flex-col sm:flex-row gap-2 justify-between items-stretch sm:items-center">
              <div className="flex gap-2 flex-1">
                <div className="flex-1">
                  <Input
                    placeholder="Cari konten pertanyaan..."
                    value={bankSearch}
                    onChange={(e) => setBankSearch(e.target.value)}
                    leftIcon={<Search className="w-4 h-4 text-slate-500" />}
                  />
                </div>
                <div className="w-36">
                  <Select
                    options={[
                      { value: "", label: "Semua Tipe" },
                      { value: "PG", label: "Pilihan Ganda" },
                      { value: "IS", label: "Isian Singkat" },
                      { value: "ES", label: "Essay" },
                    ]}
                    value={bankFilterType}
                    onChange={(e) => setBankFilterType(e.target.value)}
                  />
                </div>
                <div className="w-36">
                  <Select
                    options={[
                      { value: "", label: "Semua Tingkat" },
                      ...getGradeOptionsForSchool(user?.school_level_code),
                    ]}
                    value={bankFilterClassLevel}
                    onChange={(e) => setBankFilterClassLevel(e.target.value)}
                  />
                </div>
              </div>

              {filteredBank.length > 0 && (
                <button
                  type="button"
                  onClick={() => handleToggleSelectAllFiltered(filteredBank)}
                  className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs font-semibold text-indigo-300 hover:text-indigo-200 transition-colors flex items-center justify-center gap-2 shrink-0"
                >
                  <input
                    type="checkbox"
                    checked={
                      filteredBank.length > 0 &&
                      filteredBank.every((q) => selectedBankQIds.includes(q.id))
                    }
                    onChange={() => {}}
                    className="w-4 h-4 rounded text-indigo-600 pointer-events-none"
                  />
                  <span>Pilih Sesuai Sisa Kuota Paket ({filteredBank.length})</span>
                </button>
              )}
            </div>

            {/* Questions Selection List */}
            <div className="max-h-[350px] overflow-y-auto space-y-2 p-1.5 rounded-xl bg-slate-950/40 border border-slate-900">
              {bankLoading ? (
                <p className="text-center text-xs text-slate-500 py-10">Memuat bank soal...</p>
              ) : filteredBank.length === 0 ? (
                <p className="text-center text-xs text-slate-500 py-10">
                  Tidak ada soal yang tersedia untuk ditambahkan.
                </p>
              ) : (
                filteredBank.map((q) => {
                  const isSelected = selectedBankQIds.includes(q.id);

                  const targetForType = detail?.target_counts?.[q.type] || 0;
                  const actualForType = getActualCount(q.type);
                  const remForType = Math.max(0, targetForType - actualForType);

                  const selectedForType = selectedBankQIds.filter(
                    (id) => bankQuestions.find((b) => b.id === id)?.type === q.type
                  ).length;

                  const isTypeFull = remForType === 0;
                  const isTypeLimitReached = !isSelected && selectedForType >= remForType;

                  return (
                    <div
                      key={q.id}
                      onClick={() => handleToggleSelectBankQ(q.id)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 text-xs ${
                        isSelected
                          ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950/50"
                          : isTypeLimitReached
                          ? "bg-slate-950/40 border-slate-900 opacity-55 hover:border-slate-800"
                          : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={isTypeLimitReached}
                        onChange={() => {}}
                        className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 mt-0.5 shrink-0"
                      />

                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getQuestionTypeColor(
                              q.type
                            )}`}
                          >
                            {q.type}
                          </span>
                          {q.class_level && (
                            <Badge variant="indigo" size="sm">
                              Tingkat {q.class_level}
                            </Badge>
                          )}
                          {isTypeFull ? (
                            <Badge variant="amber" size="sm">
                              🔒 Target {q.type} Penuh ({actualForType}/{targetForType})
                            </Badge>
                          ) : isTypeLimitReached ? (
                            <Badge variant="amber" size="sm">
                              🔒 Kuota Terpilih Penuh (Max {remForType})
                            </Badge>
                          ) : null}
                          <span className="text-[10px] text-slate-500 font-mono">ID: #{q.id}</span>
                        </div>
                        <LaTeXText
                          content={q.content}
                          className="text-slate-200 leading-relaxed font-medium break-words pt-1"
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Step 1 Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <span className="text-xs text-slate-400 font-medium">
                Dipilih: <strong className="text-indigo-400 font-mono text-sm">{selectedBankQIds.length}</strong> soal
              </span>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setIsBankModalOpen(false)}>
                  Batal
                </Button>
                <Button
                  variant="primary"
                  onClick={handleProceedToScores}
                  disabled={selectedBankQIds.length === 0}
                >
                  Lanjut ke Pengisian Skor ({selectedBankQIds.length}) →
                </Button>
              </div>
            </div>
          </div>
        ) : (
          /* STEP 2: FILL SCORES FOR SELECTED QUESTIONS */
          <div className="space-y-4">
            {/* Batch Score Setter Bar */}
            <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <span className="text-xs font-semibold text-slate-300">Set Skor Serentak untuk Semua Soal:</span>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={batchScoreInput}
                  onChange={(e) => setBatchScoreInput(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-mono text-center focus:outline-none focus:border-indigo-500"
                />
                <Button variant="ghost" size="sm" onClick={handleApplyBatchScore}>
                  Terapkan ke Semua
                </Button>
              </div>
            </div>

            {/* Selected Questions Score Input List */}
            <div className="max-h-[350px] overflow-y-auto space-y-3 p-1.5 rounded-xl bg-slate-950/40 border border-slate-900">
              {selectedBankQIds.map((qId, idx) => {
                const q = bankQuestions.find((b) => b.id === qId);
                if (!q) return null;

                return (
                  <div
                    key={qId}
                    className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="w-5 h-5 rounded bg-slate-800 border border-slate-700 flex items-center justify-center font-mono font-bold text-slate-300 text-[10px]">
                          {idx + 1}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getQuestionTypeColor(
                            q.type
                          )}`}
                        >
                          {q.type}
                        </span>
                        {q.class_level && (
                          <Badge variant="indigo" size="sm">
                            Tingkat {q.class_level}
                          </Badge>
                        )}
                        <span className="text-[10px] text-slate-500 font-mono">ID: #{q.id}</span>
                      </div>
                      <LaTeXText
                        content={q.content}
                        className="text-slate-300 leading-relaxed font-medium break-words pt-1 line-clamp-2"
                      />
                    </div>

                    <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto justify-end border-t sm:border-t-0 border-slate-800 pt-2 sm:pt-0">
                      <span className="text-xs font-medium text-slate-400">Skor:</span>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={selectedScores[qId] || "10"}
                        onChange={(e) =>
                          setSelectedScores((prev) => ({ ...prev, [qId]: e.target.value }))
                        }
                        className="w-20 bg-slate-950 border border-indigo-500/50 rounded-lg px-3 py-1.5 text-xs text-indigo-300 font-mono font-bold text-center focus:outline-none focus:border-indigo-400"
                        required
                      />
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Step 2 Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <Button
                variant="ghost"
                onClick={() => setBankStep(1)}
                disabled={isSubmittingBulkBank}
              >
                ← Kembali (Pilih Soal)
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmAddBulkFromBank}
                isLoading={isSubmittingBulkBank}
              >
                Simpan {selectedBankQIds.length} Soal ke Paket
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Sub Modal: Create and Add Question Inline ── */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Buat & Tambah Soal Baru"
        maxWidth="lg"
      >
        <form onSubmit={handleCreateAndAdd} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Tipe Soal"
              options={[
                { value: "PG", label: "Pilihan Ganda" },
                { value: "IS", label: "Isian Singkat" },
                { value: "ES", label: "Essay" },
              ]}
              value={newType}
              onChange={(e) => setNewType(e.target.value as QuestionType)}
            />
            <Input
              label="Bobot Skor Soal"
              type="number"
              min="1"
              value={newScore}
              onChange={(e) => setNewScore(e.target.value)}
              required
            />
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
              className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 min-h-[80px]"
              placeholder="Ketikkan pertanyaan di sini..."
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              required
            />
          </div>

          {newType === "PG" && (
            <div className="space-y-2 bg-slate-950/40 p-4 rounded-xl border border-slate-900">
              <div className="flex justify-between items-center mb-1">
                <span className="text-xs font-bold text-slate-300">Pilihan Opsi Jawaban (Min 2 Opsi, Max 6)</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  leftIcon={<Plus className="w-3.5 h-3.5" />}
                  onClick={() => {
                    if (newOptions.length >= 6) {
                      showToast({ type: "warning", title: "Batas Opsi Terpenuhi", message: "Soal Pilihan Ganda maksimal 6 opsi (A-F)." });
                      return;
                    }
                    setNewOptions((prev) => [...prev, ""]);
                  }}
                  disabled={newOptions.length >= 6}
                >
                  Tambah Opsi
                </Button>
              </div>

              <div className="space-y-2">
                {newOptions.map((opt, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <div className="w-6 h-6 rounded-full bg-slate-800 text-xs font-bold text-slate-400 flex items-center justify-center shrink-0">
                      {String.fromCharCode(65 + i)}
                    </div>
                    <div className="flex-1">
                      <Input
                        placeholder={`Opsi ${String.fromCharCode(65 + i)} ${i < 2 ? "(Wajib)" : "(Opsional)"}`}
                        value={opt}
                        onChange={(e) => {
                          const copy = [...newOptions];
                          copy[i] = e.target.value;
                          setNewOptions(copy);
                        }}
                        required={i < 2}
                      />
                    </div>
                    <input
                      type="file"
                      id={`inline-opt-img-input-${i}`}
                      className="hidden"
                      accept="image/*"
                      onChange={(e) => handleUploadImageToOption(i, e)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      leftIcon={<Image className="w-3.5 h-3.5 text-indigo-400" />}
                      onClick={() => document.getElementById(`inline-opt-img-input-${i}`)?.click()}
                      title={`Sisipkan gambar ke Opsi ${String.fromCharCode(65 + i)}`}
                    />
                    {newOptions.length > 2 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                        onClick={() => setNewOptions((prev) => prev.filter((_, idx) => idx !== i))}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Official Answer Key */}
          {newType === "PG" ? (
            <Select
              label="Kunci Jawaban Benar (Wajib)"
              options={[
                { value: "", label: "-- Pilih Opsi yang Benar --" },
                ...newOptions.filter(Boolean).map((opt) => ({ value: opt, label: opt })),
              ]}
              value={newAnswerKey}
              onChange={(e) => setNewAnswerKey(e.target.value)}
              required
            />
          ) : (
            <Input
              label="Kunci Jawaban Benar (Wajib)"
              placeholder={newType === "IS" ? "Cth: Fotosintesis" : "Cth: Jawaban esai ideal..."}
              value={newAnswerKey}
              onChange={(e) => setNewAnswerKey(e.target.value)}
              required
            />
          )}

          {/* Essay AI Rubric Generator & Rubric Editor */}
          {newType === "ES" && (
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
                  isLoading={isGeneratingInlineAiRubric}
                  disabled={!newContent.trim() || !newAnswerKey.trim()}
                  onClick={handleGenerateInlineAiRubric}
                  leftIcon={<Sparkles className="w-3.5 h-3.5 text-amber-400" />}
                  className="shrink-0"
                >
                  {newRubrics.length > 0 && newAiGrading ? "Re-Generate Rubrik AI" : "Generate Rubrik AI"}
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
                    onClick={() => {
                      if (newRubrics.length >= 5) return;
                      setNewRubrics((prev) => [...prev, { criteria: "", max_score: 20 }]);
                    }}
                    disabled={newRubrics.length >= 5}
                  >
                    Tambah Rubrik
                  </Button>
                </div>

                <div className="space-y-2">
                  {newRubrics.map((r, idx) => (
                    <div key={idx} className="flex gap-2 items-center">
                      <div className="flex-1">
                        <Input
                          placeholder={`Kriteria Rubrik #${idx + 1}`}
                          value={r.criteria}
                          onChange={(e) => {
                            const copy = [...newRubrics];
                            copy[idx].criteria = e.target.value;
                            setNewRubrics(copy);
                          }}
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
                          onChange={(e) => {
                            const copy = [...newRubrics];
                            copy[idx].max_score = parseInt(e.target.value, 10) || 0;
                            setNewRubrics(copy);
                          }}
                          required
                        />
                      </div>
                      {newRubrics.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                          onClick={() => setNewRubrics((prev) => prev.filter((_, i) => i !== idx))}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button variant="ghost" onClick={() => setIsCreateModalOpen(false)}>
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              leftIcon={<Plus className="w-4 h-4" />}
              isLoading={isCreatingQuestion}
            >
              Simpan & Tambahkan
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Sub Modal: Edit Rubrics Inline ── */}
      <Modal
        isOpen={isEditRubricModalOpen}
        onClose={() => setIsEditRubricModalOpen(false)}
        title="Edit Rubrik Penilaian Essay"
        maxWidth="md"
      >
        <form onSubmit={handleSaveRubrics} className="space-y-4">
          <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-300 text-[10px] leading-relaxed">
            💡 Mengubah rubrik penilaian di sini hanya akan berlaku untuk penjadwalan ujian baru yang memakai paket ini. Perubahan tidak akan mempengaruhi atau merusak nilai hasil koreksi ujian yang sudah berjalan sebelumnya.
          </div>

          <div className="space-y-2 bg-slate-950/40 p-4 rounded-xl border border-slate-900">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-bold text-slate-300">Kriteria & Skor Maksimal Rubrik (Manual)</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                leftIcon={<Plus className="w-3.5 h-3.5" />}
                onClick={() => setEditRubrics((prev) => [...prev, { criteria: "", max_score: 5 }])}
                disabled={editRubrics.length >= 5}
              >
                Tambah Kriteria
              </Button>
            </div>

            <div className="space-y-2.5">
              {editRubrics.map((r, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <div className="flex-1">
                    <Input
                      placeholder="Nama kriteria cth: Tata bahasa"
                      value={r.criteria}
                      onChange={(e) => {
                        const copy = [...editRubrics];
                        copy[idx].criteria = e.target.value;
                        setEditRubrics(copy);
                      }}
                      required
                    />
                  </div>
                  <div className="w-28">
                    <Input
                      type="number"
                      min="1"
                      placeholder="Skor maks"
                      value={r.max_score.toString()}
                      onChange={(e) => {
                        const copy = [...editRubrics];
                        copy[idx].max_score = parseInt(e.target.value, 10) || 5;
                        setEditRubrics(copy);
                      }}
                      required
                    />
                  </div>
                  {editRubrics.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                      onClick={() => setEditRubrics((prev) => prev.filter((_, i) => i !== idx))}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button variant="ghost" onClick={() => setIsEditRubricModalOpen(false)}>
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isUpdatingRubrics}
            >
              Simpan Perubahan
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Impor XLSX Manual ke Paket ── */}
      <Modal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        title="Impor Soal Manual & Bobot Skor ke Paket"
        maxWidth="lg"
      >
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <span className="text-xs font-bold text-slate-300 block">Unduh Template Manual (Dengan Kolom Skor)</span>
              <p className="text-[10px] text-slate-400">
                Sediakan bobot skor untuk masing-masing soal di kolom Skor pada template Excel.
              </p>
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
            <div
              className="border-2 border-dashed border-slate-700/60 hover:border-indigo-500/50 rounded-2xl p-8 text-center cursor-pointer transition-colors relative"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept=".xlsx, .xls"
                onChange={handleFileImport}
                disabled={isImporting}
              />
              {isImporting ? (
                <div className="space-y-3">
                  <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto" />
                  <p className="text-xs text-slate-300 font-semibold">Sedang memproses & menyusun...</p>
                  {importProgress && (
                    <div className="text-[10px] text-slate-500">
                      Progress: {importProgress.current} / {importProgress.total} soal
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <FileSpreadsheet className="w-8 h-8 text-emerald-400 mx-auto" />
                  <p className="text-xs text-slate-300 font-semibold">Klik untuk memilih file Excel (.xlsx)</p>
                  <p className="text-[10px] text-slate-500">
                    Sistem mendeteksi dan mendaftarkan otomatis soal baru ke bank soal subjek <strong>{detail.subject}</strong> jika belum tersedia.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Import report results */}
          {importReport && (
            <div className="space-y-3.5 bg-slate-950/40 p-4 rounded-xl border border-slate-900 text-xs">
              <h4 className="font-bold text-slate-300 border-b border-slate-800 pb-1.5">Laporan Impor Paket</h4>
              
              <div className="flex gap-4 font-semibold text-slate-400">
                <span>Sukses Ditambahkan: <strong className="text-emerald-400">{importReport.success} Soal</strong></span>
                <span>Dilewati (Sudah ada di Paket): <strong className="text-indigo-400">{importReport.skipped.length} Soal</strong></span>
                <span>Gagal: <strong className="text-red-400">{importReport.failed.length} Soal</strong></span>
              </div>

              {/* Skipped rows check */}
              {importReport.skipped.length > 0 && (
                <div className="space-y-1 bg-indigo-950/10 p-2.5 rounded-lg border border-indigo-500/20 max-h-40 overflow-y-auto">
                  <span className="font-bold text-indigo-300 block mb-1">Daftar Baris Dilewati:</span>
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

      {/* ── Sub Modal: Replace Question in Package ── */}
      <Modal
        isOpen={isReplaceModalOpen}
        onClose={() => setIsReplaceModalOpen(false)}
        title={replacingQuestion ? `Ganti Soal #${replacingQuestion.id} (${replacingQuestion.type})` : "Ganti Soal"}
        maxWidth="lg"
      >
        {replacingQuestion && (
          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs space-y-1">
              <span className="text-[10px] text-slate-400 font-semibold block">Soal yang Akan Digantikan dalam Paket:</span>
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getQuestionTypeColor(replacingQuestion.type)}`}>
                  {replacingQuestion.type}
                </span>
                <span className="font-mono text-slate-400 text-[10px]">ID: #{replacingQuestion.id}</span>
                <Badge variant="indigo" size="sm">Skor Saat Ini: {replacingQuestion.score}</Badge>
              </div>
              <LaTeXText content={replacingQuestion.content} className="text-slate-200 pt-1 leading-relaxed font-medium line-clamp-2" />
            </div>

            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder="Cari soal pengganti di Bank Soal..."
                  value={replaceSearch}
                  onChange={(e) => setReplaceSearch(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-slate-500" />}
                />
              </div>
            </div>

            {/* List of Available Replacement Questions (Same Type & Not in Package) */}
            <div className="max-h-[300px] overflow-y-auto space-y-2 p-1.5 rounded-xl bg-slate-950/40 border border-slate-900">
              {bankLoading ? (
                <p className="text-center text-xs text-slate-500 py-10">Memuat bank soal...</p>
              ) : (() => {
                const availableReplacements = bankQuestions.filter((bq) => {
                  const isSameType = bq.type === replacingQuestion.type;
                  const notInPackage = !detail?.questions.some((pq) => pq.id === bq.id);
                  const matchesClass = bq.class_level ? bq.class_level === detail?.class_level : true;
                  const matchesSearch = bq.content.toLowerCase().includes(replaceSearch.toLowerCase()) ||
                    bq.answer_key.toLowerCase().includes(replaceSearch.toLowerCase());
                  return isSameType && notInPackage && matchesClass && matchesSearch;
                });

                if (availableReplacements.length === 0) {
                  return (
                    <p className="text-center text-xs text-slate-500 py-10">
                      Tidak ada soal pengganti bertipe <strong>{replacingQuestion.type}</strong> yang tersedia di Bank Soal.
                    </p>
                  );
                }

                return availableReplacements.map((bq) => {
                  const isSelected = selectedNewQId === bq.id;
                  return (
                    <div
                      key={bq.id}
                      onClick={() => setSelectedNewQId(bq.id)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer flex items-start gap-3 text-xs ${
                        isSelected
                          ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950/50"
                          : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <input
                        type="radio"
                        name="replaceQuestionRadio"
                        checked={isSelected}
                        onChange={() => setSelectedNewQId(bq.id)}
                        className="w-4 h-4 text-indigo-600 focus:ring-indigo-500 mt-0.5 shrink-0"
                      />
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getQuestionTypeColor(bq.type)}`}>
                            {bq.type}
                          </span>
                          {bq.class_level && (
                            <Badge variant="indigo" size="sm">Tingkat {bq.class_level}</Badge>
                          )}
                          <span className="text-[10px] text-slate-500 font-mono">ID: #{bq.id}</span>
                        </div>
                        <LaTeXText content={bq.content} className="text-slate-200 leading-relaxed font-medium pt-1" />
                      </div>
                    </div>
                  );
                });
              })()}
            </div>

            {/* Score Input for replacement */}
            <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-850">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-300">Skor Soal Pengganti:</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={replaceScore}
                  onChange={(e) => setReplaceScore(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-indigo-300 font-mono font-bold text-center focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setIsReplaceModalOpen(false)}>
                  Batal
                </Button>
                <Button
                  variant="primary"
                  onClick={handleConfirmReplace}
                  disabled={selectedNewQId === null}
                  isLoading={isSubmittingReplace}
                >
                  Terapkan Penggantian Soal
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Custom Confirmation MessageBox: Remove Question from Package ── */}
      <MessageBox
        isOpen={removingQuestionItem !== null}
        onClose={() => setRemovingQuestionItem(null)}
        type="warning"
        title="Keluarkan Soal dari Paket"
        message={
          <div>
            Apakah Anda yakin ingin mengeluarkan <strong>Soal #{removingQuestionItem?.id} ({removingQuestionItem?.type})</strong> dari paket soal ini?
            <p className="text-[11px] text-slate-400 mt-1">
              Status kelengkapan paket soal akan otomatis disesuaikan menjadi <strong>INCOMPLETE</strong> dan sisa kuota target akan terbuka kembali. Soal asli tetap tersimpan aman di Bank Soal.
            </p>
          </div>
        }
        confirmText="Keluarkan Soal"
        cancelText="Batal"
        onConfirm={handleConfirmRemoveQuestion}
        isLoading={isRemovingFromPackage}
        confirmVariant="danger"
      />

      {/* ── Custom Confirmation MessageBox: Revert Package to Draft ── */}
      <MessageBox
        isOpen={isRevertDraftConfirmOpen}
        onClose={() => setIsRevertDraftConfirmOpen(false)}
        type="question"
        title="Ubah Paket Soal ke Draft"
        message={
          <div>
            Apakah Anda yakin ingin mengembalikan status paket soal ini ke <strong>DRAFT (INCOMPLETE)</strong>?
            <p className="text-[11px] text-slate-400 mt-1">
              Penugasan paket ke jadwal ujian akan dibatalkan sementara agar Anda dapat mengubah, menambah, atau mengganti butir soal.
            </p>
          </div>
        }
        confirmText="Ubah ke Draft"
        cancelText="Batal"
        onConfirm={handleConfirmRevertDraft}
        isLoading={isRevertingDraft}
        confirmVariant="primary"
      />
    </div>
  );
}
