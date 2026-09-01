import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  BookOpen, Clock, Play, Lock, Search, RefreshCw, CheckCircle,
  AlertCircle, QrCode, Camera, CameraOff, ScanLine,
  Trophy, Award, TrendingUp, Crown, CalendarX,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { studentExamApi } from "../../api/studentExam";
import type { StudentSchedule, ClassLeaderboardResponse } from "../../api/studentExam";
import { StudentCbtEngineView } from "./StudentCbtEngineView";
import { MultilingualTypingWelcome } from "../../components/ui/MultilingualTypingWelcome";

// jsQR loaded dynamically via script tag with multiple CDN fallbacks
let _jsQR: any = null;
async function loadJsQR(): Promise<any> {
  if (_jsQR) return _jsQR;
  if (typeof window !== "undefined" && (window as any).jsQR) {
    _jsQR = (window as any).jsQR;
    return _jsQR;
  }

  const cdns = [
    "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js",
    "https://unpkg.com/jsqr@1.4.0/dist/jsQR.js",
    "https://cdnjs.cloudflare.com/ajax/libs/jsQR/1.4.0/jsQR.min.js",
  ];

  for (const url of cdns) {
    const loaded = await new Promise<any>((resolve) => {
      const s = document.createElement("script");
      s.src = url;
      s.onload = () => resolve((window as any).jsQR);
      s.onerror = () => resolve(null);
      document.head.appendChild(s);
    });
    if (loaded) {
      _jsQR = loaded;
      return _jsQR;
    }
  }

  return (typeof window !== "undefined" ? (window as any).jsQR : null) || null;
}

interface StudentSchedulesViewProps {
  mode?: "DASHBOARD" | "HISTORY";
  onStartExam?: (schedule: StudentSchedule) => void;
}

export function StudentSchedulesView({ mode = "DASHBOARD", onStartExam }: StudentSchedulesViewProps = {}) {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [schedules, setSchedules] = useState<StudentSchedule[]>([]);
  const [leaderboardData, setLeaderboardData] = useState<ClassLeaderboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSchedule, setSelectedSchedule] = useState<StudentSchedule | null>(null);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [activeExamSchedule, setActiveExamSchedule] = useState<StudentSchedule | null>(null);

  // QR state
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);
  const [qrScanTarget, setQrScanTarget] = useState<StudentSchedule | null>(null);
  const [checkinSuccess, setCheckinSuccess] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [manualTokenInput, setManualTokenInput] = useState("");

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scanIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const checkinLoadingRef = useRef(false);

  const stopCamera = useCallback(() => {
    if (scanIntervalRef.current) { clearInterval(scanIntervalRef.current); scanIntervalRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach((t) => t.stop()); streamRef.current = null; }
    setIsCameraActive(false);
  }, []);

  const autoStartedRef = useRef<Record<number, boolean>>({});

  const handleStartExam = useCallback((sch: StudentSchedule) => {
    if (onStartExam) {
      onStartExam(sch);
    } else {
      setActiveExamSchedule(sch);
    }
  }, [onStartExam]);

  const getTimeStatus = useCallback((start: string, end: string) => {
    const now = Date.now(), s = new Date(start).getTime(), e = new Date(end).getTime();
    if (now < s) return "FUTURE";
    if (now <= e) return "OPEN";
    return "PASSED";
  }, []);

  const performCheckin = useCallback(async (token: string) => {
    const clean = token.trim();
    if (!clean || checkinLoadingRef.current) return;
    checkinLoadingRef.current = true;
    try {
      const result = await studentExamApi.checkin(clean, qrScanTarget?.schedule_id);
      setCheckinSuccess(true);
      showToast({ type: "success", title: "Absensi Berhasil!", message: `Kamu terdaftar untuk "${result.schedule_title}".` });
      const updatedData = await studentExamApi.getMySchedules();
      setSchedules(updatedData);

      const target = updatedData.find((s) => String(s.schedule_id) === String(result.schedule_id)) || qrScanTarget;
      if (
        target &&
        !["SUBMITTED", "GRADED", "GRADING", "CANCELLED"].includes(target.attempt_status)
      ) {
        autoStartedRef.current[target.schedule_id] = true;
        setTimeout(() => {
          setIsQrModalOpen(false);
          setCheckinSuccess(false);
          setQrScanTarget(null);
          showToast({ type: "success", title: "Membuka Ujian Otomatis!", message: `Absensi valid. Langsung masuk ke lembar ujian...` });
          handleStartExam(target);
        }, 800);
      } else {
        setTimeout(() => { setIsQrModalOpen(false); setCheckinSuccess(false); setQrScanTarget(null); }, 2000);
      }
    } catch (err: any) {
      showToast({ type: "error", title: "Absensi Gagal", message: err?.message || "Token tidak valid atau sudah kadaluarsa." });
    } finally {
      checkinLoadingRef.current = false;
    }
  }, [showToast, getTimeStatus, handleStartExam]);

  const processImageFileForQr = async (file: File) => {
    try {
      showToast({ type: "info", title: "Membaca QR...", message: "Sedang memproses foto dari kamera..." });
      const lib = await loadJsQR();
      if (!lib) throw new Error("jsQR library gagal dimuat dari server CDN.");

      const img = new window.Image();
      const url = URL.createObjectURL(file);

      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("Gagal membaca data gambar dari kamera."));
        img.src = url;
      });

      let maxDim = 1000;
      let width = img.width;
      let height = img.height;
      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round((height * maxDim) / width);
          width = maxDim;
        } else {
          width = Math.round((width * maxDim) / height);
          height = maxDim;
        }
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Gagal menginisialisasi canvas.");

      ctx.drawImage(img, 0, 0, width, height);
      const imageData = ctx.getImageData(0, 0, width, height);
      const code = lib(imageData.data, width, height);
      URL.revokeObjectURL(url);

      if (code?.data) {
        stopCamera();
        performCheckin(code.data);
      } else {
        showToast({
          type: "warning",
          title: "QR Tidak Terdeteksi",
          message: "Foto QR Code tidak terbaca. Pastikan kamera diarahkan dengan jelas dan fokus pada QR Code.",
        });
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Membaca Kamera",
        message: err?.message || "Terjadi kesalahan saat memproses foto kamera.",
      });
    }
  };

  const handleCapturePhotoQR = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await processImageFileForQr(file);
    e.target.value = "";
  };

  const startCamera = useCallback(async () => {
    setCameraError(null);
    try {
      // 1. Check if running inside Lockxam Native Android APK Bridge
      if (typeof window !== "undefined" && (window as any).LockxamBridge?.scanQR) {
        (window as any).onQrResult = (token: string | null, errorMsg?: string) => {
          if (token) {
            performCheckin(token);
          } else if (errorMsg) {
            setCameraError(`Kamera Native APK: ${errorMsg}`);
          }
        };
        (window as any).LockxamBridge.scanQR();
        return;
      }

      const lib = await loadJsQR();
      if (!lib) throw new Error("jsQR library gagal dimuat.");

      // Polyfill navigator.mediaDevices for legacy browsers / HTTP WebViews
      if (typeof navigator !== "undefined" && !(navigator as any).mediaDevices) {
        (navigator as any).mediaDevices = {};
      }
      if (navigator?.mediaDevices && !(navigator.mediaDevices as any).getUserMedia) {
        const legacyGetUserMedia =
          (navigator as any).getUserMedia ||
          (navigator as any).webkitGetUserMedia ||
          (navigator as any).mozGetUserMedia ||
          (navigator as any).msGetUserMedia;

        if (legacyGetUserMedia) {
          (navigator.mediaDevices as any).getUserMedia = function (constraints: MediaStreamConstraints) {
            return new Promise((resolve, reject) => {
              legacyGetUserMedia.call(navigator, constraints, resolve, reject);
            });
          };
        }
      }

      let stream: MediaStream | null = null;
      if (navigator?.mediaDevices?.getUserMedia) {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        } catch (_envErr) {
          try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
          } catch (_userErr) {
            stream = await navigator.mediaDevices.getUserMedia({ video: true });
          }
        }
      }

      if (!stream) {
        throw new Error(
          "Kamera live di-block browser pada koneksi HTTP. Klik tombol 'Ambil Foto QR' di bawah untuk scan via kamera HP."
        );
      }

      streamRef.current = stream;
      setIsCameraActive(true);

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.setAttribute("playsinline", "true");
          videoRef.current.setAttribute("autoplay", "true");
          videoRef.current.play().catch((e) => console.warn("Video play error:", e));
        }
      }, 50);

      scanIntervalRef.current = setInterval(() => {
        if (!videoRef.current || !canvasRef.current) return;
        const video = videoRef.current;
        if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
        const canvas = canvasRef.current;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = lib(imageData.data, canvas.width, canvas.height);
        if (code?.data) { stopCamera(); performCheckin(code.data); }
      }, 200);
    } catch (err: any) {
      setCameraError(err?.name === "NotAllowedError" ? "Izin kamera ditolak. Aktifkan izin kamera di pengaturan HP / browser." : `${err?.message || "Tidak dapat mengakses kamera"}`);
    }
  }, [stopCamera, performCheckin]);

  const openQrModal = (sch: StudentSchedule) => {
    setQrScanTarget(sch); setCheckinSuccess(false); setCameraError(null); setIsCameraActive(false); setIsQrModalOpen(true);
  };
  const closeQrModal = () => { stopCamera(); setIsQrModalOpen(false); setQrScanTarget(null); setCheckinSuccess(false); };

  useEffect(() => {
    if (isQrModalOpen && !checkinSuccess) { const t = setTimeout(() => startCamera(), 400); return () => clearTimeout(t); }
    else stopCamera();
  }, [isQrModalOpen, checkinSuccess]);

  useEffect(() => {
    (window as any).onNativeQrFrame = async (base64Str: string) => {
      try {
        const lib = await loadJsQR();
        if (!lib) return;
        const img = new window.Image();
        img.onload = () => {
          const canvas = document.createElement("canvas");
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext("2d");
          if (!ctx) return;
          ctx.drawImage(img, 0, 0);
          const imageData = ctx.getImageData(0, 0, img.width, img.height);
          const code = lib(imageData.data, img.width, img.height);
          if (code?.data) {
            if ((window as any).LockxamBridge?.onQrDecoded) {
              (window as any).LockxamBridge.onQrDecoded(code.data);
            }
            performCheckin(code.data);
          }
        };
        img.src = `data:image/jpeg;base64,${base64Str}`;
      } catch (e) {
        console.warn("Native QR frame decode error:", e);
      }
    };

    return () => {
      delete (window as any).onNativeQrFrame;
    };
  }, [performCheckin]);

  useEffect(() => () => stopCamera(), []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [schedData, lbData] = await Promise.all([
        studentExamApi.getMySchedules(),
        studentExamApi.getClassLeaderboard().catch(() => null),
      ]);
      setSchedules(schedData);
      if (lbData) setLeaderboardData(lbData);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat Data", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    (window as any).LockxamBridge?.exitKioskMode?.();
    loadData();
  }, []);

  // Register future checked-in exam times to Native Android background lock scheduler
  useEffect(() => {
    const bridge = (window as any).LockxamBridge;
    for (const sch of schedules) {
      if (sch.has_checked_in && !["SUBMITTED", "GRADED", "GRADING", "CANCELLED"].includes(sch.attempt_status)) {
        const startTimeMs = new Date(sch.start_time).getTime();
        if (startTimeMs > Date.now()) {
          bridge?.scheduleExamAutoStart?.(startTimeMs);
        }
      }
    }
  }, [schedules]);

  // Handle native trigger when Android forces app back to foreground at exam start time
  useEffect(() => {
    (window as any).onNativeExamAutoLockTriggered = () => {
      const target = schedules.find(
        (s) => s.has_checked_in && !["SUBMITTED", "GRADED", "GRADING", "CANCELLED"].includes(s.attempt_status)
      );
      if (target) {
        showToast({
          type: "success",
          title: "Ujian Dimulai & HP Terkunci!",
          message: `Jam ujian telah tiba. Aplikasi otomatis terkunci ke Mode Ujian.`,
        });
        handleStartExam(target);
      }
    };
    return () => {
      delete (window as any).onNativeExamAutoLockTriggered;
    };
  }, [schedules, showToast, handleStartExam]);

  // Auto-start exam when checked in and exam start time arrives (every 2s check)
  useEffect(() => {
    const checkAutoStart = () => {
      const now = Date.now();
      for (const sch of schedules) {
        if (!sch.has_checked_in) continue;
        if (["SUBMITTED", "GRADED", "GRADING", "CANCELLED"].includes(sch.attempt_status)) continue;

        const startTime = new Date(sch.start_time).getTime();
        const endTime = new Date(sch.end_time).getTime();

        if (now >= startTime && now <= endTime) {
          if (!autoStartedRef.current[sch.schedule_id]) {
            autoStartedRef.current[sch.schedule_id] = true;
            showToast({
              type: "success",
              title: "Jam Ujian Tiba!",
              message: `Waktu ujian untuk "${sch.title}" telah tiba. Membuka lembar ujian secara otomatis...`,
            });
            setTimeout(() => {
              handleStartExam(sch);
            }, 800);
            break;
          }
        }
      }
    };

    checkAutoStart();
    const interval = setInterval(checkAutoStart, 2000);
    return () => clearInterval(interval);
  }, [schedules, showToast, handleStartExam]);

  const formatDateTime = (dtStr: string) => {
    if (!dtStr) return "-";
    try { return new Date(dtStr).toLocaleString("id-ID", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
    catch { return dtStr; }
  };

  const [historyTab, setHistoryTab] = useState<"COMPLETED" | "MISSED">("COMPLETED");

  const isExamPassed = useCallback((sch: StudentSchedule) => {
    if (sch.category === "MISSED") return true;
    const now = Date.now(), e = new Date(sch.end_time).getTime();
    return now > e && !["SUBMITTED", "GRADED", "GRADING"].includes(sch.attempt_status);
  }, []);

  // Performance Stats
  const completedExams = useMemo(() => {
    return schedules.filter(s => s.category === "COMPLETED" || ["SUBMITTED", "GRADED", "GRADING"].includes(s.attempt_status));
  }, [schedules]);

  const missedExams = useMemo(() => {
    return schedules.filter(s => {
      if (s.category === "COMPLETED" || ["SUBMITTED", "GRADED", "GRADING"].includes(s.attempt_status)) return false;
      return s.category === "MISSED" || isExamPassed(s);
    });
  }, [schedules, isExamPassed]);

  const upcomingExams = useMemo(() => {
    return schedules.filter(s => {
      if (s.category === "COMPLETED" || ["SUBMITTED", "GRADED", "GRADING"].includes(s.attempt_status)) return false;
      if (s.category === "MISSED" || isExamPassed(s)) return false;
      return true;
    });
  }, [schedules, isExamPassed]);

  const avgScore = useMemo(() => {
    const scores = completedExams.map(s => s.final_score).filter((sc): sc is number => sc !== null && sc !== undefined);
    if (scores.length === 0) return null;
    const sum = scores.reduce((a, b) => a + b, 0);
    return (sum / scores.length).toFixed(1);
  }, [completedExams]);

  const filteredUpcomingExams = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return upcomingExams.filter((s) => {
      return s.title.toLowerCase().includes(q) || (s.subject_name || "").toLowerCase().includes(q);
    });
  }, [upcomingExams, searchQuery]);

  const filteredCompletedExams = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return completedExams.filter((s) => {
      return s.title.toLowerCase().includes(q) || (s.subject_name || "").toLowerCase().includes(q);
    });
  }, [completedExams, searchQuery]);

  const filteredMissedExams = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return missedExams.filter((s) => {
      return s.title.toLowerCase().includes(q) || (s.subject_name || "").toLowerCase().includes(q);
    });
  }, [missedExams, searchQuery]);

  const groupedHistory = useMemo(() => {
    const map: Record<string, StudentSchedule[]> = {};
    for (const sch of filteredCompletedExams) {
      const groupKey = (sch as any).package_title || (sch as any).package_name || (sch as any).exam_package_name || "Paket Ujian Sekolah";
      if (!map[groupKey]) map[groupKey] = [];
      map[groupKey].push(sch);
    }
    return Object.entries(map);
  }, [filteredCompletedExams]);

  if (activeExamSchedule) {
    if (onStartExam) {
      onStartExam(activeExamSchedule);
      setActiveExamSchedule(null);
      return null;
    }
    return <StudentCbtEngineView schedule={activeExamSchedule} onExit={() => { setActiveExamSchedule(null); loadData(); }} />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Banner */}
      <div className="glass-panel p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="indigo">STUDENT PORTAL</Badge>
            <Badge variant="emerald">{mode === "DASHBOARD" ? "BERANDA KELAS & UJIAN" : "RIWAYAT UJIAN"}</Badge>
          </div>
          <MultilingualTypingWelcome userName={user?.full_name || user?.name || user?.username || "Siswa Equigrade"} />
          <p className="text-xs text-slate-400 mt-2">
            {mode === "DASHBOARD"
              ? "Pantau jadwal ujian mendatang, performa akademik, dan peringkat kelas Anda."
              : "Seluruh riwayat pengerjaan ujian CBT dan nilai terverifikasi Anda tersimpan di bawah."}
          </p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />} onClick={loadData}>Refresh Data</Button>
      </div>

      {/* ── MODE DASHBOARD: Modern 2-Column Responsive Layout ── */}
      {mode === "DASHBOARD" ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* 👈 KOLOM KIRI (lg:col-span-5): Analytics Bar & Leaderboard Widget */}
          <div className="lg:col-span-5 space-y-6">
            {/* Performance Analytics Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="glass-panel p-4 border border-slate-800 flex items-center gap-3 bg-gradient-to-br from-indigo-950/30 to-slate-900/60">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                  <Trophy className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-medium block">Rata-Rata Nilai</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">
                    {avgScore !== null ? <span className="text-emerald-400">{avgScore}</span> : <span className="text-slate-500 text-xs font-semibold">Belum Ada</span>}
                  </p>
                </div>
              </div>

              <div className="glass-panel p-4 border border-slate-800 flex items-center gap-3 bg-gradient-to-br from-emerald-950/30 to-slate-900/60">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                  <Award className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-medium block">Ujian Selesai</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">{completedExams.length} <span className="text-xs text-slate-400 font-normal">Sesi</span></p>
                </div>
              </div>

              <div className="glass-panel p-4 border border-slate-800 flex items-center gap-3 bg-gradient-to-br from-amber-950/30 to-slate-900/60">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                  <Crown className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-medium block">Peringkat Kelas</span>
                  <p className="text-lg font-black text-amber-300 mt-0.5">
                    {leaderboardData?.rank_self ? `#${leaderboardData.rank_self}` : <span className="text-slate-500 text-xs font-semibold">-</span>}
                  </p>
                </div>
              </div>

              <div className="glass-panel p-4 border border-slate-800 flex items-center gap-3 bg-gradient-to-br from-purple-950/30 to-slate-900/60">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 font-medium block">Ujian Akan Datang</span>
                  <p className="text-lg font-black text-slate-100 mt-0.5">{upcomingExams.length} <span className="text-xs text-slate-400 font-normal">Jadwal</span></p>
                </div>
              </div>
            </div>

            {/* Class Leaderboard Widget */}
            {leaderboardData && leaderboardData.leaderboard.length > 0 && (
              <div className="glass-panel p-5 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
                      <Trophy className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-100 text-xs flex items-center gap-2">
                        Leaderboard Performa Kelas
                        <Badge variant="amber">TOP RANK</Badge>
                      </h3>
                      <p className="text-[10px] text-slate-400">Peringkat berdasarkan rata-rata nilai CBT</p>
                    </div>
                  </div>
                  {leaderboardData.rank_self && (
                    <span className="text-xs font-black text-emerald-400">Posisi #{leaderboardData.rank_self}</span>
                  )}
                </div>

                <div className="space-y-2 pt-1">
                  {leaderboardData.leaderboard.slice(0, 5).map((item) => (
                    <div
                      key={item.student_id}
                      className={`p-3 rounded-xl border flex items-center justify-between transition-all ${
                        item.is_self
                          ? "bg-indigo-950/60 border-indigo-500/60 shadow-md shadow-indigo-500/10"
                          : item.rank === 1
                          ? "bg-amber-950/40 border-amber-500/40"
                          : item.rank === 2
                          ? "bg-slate-900/80 border-slate-400/40"
                          : item.rank === 3
                          ? "bg-amber-900/20 border-amber-700/40"
                          : "bg-slate-900/60 border-slate-800"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-black text-xs ${
                          item.rank === 1 ? "bg-amber-400 text-slate-950" : item.rank === 2 ? "bg-slate-300 text-slate-950" : item.rank === 3 ? "bg-amber-700 text-white" : "bg-slate-800 text-slate-300"
                        }`}>
                          {item.rank === 1 ? "🥇" : item.rank === 2 ? "🥈" : item.rank === 3 ? "🥉" : item.avatar_initial}
                        </div>
                        <div>
                          <p className={`text-xs font-bold ${item.is_self ? "text-indigo-300" : "text-slate-200"}`}>
                            {item.student_name} {item.is_self && "(Kamu)"}
                          </p>
                          <span className="text-[9px] text-slate-400 block">{item.total_exams} Ujian Diikuti</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="text-xs font-black text-emerald-400 block">{item.avg_score}</span>
                        <span className="text-[9px] text-slate-500 font-semibold">Rata-Rata</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 👉 KOLOM KANAN (lg:col-span-7): Jadwal Ujian Akan Datang Cards */}
          <div className="lg:col-span-7 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400" />
                Jadwal Ujian Akan Datang ({filteredUpcomingExams.length})
              </h3>

              <div className="w-full sm:w-56">
                <Input placeholder="Cari ujian..." leftIcon={<Search className="w-4 h-4 text-slate-400" />} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              </div>
            </div>

            {/* Alert info if there are missed exams */}
            {missedExams.length > 0 && !searchQuery && (
              <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-900/40 flex items-center justify-between gap-3 text-xs text-rose-300">
                <div className="flex items-center gap-2.5">
                  <CalendarX className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>
                    Anda memiliki <strong>{missedExams.length} ujian yang terlewat</strong> (waktu pengerjaan telah berakhir).
                  </span>
                </div>
                <span className="text-[10px] text-rose-400 font-bold uppercase tracking-wider shrink-0 bg-rose-950/60 px-2 py-1 rounded-lg border border-rose-800/40">
                  Lihat Riwayat
                </span>
              </div>
            )}

            {/* Cards Grid */}
            {isLoading ? (
              <div className="glass-panel p-12 text-center flex flex-col items-center gap-3"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" /><p className="text-xs text-slate-400">Memuat data...</p></div>
            ) : filteredUpcomingExams.length === 0 ? (
              <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
                <BookOpen className="w-12 h-12 text-slate-600" />
                <h3 className="text-sm font-bold text-slate-300">
                  {searchQuery ? "Tidak Ada Hasil" : "Belum Ada Jadwal Ujian Mendatang"}
                </h3>
                <p className="text-xs text-slate-500 max-w-xs">
                  {searchQuery ? `Tidak ditemukan jadwal untuk "${searchQuery}".` : "Tidak ada ujian yang sedang berlangsung atau akan datang untuk kelas Anda saat ini."}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredUpcomingExams.map((sch) => {
                  const ts = getTimeStatus(sch.start_time, sch.end_time);
                  const isAttempted = ["IN_PROGRESS","PAUSED"].includes(sch.attempt_status);
                  const isSubmitted = ["SUBMITTED", "GRADED", "GRADING"].includes(sch.attempt_status);
                  const isCancelled = sch.status === "CANCELLED";
                  const canStart = (ts === "OPEN" || isAttempted) && !isSubmitted && !isCancelled;
                  const isFuture = ts === "FUTURE" && !isSubmitted && !isCancelled;
                  const checked = sch.has_checked_in;
                  return (
                    <div key={sch.schedule_id} className={`glass-panel p-5 flex flex-col justify-between gap-4 border transition-all duration-200 ${isCancelled ? "opacity-60 grayscale bg-slate-950/60 border-slate-800/60" : canStart ? "border-indigo-500/40 hover:border-indigo-500/70 shadow-lg shadow-indigo-500/5" : checked && isFuture ? "border-emerald-500/30 hover:border-emerald-500/50" : "border-slate-800 hover:border-slate-700"}`}>
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-bold text-slate-100 text-sm line-clamp-1">{sch.title}</h3>
                            <div className="flex items-center gap-1.5 mt-1">
                              <Badge variant="indigo">{sch.subject_name}</Badge>
                              <Badge variant="slate">{sch.duration_minutes} Menit</Badge>
                            </div>
                          </div>
                          {isCancelled ? <Badge variant="slate">DIBATALKAN</Badge>
                            : isSubmitted ? <Badge variant="emerald">SUBMITTED</Badge>
                            : isAttempted ? <Badge variant="amber">SEDANG UJIAN</Badge>
                            : ts === "OPEN" ? <Badge variant="emerald">SIAP UJIAN</Badge>
                            : isFuture && checked ? <Badge variant="emerald">HADIR ✓</Badge>
                            : isFuture ? <Badge variant="slate">BELUM DIMULAI</Badge>
                            : <Badge variant="crimson">BERAKHIR</Badge>}
                        </div>

                        <div className="bg-slate-900/60 p-2.5 rounded-xl border border-slate-850 text-[11px] space-y-1 text-slate-400">
                          <div className="flex justify-between items-center"><span>Mulai:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.start_time)}</span></div>
                          <div className="flex justify-between items-center"><span>Selesai:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.end_time)}</span></div>
                          {checked && sch.checked_in_at && (
                            <div className="flex justify-between items-center pt-1 border-t border-slate-800">
                              <span className="text-emerald-400 font-semibold flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Absen QR</span>
                              <span className="text-emerald-300 font-semibold">{new Date(sch.checked_in_at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        {!isSubmitted && !isCancelled && (
                          <button
                            id={`qr-btn-${sch.schedule_id}`}
                            onClick={() => !checked && openQrModal(sch)}
                            disabled={checked}
                            className={`w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-bold transition-all duration-200 border ${checked ? "bg-emerald-950/60 border-emerald-700/50 text-emerald-300 opacity-90 cursor-default" : "bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/20 animate-pulse"}`}
                          >
                            {checked ? <><CheckCircle className="w-3.5 h-3.5" /> Sudah Absen ✅</> : <><QrCode className="w-3.5 h-3.5" /> Scan QR Absensi</>}
                          </button>
                        )}

                        {isCancelled ? (
                          <Button variant="secondary" size="sm" className="w-full cursor-not-allowed opacity-80" disabled leftIcon={<AlertCircle className="w-3.5 h-3.5 text-slate-500" />}>Jadwal Dibatalkan</Button>
                        ) : isSubmitted ? (
                          <Button variant="secondary" size="sm" className="w-full" disabled leftIcon={<CheckCircle className="w-3.5 h-3.5 text-emerald-400" />}>Ujian Dikumpulkan</Button>
                        ) : !checked ? (
                          <Button variant="secondary" size="sm" className="w-full cursor-not-allowed opacity-80 text-[11px]" disabled leftIcon={<Lock className="w-3.5 h-3.5 text-amber-400" />}>Wajib Scan QR Absensi</Button>
                        ) : isAttempted ? (
                          <Button variant="primary" size="sm" className="w-full" leftIcon={<Play className="w-3.5 h-3.5" />} onClick={() => { setSelectedSchedule(sch); setIsConfirmModalOpen(true); }}>Lanjutkan Ujian</Button>
                        ) : canStart ? (
                          <Button variant="primary" size="sm" className="w-full" leftIcon={<Play className="w-3.5 h-3.5" />} onClick={() => { setSelectedSchedule(sch); setIsConfirmModalOpen(true); }}>Mulai Ujian</Button>
                        ) : isFuture ? (
                          <Button variant="secondary" size="sm" className="w-full" disabled leftIcon={<Clock className="w-3.5 h-3.5" />}>Menunggu Jam Ujian</Button>
                        ) : (
                          <Button variant="secondary" size="sm" className="w-full" disabled leftIcon={<AlertCircle className="w-3.5 h-3.5" />}>Sesi Berakhir</Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : (
        /* ── MODE HISTORY: Full Width Transkrip & Ujian Terlewat Tabs ── */
        <div className="space-y-5">
          {/* Top Bar with Tabs and Search */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHistoryTab("COMPLETED")}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  historyTab === "COMPLETED"
                    ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20"
                    : "bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                <Award className="w-4 h-4" />
                Ujian Selesai ({filteredCompletedExams.length})
              </button>
              <button
                onClick={() => setHistoryTab("MISSED")}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  historyTab === "MISSED"
                    ? "bg-rose-600 text-white shadow-lg shadow-rose-500/20"
                    : "bg-slate-900/80 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                <CalendarX className="w-4 h-4" />
                Ujian Terlewat ({filteredMissedExams.length})
                {missedExams.length > 0 && (
                  <span className={`ml-1 px-1.5 py-0.2 text-[10px] rounded-full ${
                    historyTab === "MISSED" ? "bg-white/20 text-white" : "bg-rose-950 border border-rose-700/50 text-rose-300"
                  }`}>
                    {missedExams.length}
                  </span>
                )}
              </button>
            </div>

            <div className="w-full sm:w-64">
              <Input placeholder="Cari ujian..." leftIcon={<Search className="w-4 h-4 text-slate-400" />} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </div>
          </div>

          {/* TAB 1: UJIAN SELESAI */}
          {historyTab === "COMPLETED" && (
            <div>
              {filteredCompletedExams.length === 0 ? (
                <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
                  <BookOpen className="w-12 h-12 text-slate-600" />
                  <h3 className="text-sm font-bold text-slate-300">
                    {searchQuery ? "Tidak Ditemukan" : "Belum Ada Riwayat Ujian Selesai"}
                  </h3>
                  <p className="text-xs text-slate-500 max-w-xs">
                    {searchQuery ? `Tidak ada ujian selesai yang cocok dengan "${searchQuery}".` : "Anda belum pernah menyelesaikan ujian CBT."}
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {groupedHistory.map(([pkgTitle, schList], gIdx) => (
                    <div key={gIdx} className="space-y-3">
                      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
                        <Trophy className="w-4 h-4 text-amber-400" />
                        <h4 className="font-bold text-slate-200 text-sm">{pkgTitle}</h4>
                        <Badge variant="indigo">{schList.length} Mata Pelajaran</Badge>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {schList.map((sch) => (
                          <div key={sch.schedule_id} className="glass-panel p-5 flex flex-col justify-between gap-4 border border-slate-800">
                            <div className="space-y-3">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <h3 className="font-bold text-slate-100 text-base">{sch.subject_name}</h3>
                                  <p className="text-[11px] text-slate-400 mt-0.5">{sch.title}</p>
                                </div>
                                <Badge variant="emerald">SUBMITTED</Badge>
                              </div>

                              <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1.5 text-slate-400">
                                <div className="flex justify-between items-center"><span>Selesai Pada:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.end_time)}</span></div>
                                {sch.final_score !== null && sch.final_score !== undefined && (
                                  <div className="flex justify-between items-center pt-2 border-t border-slate-800">
                                    <span className="text-indigo-300 font-bold flex items-center gap-1"><Trophy className="w-4 h-4 text-amber-400" /> Nilai Akhir:</span>
                                    <span className="text-emerald-400 font-black text-base">{sch.final_score} / 100</span>
                                  </div>
                                )}
                              </div>
                            </div>

                            <Button variant="secondary" className="w-full" disabled leftIcon={<CheckCircle className="w-4 h-4 text-emerald-400" />}>
                              Ujian Berhasil Dikumpulkan
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: UJIAN TERLEWAT */}
          {historyTab === "MISSED" && (
            <div>
              {filteredMissedExams.length === 0 ? (
                <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
                  <CheckCircle className="w-12 h-12 text-emerald-500/60" />
                  <h3 className="text-sm font-bold text-slate-300">
                    {searchQuery ? "Tidak Ditemukan" : "Tidak Ada Ujian Terlewat"}
                  </h3>
                  <p className="text-xs text-slate-500 max-w-xs">
                    {searchQuery ? `Tidak ada ujian terlewat yang cocok dengan "${searchQuery}".` : "Hebat! Anda tidak melewatkan sesi ujian apapun."}
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-900/40 text-xs text-rose-300 flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Daftar ujian di bawah ini adalah jadwal yang telah melewati batas waktu pengerjaan dan Anda tidak bergabung atau mengumpulkannya.</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredMissedExams.map((sch) => (
                      <div key={sch.schedule_id} className="glass-panel p-5 flex flex-col justify-between gap-4 border border-rose-900/30 bg-gradient-to-br from-rose-950/20 to-slate-900/60">
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h3 className="font-bold text-slate-100 text-base">{sch.subject_name}</h3>
                              <p className="text-[11px] text-slate-400 mt-0.5">{sch.title}</p>
                            </div>
                            <Badge variant="crimson">TERLEWAT</Badge>
                          </div>

                          <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1.5 text-slate-400">
                            <div className="flex justify-between items-center">
                              <span>Waktu Mulai:</span>
                              <span className="font-semibold text-slate-200">{formatDateTime(sch.start_time)}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span>Batas Selesai:</span>
                              <span className="font-semibold text-rose-300">{formatDateTime(sch.end_time)}</span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span>Durasi:</span>
                              <span className="font-semibold text-slate-300">{sch.duration_minutes} Menit</span>
                            </div>
                            <div className="pt-2 border-t border-slate-800 text-[11px] text-rose-400/90 flex items-start gap-1.5">
                              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-rose-400" />
                              <span>Tidak mengikuti ujian hingga batas waktu berakhir.</span>
                            </div>
                          </div>
                        </div>

                        <Button variant="secondary" className="w-full opacity-70 cursor-not-allowed text-rose-300" disabled leftIcon={<CalendarX className="w-3.5 h-3.5 text-rose-400" />}>
                          Sesi Ujian Telah Berakhir
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Modal Konfirmasi Sesi Ujian */}
      <Modal isOpen={isConfirmModalOpen} onClose={() => setIsConfirmModalOpen(false)} title="Konfirmasi Mulai Ujian">
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">Apakah Anda siap memulai ujian <strong>{selectedSchedule?.title}</strong>?</p>
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-300 space-y-1">
            <p>• Durasi: <strong>{selectedSchedule?.duration_minutes} Menit</strong></p>
            <p>• Pastikan baterai dan koneksi internet dalam keadaan baik.</p>
            {selectedSchedule?.lock_browser && <p className="text-emerald-400 font-semibold">• Aplikasi akan masuk ke Mode Kiosk Terkunci.</p>}
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setIsConfirmModalOpen(false)}>Batal</Button>
            <Button variant="primary" onClick={() => { setIsConfirmModalOpen(false); if (selectedSchedule) handleStartExam(selectedSchedule); }}>Mulai Ujian Sekarang</Button>
          </div>
        </div>
      </Modal>

      {/* Modal QR Code Scanner */}
      <Modal isOpen={isQrModalOpen} onClose={closeQrModal} title={`Scan QR Absensi: ${qrScanTarget?.title || ""}`} maxWidth="sm">
        <div className="space-y-4 text-xs">
          {checkinSuccess ? (
            <div className="p-6 text-center space-y-3">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto animate-bounce" />
              <h3 className="font-bold text-slate-100 text-sm">Absensi Berhasil!</h3>
              <p className="text-slate-400">Data absensi telah tercatat di server pengawas.</p>
            </div>
          ) : (
            <>
              <p className="text-slate-300 text-center">Arahkan kamera HP ke QR Code yang ditampilkan di layar Laptop Pengawas Ujian.</p>
              <div className="relative w-full aspect-square bg-slate-950 rounded-2xl overflow-hidden border-2 border-indigo-500/50 flex items-center justify-center">
                {isCameraActive ? (
                  <>
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover"
                    />
                    <canvas ref={canvasRef} className="hidden" />
                    <div className="absolute inset-0 border-2 border-indigo-400/40 rounded-2xl pointer-events-none flex items-center justify-center">
                      <ScanLine className="w-32 h-32 text-indigo-400 animate-pulse opacity-70" />
                    </div>
                  </>
                ) : (
                  <div className="text-center p-4 space-y-2">
                    {cameraError ? <CameraOff className="w-8 h-8 text-rose-400 mx-auto" /> : <Camera className="w-8 h-8 text-indigo-400 mx-auto animate-pulse" />}
                    <p className="text-slate-400 text-xs">{cameraError || "Membuka kamera..."}</p>
                  </div>
                )}
              </div>

              {/* Dual Touchable Labels for Camera & File Picker */}
              <div className="space-y-2">
                <label
                  htmlFor="native-qr-camera-direct"
                  className="w-full flex items-center justify-center gap-2.5 px-4 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-bold text-xs cursor-pointer shadow-lg shadow-indigo-600/30 transition-all text-center select-none"
                >
                  <Camera className="w-4 h-4 text-emerald-300 shrink-0" />
                  <span>📸 Ambil Foto QR via Kamera HP</span>
                  <input
                    id="native-qr-camera-direct"
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="sr-only"
                    onChange={handleCapturePhotoQR}
                  />
                </label>

                <label
                  htmlFor="native-qr-file-picker"
                  className="w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs cursor-pointer border border-slate-700/60 transition-all text-center select-none"
                >
                  <QrCode className="w-4 h-4 text-indigo-400 shrink-0" />
                  <span>📁 Pilih Foto QR (Galeri / Pengambil File)</span>
                  <input
                    id="native-qr-file-picker"
                    type="file"
                    accept="image/*"
                    className="sr-only"
                    onChange={handleCapturePhotoQR}
                  />
                </label>
              </div>

              {/* Kode Token Presensi 6-Digit Section */}
              <div className="p-3.5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-slate-200">
                    🔑 Kode Token Presensi Pengawas
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">Input Manual / PIN</span>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (manualTokenInput.trim()) {
                      stopCamera();
                      performCheckin(manualTokenInput.trim());
                      setManualTokenInput("");
                    }
                  }}
                  className="flex gap-2"
                >
                  <Input
                    placeholder="Contoh: CHK-123456"
                    value={manualTokenInput}
                    onChange={(e) => setManualTokenInput(e.target.value)}
                    className="text-xs flex-1 font-mono uppercase tracking-wider"
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={!manualTokenInput.trim()}
                  >
                    Kirim
                  </Button>
                </form>
                <p className="text-[10px] text-slate-400 italic">
                  *Minta 6-digit Kode Token kepada Pengawas Ujian jika kamera HP terkendala HTTP/Lokal.
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button variant="outline" onClick={closeQrModal}>Batal</Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  );
}
