import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  BookOpen, Clock, Play, Lock, Search, RefreshCw, CheckCircle,
  AlertCircle, ShieldCheck, QrCode, Camera, CameraOff, ScanLine,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { studentExamApi } from "../../api/studentExam";
import type { StudentSchedule } from "../../api/studentExam";
import { StudentCbtEngineView } from "./StudentCbtEngineView";
import { MultilingualTypingWelcome } from "../../components/ui/MultilingualTypingWelcome";

// jsQR loaded dynamically via script tag
let _jsQR: any = null;
async function loadJsQR(): Promise<any> {
  if (_jsQR) return _jsQR;
  if ((window as any).jsQR) { _jsQR = (window as any).jsQR; return _jsQR; }
  return new Promise<any>((resolve) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js";
    s.onload = () => { _jsQR = (window as any).jsQR; resolve(_jsQR); };
    s.onerror = () => resolve(null);
    document.head.appendChild(s);
  });
}

interface StudentSchedulesViewProps {
  onStartExam?: (schedule: StudentSchedule) => void;
}

export function StudentSchedulesView({ onStartExam }: StudentSchedulesViewProps = {}) {
  const { user } = useAuth();
  const { showToast } = useToast();

  const [schedules, setSchedules] = useState<StudentSchedule[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [selectedSchedule, setSelectedSchedule] = useState<StudentSchedule | null>(null);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [activeExamSchedule, setActiveExamSchedule] = useState<StudentSchedule | null>(null);

  // QR state
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);
  const [qrScanTarget, setQrScanTarget] = useState<StudentSchedule | null>(null);
  const [checkinSuccess, setCheckinSuccess] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);

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

  const performCheckin = useCallback(async (token: string) => {
    const clean = token.trim();
    if (!clean || checkinLoadingRef.current) return;
    checkinLoadingRef.current = true;
    try {
      const result = await studentExamApi.checkin(clean);
      setCheckinSuccess(true);
      showToast({ type: "success", title: "Absensi Berhasil!", message: `Kamu terdaftar untuk "${result.schedule_title}".` });
      await loadSchedules();
      setTimeout(() => { setIsQrModalOpen(false); setCheckinSuccess(false); setQrScanTarget(null); }, 2000);
    } catch (err: any) {
      showToast({ type: "error", title: "Absensi Gagal", message: err?.message || "Token tidak valid atau sudah kadaluarsa." });
    } finally {
      checkinLoadingRef.current = false;
    }
  }, [showToast]);

  const startCamera = useCallback(async () => {
    setCameraError(null);
    try {
      const lib = await loadJsQR();
      if (!lib) throw new Error("jsQR library gagal dimuat.");
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setIsCameraActive(true);
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
      }
    } catch (err: any) {
      setCameraError(err?.name === "NotAllowedError" ? "Izin kamera ditolak. Aktifkan di pengaturan browser HP." : `Kamera error: ${err?.message}`);
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

  useEffect(() => () => stopCamera(), []);

  const loadSchedules = async () => {
    setIsLoading(true);
    try { const data = await studentExamApi.getMySchedules(); setSchedules(data); }
    catch (err: any) { showToast({ type: "error", title: "Gagal Memuat Jadwal", message: err?.message || "Terjadi kesalahan." }); }
    finally { setIsLoading(false); }
  };

  useEffect(() => { loadSchedules(); }, []);

  const formatDateTime = (dtStr: string) => {
    if (!dtStr) return "-";
    try { return new Date(dtStr).toLocaleString("id-ID", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
    catch { return dtStr; }
  };

  const getTimeStatus = (start: string, end: string) => {
    const now = Date.now(), s = new Date(start).getTime(), e = new Date(end).getTime();
    if (now < s) return "FUTURE";
    if (now <= e) return "OPEN";
    return "PASSED";
  };

  const filteredSchedules = useMemo(() => schedules.filter((s) => {
    const q = searchQuery.toLowerCase();
    const matchQ = s.title.toLowerCase().includes(q) || (s.subject_name || "").toLowerCase().includes(q);
    const ts = getTimeStatus(s.start_time, s.end_time);
    if (statusFilter === "READY") return matchQ && (ts === "OPEN" || s.attempt_status === "IN_PROGRESS");
    if (statusFilter === "SUBMITTED") return matchQ && ["SUBMITTED","GRADED"].includes(s.attempt_status);
    return matchQ;
  }), [schedules, searchQuery, statusFilter]);

  if (activeExamSchedule) {
    if (onStartExam) {
      onStartExam(activeExamSchedule);
      setActiveExamSchedule(null);
      return null;
    }
    return <StudentCbtEngineView schedule={activeExamSchedule} onExit={() => { setActiveExamSchedule(null); loadSchedules(); }} />;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Banner */}
      <div className="glass-panel p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="indigo">STUDENT PORTAL</Badge>
            <Badge variant="emerald">AKTIF &amp; TERKUNCI</Badge>
          </div>
          <MultilingualTypingWelcome userName={user?.full_name || user?.name || user?.username || "Siswa Equigrade"} />
          <p className="text-xs text-slate-400 mt-2">Pilih dan ikuti jadwal ujian CBT. Pastikan koneksi internet stabil.</p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />} onClick={loadSchedules}>Refresh</Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          {[["ALL","Semua Jadwal"],["READY","Siap Dikerjakan"],["SUBMITTED","Selesai"]].map(([v, l]) => (
            <button key={v} onClick={() => setStatusFilter(v)} className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${statusFilter === v ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20" : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"}`}>
              {l}{v === "ALL" ? ` (${schedules.length})` : ""}
            </button>
          ))}
        </div>
        <div className="w-full sm:w-64">
          <Input placeholder="Cari ujian atau mapel..." leftIcon={<Search className="w-4 h-4 text-slate-400" />} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
      </div>

      {/* Cards */}
      {isLoading ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center gap-3"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" /><p className="text-xs text-slate-400">Memuat jadwal...</p></div>
      ) : filteredSchedules.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
          <BookOpen className="w-12 h-12 text-slate-600" />
          <h3 className="text-sm font-bold text-slate-300">{searchQuery ? "Tidak Ada Hasil Pencarian" : "Tidak Ada Jadwal Ujian Aktif"}</h3>
          <p className="text-xs text-slate-500 max-w-sm">{searchQuery ? `Tidak ditemukan jadwal untuk "${searchQuery}".` : "Belum ada jadwal aktif untuk kelas Anda."}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredSchedules.map((sch) => {
            const ts = getTimeStatus(sch.start_time, sch.end_time);
            const isAttempted = ["IN_PROGRESS","PAUSED"].includes(sch.attempt_status);
            const isSubmitted = ["SUBMITTED","GRADED"].includes(sch.attempt_status);
            const canStart = (ts === "OPEN" || isAttempted) && !isSubmitted;
            const isFuture = ts === "FUTURE" && !isSubmitted;
            const checked = sch.has_checked_in;
            return (
              <div key={sch.schedule_id} className={`glass-panel p-6 flex flex-col justify-between gap-5 border transition-all duration-200 ${canStart ? "border-indigo-500/40 hover:border-indigo-500/70 shadow-lg shadow-indigo-500/5" : checked && isFuture ? "border-emerald-500/30 hover:border-emerald-500/50" : "border-slate-800 hover:border-slate-700"}`}>
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-bold text-slate-100 text-base">{sch.title}</h3>
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <Badge variant="indigo">{sch.subject_name}</Badge>
                        <Badge variant="slate">{sch.duration_minutes} Menit</Badge>
                      </div>
                    </div>
                    {isSubmitted ? <Badge variant="emerald">SUBMITTED</Badge>
                      : isAttempted ? <Badge variant="amber">SEDANG UJIAN</Badge>
                      : ts === "OPEN" ? <Badge variant="emerald">SIAP UJIAN</Badge>
                      : isFuture && checked ? <Badge variant="emerald">HADIR ✓</Badge>
                      : isFuture ? <Badge variant="slate">BELUM DIMULAI</Badge>
                      : <Badge variant="crimson">BERAKHIR</Badge>}
                  </div>

                  <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1.5 text-slate-400">
                    <div className="flex justify-between items-center"><span>Waktu Mulai:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.start_time)}</span></div>
                    <div className="flex justify-between items-center"><span>Waktu Selesai:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.end_time)}</span></div>
                    {checked && sch.checked_in_at && (
                      <div className="flex justify-between items-center pt-1 border-t border-slate-800">
                        <span className="text-emerald-400 font-semibold flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Absen QR</span>
                        <span className="text-emerald-300 font-semibold">{new Date(sch.checked_in_at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}</span>
                      </div>
                    )}
                  </div>

                  <div className="text-[11px] px-1 text-slate-400">
                    {sch.lock_browser
                      ? <span className="text-emerald-400 font-semibold flex items-center gap-1"><Lock className="w-3 h-3" /> Lockxam Browser Protected</span>
                      : <span>Open Book Exam</span>}
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  {/* Tombol Scan QR Absensi selalu ada jika ujian belum dikumpulkan (sebelum & sesudah jam ujian) */}
                  {!isSubmitted && (
                    <button
                      id={`qr-btn-${sch.schedule_id}`}
                      onClick={() => openQrModal(sch)}
                      className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 border ${checked ? "bg-emerald-950/60 border-emerald-700/50 text-emerald-300 hover:bg-emerald-900/60" : "bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500 shadow-lg shadow-indigo-500/20 animate-pulse"}`}
                    >
                      {checked ? <><CheckCircle className="w-4 h-4" /> Sudah Absen — Scan Ulang</> : <><QrCode className="w-4 h-4" /> Scan QR Absensi Pengawas</>}
                    </button>
                  )}

                  {isSubmitted ? (
                    <Button variant="secondary" className="w-full" disabled leftIcon={<CheckCircle className="w-4 h-4 text-emerald-400" />}>Ujian Sudah Dikumpulkan</Button>
                  ) : isAttempted ? (
                    <Button variant="primary" className="w-full" leftIcon={<Play className="w-4 h-4" />} onClick={() => { setSelectedSchedule(sch); setIsConfirmModalOpen(true); }}>Lanjutkan Ujian</Button>
                  ) : canStart ? (
                    <Button variant="primary" className="w-full" leftIcon={<Play className="w-4 h-4" />} onClick={() => { setSelectedSchedule(sch); setIsConfirmModalOpen(true); }}>Mulai Ujian Sekarang</Button>
                  ) : isFuture ? (
                    <Button variant="secondary" className="w-full" disabled leftIcon={<Clock className="w-4 h-4" />}>Menunggu Jam Ujian</Button>
                  ) : (
                    <Button variant="secondary" className="w-full" disabled leftIcon={<AlertCircle className="w-4 h-4" />}>Sesi Ujian Berakhir</Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* QR Scanner Modal */}
      <Modal isOpen={isQrModalOpen} onClose={closeQrModal} title="Scan QR Absensi" maxWidth="sm">
        <div className="space-y-4">
          {checkinSuccess ? (
            <div className="flex flex-col items-center justify-center py-8 gap-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center animate-bounce"><CheckCircle className="w-9 h-9 text-emerald-400" /></div>
              <p className="text-center font-bold text-emerald-300 text-lg">Absensi Berhasil!</p>
              <p className="text-center text-xs text-slate-400">Data kamu sudah terekam.</p>
            </div>
          ) : (
            <>
              {qrScanTarget && (
                <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 text-xs space-y-1">
                  <p className="text-slate-400">Jadwal Ujian:</p>
                  <p className="font-bold text-slate-100">{qrScanTarget.title}</p>
                  <p className="text-slate-400">{qrScanTarget.subject_name} · {qrScanTarget.duration_minutes} menit</p>
                </div>
              )}

              {/* Camera Stream */}
              <div className="relative w-full aspect-square rounded-2xl overflow-hidden bg-slate-950 border border-slate-800">
                <video ref={videoRef} className="w-full h-full object-cover" muted playsInline autoPlay />
                <canvas ref={canvasRef} className="hidden" />
                {isCameraActive && (
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="relative w-48 h-48">
                      <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-indigo-400 rounded-tl-lg" />
                      <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-indigo-400 rounded-tr-lg" />
                      <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-indigo-400 rounded-bl-lg" />
                      <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-indigo-400 rounded-br-lg" />
                      <style>{`@keyframes scan-line { 0%,100% { top:8%; } 50% { top:84%; } }`}</style>
                      <div style={{ animation: "scan-line 2s ease-in-out infinite", position: "absolute", left: "8px", right: "8px", height: "2px", background: "rgba(99,102,241,0.8)", boxShadow: "0 0 8px rgba(99,102,241,0.6)" }} />
                    </div>
                  </div>
                )}
                {cameraError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950/90 p-4">
                    <CameraOff className="w-10 h-10 text-red-400" />
                    <p className="text-xs text-center text-red-300">{cameraError}</p>
                    <button onClick={() => startCamera()} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors flex items-center gap-2"><Camera className="w-3.5 h-3.5" /> Coba Lagi Kamera</button>
                  </div>
                )}
                {!isCameraActive && !cameraError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                    <ScanLine className="w-10 h-10 text-slate-600 animate-pulse" />
                    <p className="text-xs text-slate-500">Membuka kamera...</p>
                  </div>
                )}
              </div>

              <p className="text-xs text-center text-slate-400">Arahkan kamera HP ke QR code yang ditampilkan pengawas</p>
            </>
          )}
        </div>
      </Modal>

      {/* Confirmation Modal */}
      <Modal isOpen={isConfirmModalOpen} onClose={() => setIsConfirmModalOpen(false)} title="Petunjuk &amp; Konfirmasi Ujian CBT" maxWidth="md">
        {selectedSchedule && (
          <div className="space-y-5">
            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 space-y-2">
              <Badge variant="indigo">{selectedSchedule.subject_name}</Badge>
              <h3 className="text-lg font-black text-slate-100">{selectedSchedule.title}</h3>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-1">
                <div><span>Durasi:</span><strong className="text-slate-200 block text-sm">{selectedSchedule.duration_minutes} Menit</strong></div>
                <div><span>Proteksi:</span><strong className="text-emerald-400 block text-sm">{selectedSchedule.lock_browser ? "Lockxam Active" : "Standar"}</strong></div>
              </div>
            </div>
            <div className="text-xs text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-850">
              <h4 className="font-bold text-slate-200 flex items-center gap-1.5 mb-2"><ShieldCheck className="w-4 h-4 text-indigo-400" /> Aturan Pengerjaan:</h4>
              <ul className="list-disc list-inside space-y-1.5 text-slate-400">
                <li>Waktu berjalan sejak tombol mulai ditekan.</li>
                <li>Jawaban tersimpan otomatis setiap kali dipilih/diisi.</li>
                <li>Gunakan tombol Ragu-Ragu untuk menandai soal yang belum yakin.</li>
                {selectedSchedule.lock_browser && <li className="text-amber-400 font-semibold">Dilarang berpindah tab / menutup jendela selama ujian.</li>}
              </ul>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setIsConfirmModalOpen(false)}>Batal</Button>
              <Button variant="primary" leftIcon={<Play className="w-4 h-4" />} onClick={() => { setIsConfirmModalOpen(false); setActiveExamSchedule(selectedSchedule); }}>Saya Siap, Mulai Ujian</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
