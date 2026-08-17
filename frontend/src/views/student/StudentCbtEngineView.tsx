import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  Clock,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Grid,
  Send,
  Lock,
  ShieldCheck,
  Award,
  Keyboard,
  ChevronDown,
} from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Modal } from "../../components/ui/Modal";
import { MathText } from "../../components/ui/MathText";
import { useToast } from "../../context/ToastContext";
import { studentExamApi } from "../../api/studentExam";
import type { StudentSchedule, StudentQuestionItem, ExamAttemptData } from "../../api/studentExam";

interface StudentCbtEngineProps {
  schedule: StudentSchedule;
  onExit: () => void;
}

export function StudentCbtEngineView({ schedule, onExit }: StudentCbtEngineProps) {
  const { showToast } = useToast();

  // Engine States
  const [attempt, setAttempt] = useState<ExamAttemptData | null>(null);
  const [questions, setQuestions] = useState<StudentQuestionItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Student Answers State: question_id -> { selected_option, text_answer, is_flagged }
  const [answers, setAnswers] = useState<
    Record<number, { selected_option?: string; text_answer?: string; is_flagged?: boolean }>
  >({});

  // UI & Keyboard States
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [fontSize, setFontSize] = useState<"normal" | "large" | "xlarge">("normal");
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);

  // Autosave Status
  const [autosaveStatus, setAutosaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [lastSavedTime, setLastSavedTime] = useState<string>("");

  // Countdown Timer
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);

  // 1. Initialize Exam Attempt & Android Native Kiosk Mode
  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).LockxamBridge?.enterKioskMode) {
      (window as any).LockxamBridge.enterKioskMode();
    }
  }, []);

  const initAttempt = async () => {
    setIsLoading(true);
    try {
      if (!schedule.session_id) {
        throw new Error("Sesi ujian belum dikonfirmasi oleh pengawas.");
      }
      const data = await studentExamApi.startAttempt(schedule.session_id);
      setAttempt(data);

      if (data.status === "SUBMITTED" || data.status === "GRADED") {
        setIsCompleted(true);
        setIsLoading(false);
        return;
      }

      // Populate questions list
      if (data.questions && data.questions.length > 0) {
        setQuestions(data.questions);
      } else {
        // Default questions with LaTeX formatting demonstration
        const mockQuestions: StudentQuestionItem[] = [
          {
            question_id: 101,
            question_type: "PG",
            content: "Tentukan hasil dari nilai perpangkatan $2^3 + 3 \\times 4$ dan penyederhanaan bentuk $\\sqrt{16}$!",
            options: [
              { key: "A", text: "$18$" },
              { key: "B", text: "$20$" },
              { key: "C", text: "$24$" },
              { key: "D", text: "$32$" },
            ],
            score_weight: 5,
          },
          {
            question_id: 102,
            question_type: "PG",
            content: "Jika $x^2 - 5x + 6 = 0$, maka himpunan penyelesaian nilai $x$ adalah...",
            options: [
              { key: "A", text: "$\\{1, 6\\}$" },
              { key: "B", text: "$\\{2, 3\\}$" },
              { key: "C", text: "$\\{-2, -3\\}$" },
              { key: "D", text: "$\\{0, 6\\}$" },
            ],
            score_weight: 5,
          },
          {
            question_id: 103,
            question_type: "IS",
            content: "Tuliskan nama senyawa kimia dari rumus molekul $\\text{H}_2\\text{O}$!",
            score_weight: 10,
          },
          {
            question_id: 104,
            question_type: "ES",
            content: "Jelaskan proses fotosintesis pada tumbuhan hijau dengan menuliskan persamaan reaksi kimianya $6\\text{CO}_2 + 6\\text{H}_2\\text{O} \\rightarrow \\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2$ secara runtut!",
            score_weight: 20,
          },
        ];
        setQuestions(mockQuestions);
      }

      // Populate existing answers & merge with local offline cache
      let mergedAnswers = data.answers || {};
      try {
        const cacheKey = `cbt_answers_session_${schedule.session_id}`;
        const cachedStr = localStorage.getItem(cacheKey);
        if (cachedStr) {
          const cachedMap = JSON.parse(cachedStr);
          mergedAnswers = { ...mergedAnswers, ...cachedMap };
        }
      } catch (e) {
        console.warn("Cache restore error:", e);
      }
      setAnswers(mergedAnswers);

      if (["SUBMITTED", "GRADING", "GRADED"].includes(data.status)) {
        setIsCompleted(true);
        setIsLoading(false);
        return;
      }

      if (data.deadline_at) {
        const deadlineMs = new Date(data.deadline_at).getTime();
        const nowMs = Date.now();
        const diffSec = Math.max(0, Math.floor((deadlineMs - nowMs) / 1000));
        setRemainingSeconds(data.remaining_seconds ?? diffSec);
      } else {
        setRemainingSeconds(schedule.duration_minutes * 60);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memulai Ujian",
        message: err?.message || "Gagal menginisialisasi sesi pengerjaan ujian.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initAttempt();
  }, []);

  // 2. Countdown Timer Ticker
  useEffect(() => {
    if (isLoading || isCompleted || remainingSeconds <= 0) return;

    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleAutoSubmitOnTimeout();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isLoading, isCompleted, remainingSeconds]);

  // Anti-Copy & Anti-Selection
  useEffect(() => {
    const handleContextMenu = (e: MouseEvent) => e.preventDefault();
    const handleCopy = (e: ClipboardEvent) => e.preventDefault();
    const handleCut = (e: ClipboardEvent) => e.preventDefault();
    const handleDragStart = (e: DragEvent) => e.preventDefault();

    document.body.classList.add("disable-selection");
    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("copy", handleCopy);
    document.addEventListener("cut", handleCut);
    document.addEventListener("dragstart", handleDragStart);

    return () => {
      document.body.classList.remove("disable-selection");
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("copy", handleCopy);
      document.removeEventListener("cut", handleCut);
      document.removeEventListener("dragstart", handleDragStart);
    };
  }, []);

  // Auto-hide keyboard when switching questions
  useEffect(() => {
    const q = questions[currentIndex];
    if (q && (q.question_type === "IS" || q.question_type === "ES")) {
      setIsKeyboardVisible(true);
    } else {
      setIsKeyboardVisible(false);
    }
  }, [currentIndex, questions]);

  const handleAutoSubmitOnTimeout = async () => {
    if (!attempt || isCompleted) return;
    showToast({
      type: "warning",
      title: "Waktu Ujian Habis!",
      message: "Waktu pengerjaan telah berakhir. Jawaban Anda sedang disubmit otomatis.",
    });
    await executeSubmit();
  };

  // 3. Save Answer Handler
  const saveAnswer = useCallback(
    async (qId: number, selectedOpt?: string, textAns?: string, flagged?: boolean) => {
      setAnswers((prev) => {
        const existing = prev[qId] || {};
        return {
          ...prev,
          [qId]: {
            selected_option: selectedOpt !== undefined ? selectedOpt : existing.selected_option,
            text_answer: textAns !== undefined ? textAns : existing.text_answer,
            is_flagged: flagged !== undefined ? flagged : existing.is_flagged,
          },
        };
      });

      try {
        const cacheKey = `cbt_answers_session_${schedule.session_id}`;
        const currentAnsMap = answers;
        const updatedAnsMap = {
          ...currentAnsMap,
          [qId]: {
            selected_option: selectedOpt !== undefined ? selectedOpt : currentAnsMap[qId]?.selected_option,
            text_answer: textAns !== undefined ? textAns : currentAnsMap[qId]?.text_answer,
            is_flagged: flagged !== undefined ? flagged : currentAnsMap[qId]?.is_flagged,
          },
        };
        localStorage.setItem(cacheKey, JSON.stringify(updatedAnsMap));
      } catch (e) {
        console.warn("LocalStorage cache error:", e);
      }

      if (!attempt) return;
      setAutosaveStatus("saving");

      try {
        await studentExamApi.autosaveAnswer(attempt.id, qId, selectedOpt, textAns);
        setAutosaveStatus("saved");
        const nowStr = new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
        setLastSavedTime(nowStr);
      } catch {
        setAutosaveStatus("error");
      }
    },
    [attempt, answers, schedule.session_id]
  );

  const toggleFlagged = (qId: number) => {
    const currentFlag = answers[qId]?.is_flagged || false;
    saveAnswer(qId, undefined, undefined, !currentFlag);
  };

  const executeSubmit = async () => {
    if (!attempt) return;
    setIsSubmitting(true);
    try {
      await studentExamApi.submitAttempt(attempt.id);
      if (typeof window !== "undefined" && (window as any).LockxamBridge?.exitKioskMode) {
        (window as any).LockxamBridge.exitKioskMode();
      }
      setIsCompleted(true);
      setIsSubmitModalOpen(false);
      showToast({
        type: "success",
        title: "Ujian Selesai!",
        message: "Jawaban Anda telah berhasil dikumpulkan.",
      });
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengumpulkan Ujian",
        message: err?.message || "Terjadi kesalahan saat submit.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatTimer = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const pad = (n: number) => String(n).padStart(2, "0");
    if (hrs > 0) return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
    return `${pad(mins)}:${pad(secs)}`;
  };

  const currentQuestion = questions[currentIndex];
  const stats = useMemo(() => {
    let answered = 0, flagged = 0, unanswered = 0;
    questions.forEach((q) => {
      const a = answers[q.question_id];
      if (a?.is_flagged) flagged++;
      if (a?.selected_option || (a?.text_answer && a.text_answer.trim().length > 0)) {
        answered++;
      } else {
        unanswered++;
      }
    });
    return { answered, flagged, unanswered, total: questions.length };
  }, [questions, answers]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6 text-slate-300">
        <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
        <h3 className="font-bold text-base text-slate-100">Memuat Sesi Ujian CBT...</h3>
        <p className="text-xs text-slate-400 mt-1">Menyiapkan lembar soal &amp; format LaTeX.</p>
      </div>
    );
  }

  if (isCompleted) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
        <div className="glass-panel max-w-md w-full p-8 text-center space-y-6 border border-emerald-500/30 animate-fade-in">
          <div className="w-20 h-20 bg-emerald-500/10 border-2 border-emerald-500/40 rounded-full flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-500/10">
            <Award className="w-10 h-10 animate-bounce" />
          </div>
          <div>
            <Badge variant="emerald">UJIAN SELESAI &amp; TERKIRIM</Badge>
            <h2 className="text-2xl font-black text-slate-100 mt-2">{schedule.title}</h2>
            <p className="text-xs text-slate-400 mt-1">
              Pelajaran: <strong>{schedule.subject_name}</strong> | Selesai: {new Date().toLocaleTimeString("id-ID")}
            </p>
          </div>

          <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Total Soal:</span>
              <span className="font-bold text-slate-200">{stats.total} Soal</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Soal Dijawab:</span>
              <span className="font-bold text-emerald-400">{stats.answered} Soal</span>
            </div>
          </div>

          <Button variant="primary" className="w-full" onClick={onExit}>
            Kembali ke Dashboard Siswa
          </Button>
        </div>
      </div>
    );
  }

  if (!currentQuestion) return null;
  const currentAnswer = answers[currentQuestion.question_id] || {};
  const isTextQuestion = currentQuestion.question_type === "IS" || currentQuestion.question_type === "ES";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between font-sans cbt-engine-container select-none relative">
      {/* ── 1. Top CBT Header Bar (Responsive 2-Tier Mobile / 1-Tier Desktop) ── */}
      <header className="sticky top-0 z-30 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 px-3 py-2 sm:px-4 sm:py-3 w-full overflow-hidden">
        <div className="max-w-7xl mx-auto space-y-2 sm:space-y-0 sm:flex sm:items-center sm:justify-between sm:gap-3">
          {/* Main Info Row (Title & Timer) */}
          <div className="flex items-center justify-between gap-2">
            {/* Left Title & Subject */}
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <div className="p-1.5 bg-indigo-950/80 border border-indigo-500/40 rounded-lg shrink-0">
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-xs sm:text-sm font-black text-slate-100 truncate">
                  {schedule.title}
                </h1>
                <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                  <span className="truncate">{schedule.subject_name}</span>
                  {schedule.lock_browser && (
                    <span className="text-emerald-400 flex items-center gap-0.5 font-bold shrink-0">
                      <Lock className="w-2.5 h-2.5" /> Lockxam
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Timer Pill */}
            <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-xl border border-slate-800 shrink-0 shadow-inner">
              <Clock className={`w-3.5 h-3.5 ${remainingSeconds < 300 ? "text-rose-400 animate-pulse" : "text-emerald-400"}`} />
              <span className={`font-mono text-xs sm:text-sm font-black ${remainingSeconds < 300 ? "text-rose-400" : "text-emerald-300"}`}>
                {formatTimer(remainingSeconds)}
              </span>
            </div>
          </div>

          {/* Action Row on Mobile / Right Bar on Desktop */}
          <div className="flex items-center justify-between sm:justify-end gap-2 pt-1.5 sm:pt-0 border-t border-slate-800/60 sm:border-0">
            <div className="flex items-center gap-1 text-[10px] text-slate-400 bg-slate-950 px-2 py-1 rounded-lg border border-slate-850">
              {autosaveStatus === "saving" && <span className="text-amber-400 animate-pulse font-semibold">Menyimpan...</span>}
              {autosaveStatus === "saved" && <span className="text-emerald-400 font-semibold">Tersimpan {lastSavedTime}</span>}
              {autosaveStatus === "error" && <span className="text-rose-400 font-semibold">Gagal Simpan</span>}
              {autosaveStatus === "idle" && <span className="text-slate-500">Autosave</span>}
            </div>

            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                className="px-2.5 py-1 text-xs"
                leftIcon={<Grid className="w-3.5 h-3.5 text-indigo-400" />}
                onClick={() => setIsDrawerOpen(true)}
              >
                Soal ({stats.answered}/{stats.total})
              </Button>

              <Button
                variant="primary"
                size="sm"
                className="px-3 py-1 text-xs"
                leftIcon={<Send className="w-3.5 h-3.5" />}
                onClick={() => setIsSubmitModalOpen(true)}
              >
                Selesai
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* ── 2. Main Question Body Area ── */}
      <main className={`flex-1 max-w-4xl w-full mx-auto p-3 sm:p-6 space-y-4 ${isTextQuestion && isKeyboardVisible ? "pb-[290px]" : "pb-6"}`}>
        {/* Question Tool Header */}
        <div className="flex items-center justify-between gap-2 bg-slate-900/80 p-3 rounded-xl border border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-300">
              Soal <strong className="text-sm text-indigo-400">#{currentIndex + 1}</strong> / {questions.length}
            </span>
            <Badge variant={currentQuestion.question_type === "PG" ? "indigo" : "amber"}>
              {currentQuestion.question_type === "PG" ? "Pilihan Ganda" : currentQuestion.question_type === "IS" ? "Isian Singkat" : "Esai"}
            </Badge>
          </div>

          {/* Font Size Selector */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setFontSize("normal")}
              className={`px-2 py-0.5 text-[10px] font-bold rounded ${fontSize === "normal" ? "bg-indigo-600 text-white" : "text-slate-400"}`}
            >
              A
            </button>
            <button
              onClick={() => setFontSize("large")}
              className={`px-2 py-0.5 text-xs font-bold rounded ${fontSize === "large" ? "bg-indigo-600 text-white" : "text-slate-400"}`}
            >
              A+
            </button>
            <button
              onClick={() => setFontSize("xlarge")}
              className={`px-2 py-0.5 text-sm font-bold rounded ${fontSize === "xlarge" ? "bg-indigo-600 text-white" : "text-slate-400"}`}
            >
              A++
            </button>
          </div>
        </div>

        {/* Question Content Box with KaTeX LaTeX Support */}
        <div className="glass-panel p-4 sm:p-8 space-y-5 border border-slate-800">
          <div
            className={`text-slate-100 leading-relaxed font-sans ${
              fontSize === "large" ? "text-base sm:text-lg" : fontSize === "xlarge" ? "text-lg sm:text-xl" : "text-sm sm:text-base"
            }`}
          >
            <MathText text={currentQuestion.content} />
          </div>

          {/* Multiple Choice Options (PG) with KaTeX LaTeX Support */}
          {currentQuestion.question_type === "PG" && currentQuestion.options && (
            <div className="space-y-2.5 pt-2">
              {currentQuestion.options.map((opt) => {
                const isSelected = currentAnswer.selected_option === opt.key;
                return (
                  <button
                    key={opt.key}
                    onClick={() => saveAnswer(currentQuestion.question_id, opt.key)}
                    className={`w-full p-3.5 sm:p-4 rounded-xl border text-left flex items-start gap-3 transition-all duration-200 active:scale-[0.99] ${
                      isSelected
                        ? "bg-indigo-950/80 border-indigo-500 text-slate-100 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-500"
                        : "bg-slate-900/50 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80"
                    }`}
                  >
                    <span
                      className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 transition-colors ${
                        isSelected ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {opt.key}
                    </span>
                    <span className={`pt-0.5 text-xs sm:text-sm ${fontSize === "large" ? "text-sm sm:text-base" : fontSize === "xlarge" ? "text-base sm:text-lg" : ""}`}>
                      <MathText text={opt.text} />
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Text Input (Short Answer / Essay) */}
          {isTextQuestion && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold text-slate-300">Jawaban Anda:</label>
                <button
                  onClick={() => setIsKeyboardVisible(!isKeyboardVisible)}
                  className="px-2.5 py-1 bg-indigo-950 border border-indigo-500/50 text-indigo-300 rounded-lg text-xs font-bold flex items-center gap-1.5 hover:bg-indigo-900 transition-colors"
                >
                  <Keyboard className="w-3.5 h-3.5" />
                  <span>{isKeyboardVisible ? "Sembunyikan Keyboard" : "Buka Keypad Lockxam"}</span>
                </button>
              </div>

              {/* Readonly textarea acting as input display */}
              <div
                onClick={() => setIsKeyboardVisible(true)}
                className="w-full min-h-[90px] bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs sm:text-sm text-slate-100 cursor-pointer focus:border-indigo-500 transition-colors font-mono whitespace-pre-wrap relative"
              >
                {currentAnswer.text_answer ? (
                  currentAnswer.text_answer
                ) : (
                  <span className="text-slate-600 italic">Tekan untuk mengetik dengan keyboard Lockxam...</span>
                )}
                <span className="inline-block w-[2px] h-4 sm:h-5 bg-indigo-400 ml-0.5 animate-[pulse_0.8s_infinite] align-middle shadow-[0_0_6px_rgba(129,140,248,0.8)]" />
              </div>
            </div>
          )}
        </div>
      </main>

      {/* ── 3. Unified Bottom Fixed Container (Tier 1: Navbar Bawah, Tier 2: Keyboard Virtual) ── */}
      <footer className="fixed bottom-0 left-0 right-0 z-40 w-full bg-slate-900/98 backdrop-blur-xl border-t border-slate-800 shadow-2xl transition-all duration-200">
        {/* Tier 1: Navbar Bawah (Sebelumnya | Ragu-Ragu | Selanjutnya) */}
        <div className="w-full px-3 py-2.5 sm:px-6 sm:py-3 border-b border-slate-800/60">
          <div className="w-full flex items-center justify-between gap-2 sm:gap-4">
            {/* Previous Button */}
            <Button
              variant="outline"
              size="sm"
              disabled={currentIndex === 0}
              leftIcon={<ChevronLeft className="w-4 h-4" />}
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              className="flex-1 sm:flex-initial"
            >
              Sebelumnya
            </Button>

            {/* Ragu-ragu Checkbox Button */}
            <button
              onClick={() => toggleFlagged(currentQuestion.question_id)}
              className={`px-3 py-2 sm:px-5 sm:py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center justify-center gap-1.5 sm:gap-2 border transition-all ${
                currentAnswer.is_flagged
                  ? "bg-amber-500/20 border-amber-500/60 text-amber-300 shadow-md shadow-amber-500/10"
                  : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              <AlertTriangle className={`w-3.5 h-3.5 ${currentAnswer.is_flagged ? "text-amber-400" : "text-slate-500"}`} />
              <span>Ragu-Ragu</span>
            </button>

            {/* Next / Finish Button */}
            {currentIndex < questions.length - 1 ? (
              <Button
                variant="primary"
                size="sm"
                rightIcon={<ChevronRight className="w-4 h-4" />}
                onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                className="flex-1 sm:flex-initial"
              >
                Selanjutnya
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Send className="w-4 h-4" />}
                onClick={() => setIsSubmitModalOpen(true)}
                className="flex-1 sm:flex-initial"
              >
                Kumpulkan
              </Button>
            )}
          </div>
        </div>

        {/* Tier 2: Keyboard Virtual (Appears BELOW Navbar Bawah when open) */}
        {isTextQuestion && isKeyboardVisible && (
          <div className="w-full bg-slate-950/95 p-2 sm:p-4 select-none animate-slide-up border-t border-slate-800">
            <LockxamBottomKeyboard
              value={currentAnswer.text_answer || ""}
              onChange={(newVal) => saveAnswer(currentQuestion.question_id, undefined, newVal)}
              onClose={() => setIsKeyboardVisible(false)}
            />
          </div>
        )}
      </footer>

      {/* ── 5. Question Matrix Drawer Modal ── */}
      <Modal
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title="Daftar Soal CBT"
        maxWidth="md"
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-xs p-2.5 bg-slate-900 rounded-xl border border-slate-800">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-indigo-600 inline-block" />
              <span className="text-slate-300">Dijawab</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-amber-500 inline-block" />
              <span className="text-slate-300">Ragu-Ragu</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-slate-950 border border-slate-800 inline-block" />
              <span className="text-slate-400">Belum Dijawab</span>
            </div>
          </div>

          <div className="grid grid-cols-5 sm:grid-cols-8 gap-2 max-h-[280px] overflow-y-auto p-1">
            {questions.map((q, idx) => {
              const ans = answers[q.question_id];
              const isAnswered = ans?.selected_option || (ans?.text_answer && ans.text_answer.trim().length > 0);
              const isFlagged = ans?.is_flagged;
              const isCurrent = idx === currentIndex;

              let btnStyle = "bg-slate-950 text-slate-400 border-slate-800";
              if (isFlagged) {
                btnStyle = "bg-amber-500/20 text-amber-300 border-amber-500/60 font-bold";
              } else if (isAnswered) {
                btnStyle = "bg-indigo-600 text-white border-indigo-400 font-bold";
              }

              return (
                <button
                  key={q.question_id}
                  onClick={() => {
                    setCurrentIndex(idx);
                    setIsDrawerOpen(false);
                  }}
                  className={`h-10 rounded-xl border text-xs font-mono flex items-center justify-center transition-all ${btnStyle} ${
                    isCurrent ? "ring-2 ring-emerald-400 ring-offset-2 ring-offset-slate-950 scale-105" : ""
                  }`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>
        </div>
      </Modal>

      {/* ── 6. Submit Confirmation Modal ── */}
      <Modal
        isOpen={isSubmitModalOpen}
        onClose={() => setIsSubmitModalOpen(false)}
        title="Konfirmasi Kumpulkan Ujian"
        maxWidth="sm"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">
            Apakah Anda yakin ingin mengumpulkan pengerjaan ujian <strong>"{schedule.title}"</strong>?
          </p>

          <div className="bg-slate-900 p-3.5 rounded-xl border border-slate-800 space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Total Soal:</span>
              <span className="font-bold text-slate-200">{stats.total} Soal</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Sudah Dijawab:</span>
              <span className="font-bold text-emerald-400">{stats.answered} Soal</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Belum Dijawab:</span>
              <span className={`font-bold ${stats.unanswered > 0 ? "text-rose-400" : "text-slate-300"}`}>
                {stats.unanswered} Soal
              </span>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setIsSubmitModalOpen(false)}>
              Batal
            </Button>
            <Button
              variant="primary"
              onClick={executeSubmit}
              disabled={isSubmitting}
              isLoading={isSubmitting}
            >
              Kumpulkan Ujian Sekarang
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Lockxam Native OS-Style Bottom Sheet Virtual Keyboard Component
// ─────────────────────────────────────────────────────────────────────────────

interface LockxamBottomKeyboardProps {
  value: string;
  onChange: (newValue: string) => void;
  onClose: () => void;
}

function LockxamBottomKeyboard({ value, onChange, onClose }: LockxamBottomKeyboardProps) {
  const [shiftMode, setShiftMode] = useState<"off" | "shift" | "caps">("shift");
  const [mode, setMode] = useState<"ABC" | "123" | "SYM">("ABC");
  const lastShiftTapRef = useRef<number>(0);

  const handleShiftTap = () => {
    const now = Date.now();
    const diff = now - lastShiftTapRef.current;
    lastShiftTapRef.current = now;

    if (diff < 350) {
      // Double tap -> Permanent CAPS LOCK
      setShiftMode("caps");
    } else {
      // Single tap -> Cycle off -> shift -> off
      setShiftMode((prev) => {
        if (prev === "off") return "shift";
        if (prev === "shift") return "off";
        return "off";
      });
    }
  };

  const handleKeyPress = (char: string) => {
    const isUpper = shiftMode !== "off";
    const nextChar = isUpper ? char.toUpperCase() : char.toLowerCase();
    onChange(value + nextChar);

    // Auto-reset single-tap Shift back to lowercase after 1 character!
    if (shiftMode === "shift") {
      setShiftMode("off");
    }
  };

  const handleBackspace = () => {
    if (value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };

  const handleEnter = () => {
    onChange(value + "\n");
  };

  const handleClear = () => {
    onChange("");
  };

  const rowNumbers = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"];
  const rowLetters1 = ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"];
  const rowLetters2 = ["A", "S", "D", "F", "G", "H", "J", "K", "L"];
  const rowLetters3 = ["Z", "X", "C", "V", "B", "N", "M"];

  const rowSym1 = ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"];
  const rowSym2 = ["-", "_", "=", "+", "[", "]", "{", "}", ";", ":"];
  const rowSym3 = ["'", '"', ",", ".", "<", ">", "/", "?", "\\", "|"];

  const isUpperDisplay = shiftMode !== "off";

  return (
    <div className="max-w-3xl mx-auto space-y-1.5 sm:space-y-2 select-none">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-1.5 text-xs border-b border-slate-800">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setMode("ABC")}
            className={`px-3.5 py-1 rounded-lg font-bold transition-none active:scale-95 ${
              mode === "ABC" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            ABC
          </button>
          <button
            type="button"
            onClick={() => setMode("123")}
            className={`px-3.5 py-1 rounded-lg font-bold transition-none active:scale-95 ${
              mode === "123" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            123
          </button>
          <button
            type="button"
            onClick={() => setMode("SYM")}
            className={`px-3.5 py-1 rounded-lg font-bold transition-none active:scale-95 ${
              mode === "SYM" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            #+=
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleClear}
            className="px-2.5 py-1 bg-rose-500/20 text-rose-300 rounded-lg text-xs font-bold transition-none active:scale-95 hover:bg-rose-500/30"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-200 rounded-lg text-xs font-bold flex items-center gap-1 transition-none active:scale-95"
          >
            <span>Sembunyikan</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Row Numbers */}
      <div className="flex justify-center gap-0.5 sm:gap-1">
        {rowNumbers.map((num) => (
          <button
            key={num}
            type="button"
            onClick={() => handleKeyPress(num)}
            className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-mono font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
          >
            {num}
          </button>
        ))}
      </div>

      {/* Main Keys Rows */}
      {mode === "ABC" && (
        <>
          <div className="flex justify-center gap-0.5 sm:gap-1">
            {rowLetters1.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {isUpperDisplay ? char : char.toLowerCase()}
              </button>
            ))}
          </div>

          <div className="flex justify-center gap-0.5 sm:gap-1 px-2.5 sm:px-4">
            {rowLetters2.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {isUpperDisplay ? char : char.toLowerCase()}
              </button>
            ))}
          </div>

          <div className="flex justify-center gap-0.5 sm:gap-1">
            <button
              type="button"
              onClick={handleShiftTap}
              className={`w-14 sm:w-20 h-11 sm:h-12 rounded-lg text-xs font-bold transition-none active:scale-90 shrink-0 flex items-center justify-center gap-1 ${
                shiftMode === "caps"
                  ? "bg-indigo-600 text-white font-black ring-2 ring-indigo-400 shadow-md shadow-indigo-500/30"
                  : shiftMode === "shift"
                  ? "bg-indigo-600/90 text-white font-bold shadow-md shadow-indigo-500/20"
                  : "bg-slate-800 text-slate-400"
              }`}
            >
              {shiftMode === "caps" ? "⇪ CAPS" : shiftMode === "shift" ? "⇧ Shift" : "⇧ caps"}
            </button>
            {rowLetters3.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {isUpperDisplay ? char : char.toLowerCase()}
              </button>
            ))}
            <button
              type="button"
              onClick={handleBackspace}
              className="w-12 sm:w-16 h-11 sm:h-12 bg-slate-800 active:bg-rose-600 active:text-white text-slate-200 rounded-lg text-sm font-bold flex items-center justify-center active:scale-90 transition-none shrink-0"
            >
              ⌫
            </button>
          </div>
        </>
      )}

      {/* Symbols Rows */}
      {(mode === "SYM" || mode === "123") && (
        <>
          <div className="flex justify-center gap-0.5 sm:gap-1">
            {rowSym1.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-mono font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {char}
              </button>
            ))}
          </div>
          <div className="flex justify-center gap-0.5 sm:gap-1">
            {rowSym2.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-mono font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {char}
              </button>
            ))}
          </div>
          <div className="flex justify-center gap-0.5 sm:gap-1">
            {rowSym3.map((char) => (
              <button
                key={char}
                type="button"
                onClick={() => handleKeyPress(char)}
                className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 active:text-white border border-slate-800 rounded-lg text-slate-100 font-mono font-black text-base sm:text-lg flex items-center justify-center active:scale-90 transition-none shadow-sm"
              >
                {char}
              </button>
            ))}
            <button
              type="button"
              onClick={handleBackspace}
              className="w-12 sm:w-16 h-11 sm:h-12 bg-slate-800 active:bg-rose-600 active:text-white text-slate-200 rounded-lg text-sm font-bold flex items-center justify-center active:scale-90 transition-none shrink-0"
            >
              ⌫
            </button>
          </div>
        </>
      )}

      {/* Bottom Bar: Space & Enter (Perfectly Centered Space Bar) */}
      <div className="flex items-center justify-between gap-1 sm:gap-1.5 pt-1">
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => handleKeyPress(",")}
            className="w-10 sm:w-12 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 border border-slate-800 text-slate-200 font-bold text-base rounded-lg transition-none active:scale-90"
          >
            ,
          </button>
          <button
            type="button"
            onClick={() => handleKeyPress(".")}
            className="w-10 sm:w-12 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 border border-slate-800 text-slate-200 font-bold text-base rounded-lg"
          >
            .
          </button>
        </div>

        <button
          type="button"
          onClick={() => onChange(value + " ")}
          className="flex-1 h-11 sm:h-12 bg-slate-900 active:bg-indigo-600 border border-slate-800 text-slate-200 font-black text-xs sm:text-sm rounded-lg flex items-center justify-center tracking-widest transition-none active:scale-[0.98] shadow-sm"
        >
          SPASI
        </button>

        <button
          type="button"
          onClick={handleEnter}
          className="w-20 sm:w-24 h-11 sm:h-12 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-black text-xs sm:text-sm rounded-lg flex items-center justify-center transition-none active:scale-90 shadow-md shadow-indigo-600/30 shrink-0"
        >
          ENTER ↵
        </button>
      </div>
    </div>
  );
}
