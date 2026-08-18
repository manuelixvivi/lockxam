import { useState, useEffect, useMemo } from "react";
import {
  RefreshCw,
  Clock,
  Lock,
  Unlock,
  AlertTriangle,
  FileSpreadsheet,
  CheckCircle,
  QrCode,
  Search,
  Volume2,
  Send,
  Zap,
  BatteryCharging,
  Wifi,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { teacherDashboardApi } from "../../api/teacherDashboard";
import type { TeacherProctorAssignment, StudentAttemptProctor } from "../../api/teacherDashboard";
import { apiClient } from "../../api/client";

export function TeacherProctorView() {
  const { showToast } = useToast();
  const [duties, setDuties] = useState<TeacherProctorAssignment[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Search Filter States
  const [dutySearchQuery, setDutySearchQuery] = useState("");
  const [monitorSearchQuery, setMonitorSearchQuery] = useState("");

  // Active Live Proctoring
  const [activeDuty, setActiveDuty] = useState<TeacherProctorAssignment | null>(null);
  const [attempts, setAttempts] = useState<StudentAttemptProctor[]>([]);

  // Live Commands
  const [selectedAttempt, setSelectedAttempt] = useState<StudentAttemptProctor | null>(null);
  const [commandReason, setCommandReason] = useState("");
  const [commandType, setCommandType] = useState<"lock" | "unlock" | "reset" | null>(null);
  const [isSendingCommand, setIsSendingCommand] = useState(false);

  // Broadcast & Extra Time State (Feature #3)
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [broadcastMsg, setBroadcastMsg] = useState("");
  const [extraMinutes, setExtraMinutes] = useState<number | null>(null);
  const [isSendingBroadcast, setIsSendingBroadcast] = useState(false);

  // BAP (Berita Acara / Attendance Log) State
  const [isBapOpen, setIsBapOpen] = useState(false);
  const [bapDuty, setBapDuty] = useState<TeacherProctorAssignment | null>(null);
  const [bauDoc, setBauDoc] = useState<any | null>(null);
  const [isLoadingBap, setIsLoadingBap] = useState(false);
  const [proctorNotes, setProctorNotes] = useState("");
  const [isSubmittingBap, setIsSubmittingBap] = useState(false);

  // QR Code Attendance State
  const [isQrOpen, setIsQrOpen] = useState(false);
  const [qrDuty, setQrDuty] = useState<TeacherProctorAssignment | null>(null);
  const [qrToken, setQrToken] = useState("");
  const [qrCountdown, setQrCountdown] = useState(30);

  const fetchDuties = async () => {
    setIsLoading(true);
    try {
      const data = await teacherDashboardApi.listProctorAssignments();
      setDuties(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Jadwal Pengawasan",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDuties();
  }, []);

  // Poll live attempts if in live proctoring view
  useEffect(() => {
    if (!activeDuty || !activeDuty.exam_session_id) return;

    const fetchAttempts = async () => {
      try {
        const list = await teacherDashboardApi.listSessionAttempts(activeDuty.exam_session_id!);
        setAttempts(list);
      } catch (err) {
        console.error("Poll error:", err);
      }
    };

    fetchAttempts();
    const interval = setInterval(fetchAttempts, 3000);
    return () => clearInterval(interval);
  }, [activeDuty]);

  // QR Code Auto Refresh
  useEffect(() => {
    if (!isQrOpen || !qrDuty) return;

    const fetchToken = async () => {
      try {
        const res = await apiClient.get<{ qr_token: string }>(
          `/api/v1/exam/schedules/${qrDuty.id}/qr-token`
        );
        setQrToken(res.qr_token);
        setQrCountdown(30);
      } catch (err) {
        console.error("QR token fetch error:", err);
      }
    };

    fetchToken();
    const timer = setInterval(() => {
      setQrCountdown((prev) => {
        if (prev <= 1) {
          fetchToken();
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isQrOpen, qrDuty]);

  const handleOpenQr = (duty: TeacherProctorAssignment) => {
    setQrDuty(duty);
    setIsQrOpen(true);
  };

  const handleOpenBap = async (duty: TeacherProctorAssignment) => {
    setBapDuty(duty);
    setIsBapOpen(true);
    setIsLoadingBap(true);
    try {
      const doc = await apiClient.get(`/api/v1/proctor/assignments/${duty.id}/bau`);
      setBauDoc(doc);
      setProctorNotes(doc.proctor_notes || "");
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat BAP",
        message: err?.message || "Gagal mengambil data Berita Acara.",
      });
    } finally {
      setIsLoadingBap(false);
    }
  };

  const handleSubmitBap = async () => {
    if (!bauDoc) return;
    setIsSubmittingBap(true);
    try {
      await apiClient.post(`/api/v1/proctor/bau/${bauDoc.id}/submit`, {
        proctor_notes: proctorNotes,
      });
      showToast({
        type: "success",
        title: "BAP Berhasil Dikirim",
        message: "Dokumen Berita Acara Pelaksanaan Ujian telah disubmit ke Admin.",
      });
      setIsBapOpen(false);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Submit BAP",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsSubmittingBap(false);
    }
  };

  const handleOpenCommandModal = (
    att: StudentAttemptProctor,
    type: "lock" | "unlock" | "reset"
  ) => {
    setSelectedAttempt(att);
    setCommandType(type);
    setCommandReason("");
  };

  const handleExecuteCommand = async () => {
    if (!selectedAttempt || !commandType || !activeDuty) return;

    setIsSendingCommand(true);
    try {
      const endpointMap = {
        lock: "/api/v1/proctor/commands/lock",
        unlock: "/api/v1/proctor/commands/unlock",
        reset: "/api/v1/proctor/commands/device-reset",
      };

      await apiClient.post(endpointMap[commandType], {
        attempt_id: selectedAttempt.attempt_id,
        proctor_assignment_id: activeDuty.id,
        exam_session_id: activeDuty.exam_session_id,
        reason: commandReason,
      });

      showToast({
        type: "success",
        title: "Perintah Terkirim",
        message: `Perintah ${commandType.toUpperCase()} berhasil dikirim untuk siswa ${selectedAttempt.student_name}.`,
      });
      setCommandType(null);
      setSelectedAttempt(null);

      if (activeDuty.exam_session_id) {
        const list = await teacherDashboardApi.listSessionAttempts(activeDuty.exam_session_id);
        setAttempts(list);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Perintah Gagal",
        message: err?.message || "Gagal mengeksekusi perintah pengawas.",
      });
    } finally {
      setIsSendingCommand(false);
    }
  };

  const handleSendBroadcast = async () => {
    if (!activeDuty?.exam_session_id) return;
    setIsSendingBroadcast(true);
    try {
      await apiClient.post("/api/v1/proctor/commands/broadcast", {
        exam_session_id: activeDuty.exam_session_id,
        message: broadcastMsg || undefined,
        extra_minutes: extraMinutes || undefined,
      });
      showToast({
        type: "success",
        title: "Broadcast Terkirim!",
        message: "Pengumuman dan perpanjangan waktu berhasil dikirim ke seluruh siswa.",
      });
      setIsBroadcastModalOpen(false);
      setBroadcastMsg("");
      setExtraMinutes(null);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Broadcast", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsSendingBroadcast(false);
    }
  };

  const filteredDuties = useMemo(() => {
    if (!dutySearchQuery.trim()) return duties;
    const q = dutySearchQuery.toLowerCase();
    return duties.filter(
      (d) =>
        d.title.toLowerCase().includes(q) ||
        (d.class_name && d.class_name.toLowerCase().includes(q)) ||
        (d.subject_name && d.subject_name.toLowerCase().includes(q))
    );
  }, [duties, dutySearchQuery]);

  const filteredAttempts = useMemo(() => {
    if (!monitorSearchQuery.trim()) return attempts;
    const q = monitorSearchQuery.toLowerCase();
    return attempts.filter(
      (a) =>
        a.student_name.toLowerCase().includes(q) ||
        a.student_username.toLowerCase().includes(q) ||
        (a.nisn && a.nisn.toLowerCase().includes(q))
    );
  }, [attempts, monitorSearchQuery]);

  // Analytics for Live Progress Gauge (Feature #2)
  const statsSubmitted = useMemo(() => attempts.filter((a) => ["SUBMITTED", "GRADED"].includes(a.status)).length, [attempts]);
  const statsInProgress = useMemo(() => attempts.filter((a) => a.status === "IN_PROGRESS").length, [attempts]);
  const statsPaused = useMemo(() => attempts.filter((a) => a.status === "PAUSED").length, [attempts]);
  const statsNotStarted = useMemo(() => attempts.filter((a) => a.status === "NOT_STARTED").length, [attempts]);
  const percentSubmitted = useMemo(() => (attempts.length > 0 ? Math.round((statsSubmitted / attempts.length) * 100) : 0), [statsSubmitted, attempts]);

  const yellowCount = useMemo(() => attempts.filter((a) => a.monitoring_card_state === "YELLOW").length, [attempts]);
  const redCount = useMemo(() => attempts.filter((a) => a.monitoring_card_state === "RED").length, [attempts]);

  const formatDateTime = (dtStr: string) => {
    if (!dtStr) return "-";
    try {
      const d = new Date(dtStr);
      return d.toLocaleString("id-ID", {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dtStr;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {activeDuty ? (
        // Live Proctoring Dashboard Panel
        <div className="space-y-6 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => setActiveDuty(null)}>
                  &larr; Kembali
                </Button>
                <Badge variant="indigo">Live Proctoring</Badge>
              </div>
              <h2 className="text-xl font-black text-slate-100 mt-2">
                Monitoring Live: {activeDuty.title}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Mengawasi kelas <strong>{activeDuty.class_name}</strong> | Pelajaran <strong>{activeDuty.subject_name}</strong>
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Volume2 className="w-4 h-4 text-amber-300" />}
                onClick={() => setIsBroadcastModalOpen(true)}
              >
                📢 Broadcast & Perpanjang Waktu
              </Button>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<QrCode className="w-4 h-4 text-indigo-400" />}
                onClick={() => handleOpenQr(activeDuty)}
              >
                QR Code Absen
              </Button>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<FileSpreadsheet className="w-4 h-4" />}
                onClick={() => handleOpenBap(activeDuty)}
              >
                Isi Berita Acara (BAP)
              </Button>
            </div>
          </div>

          {/* Alert Banners (Red & Yellow Warnings) */}
          {redCount > 0 && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-2xl flex items-center gap-3 text-rose-300 text-xs animate-pulse">
              <AlertTriangle className="w-5 h-5 shrink-0 text-rose-400" />
              <div>
                <strong className="block font-bold text-sm">🚨 PELANGGARAN TERDETEKSI ({redCount} Siswa)</strong>
                <p>Siswa terdeteksi berpindah aplikasi, split screen, atau terkunci oleh sistem. Periksa baris siswa berwarna merah.</p>
              </div>
            </div>
          )}

          {yellowCount > 0 && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-center gap-3 text-amber-300 text-xs">
              <Zap className="w-5 h-5 shrink-0 text-amber-400" />
              <div>
                <strong className="block font-bold text-sm">⚠️ KENDALA TEKNIS / BATERAI KRITIS ({yellowCount} Siswa)</strong>
                <p>Siswa mengalami baterai low (&lt;20%) atau gangguan jaringan offline. Peringatkan siswa untuk mengisi daya HP.</p>
              </div>
            </div>
          )}

          {/* 📊 FEATURE #2: Live Class Progress & Completion Gauge Bar */}
          <div className="glass-panel p-5 border border-slate-800 space-y-3 bg-gradient-to-br from-indigo-950/20 to-slate-900/60">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold text-slate-200">Progress Pengerjaan Ujian Kelas:</span>
              </div>
              <span className="text-xs font-black text-emerald-400">{percentSubmitted}% Selesai ({statsSubmitted}/{attempts.length} Siswa)</span>
            </div>

            {/* Multi-segment Progress Bar */}
            <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden flex border border-slate-800 p-0.5">
              <div className="h-full bg-emerald-500 rounded-l-full transition-all duration-500" style={{ width: `${percentSubmitted}%` }} title="Dikumpulkan" />
              <div className="h-full bg-indigo-500 transition-all duration-500" style={{ width: `${attempts.length > 0 ? (statsInProgress / attempts.length) * 100 : 0}%` }} title="Sedang Mengerjakan" />
              <div className="h-full bg-amber-500 transition-all duration-500" style={{ width: `${attempts.length > 0 ? (statsPaused / attempts.length) * 100 : 0}%` }} title="Terkunci / Paused" />
              <div className="h-full bg-slate-800 rounded-r-full transition-all duration-500" style={{ width: `${attempts.length > 0 ? (statsNotStarted / attempts.length) * 100 : 0}%` }} title="Belum Mulai" />
            </div>

            <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-400 pt-1">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" /> Selesai: <strong>{statsSubmitted}</strong></span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-indigo-500 inline-block" /> Mengerjakan: <strong>{statsInProgress}</strong></span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" /> Terkunci/Paused: <strong>{statsPaused}</strong></span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-slate-700 inline-block" /> Belum Absen: <strong>{statsNotStarted}</strong></span>
            </div>
          </div>

          {/* Student Live Table */}
          <div className="glass-panel p-6 space-y-4 border border-slate-800">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>Daftar Siswa & Status Perangkat Live ({attempts.length} Siswa)</span>
              </h3>
              <div className="w-full sm:w-64">
                <Input
                  placeholder="Cari siswa di live monitoring..."
                  leftIcon={<Search className="w-4 h-4 text-slate-400" />}
                  value={monitorSearchQuery}
                  onChange={(e) => setMonitorSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {/* Desktop Table View */}
            <div className="overflow-x-auto hidden md:block">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-3 px-4 font-bold">Nama Siswa</th>
                    <th className="py-3 px-4 font-bold text-center">Status Sesi</th>
                    <th className="py-3 px-4 font-bold text-center">Status Perangkat</th>
                    <th className="py-3 px-4 font-bold text-center">Telemetry (Baterai & Ping)</th>
                    <th className="py-3 px-4 font-bold text-right">Aksi Live Control</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {filteredAttempts.map((att) => {
                    const isRed = att.monitoring_card_state === "RED";
                    const isYellow = att.monitoring_card_state === "YELLOW";
                    return (
                      <tr
                        key={att.student_id}
                        className={`transition-colors ${
                          isRed
                            ? "bg-rose-950/40 hover:bg-rose-950/60 text-rose-200 border-l-4 border-l-rose-500"
                            : isYellow
                            ? "bg-amber-950/30 hover:bg-amber-950/50 text-amber-200 border-l-4 border-l-amber-500"
                            : "hover:bg-slate-900/40"
                        }`}
                      >
                        <td className="py-3 px-4">
                          <div className="font-bold text-slate-200">{att.student_name}</div>
                          <div className="text-[10px] text-slate-500">
                            {att.student_username} {att.nisn ? `| NISN: ${att.nisn}` : ""}
                          </div>
                          {att.violation_reason && (
                            <span className="text-[10px] font-bold text-rose-400 block mt-0.5">
                              🚨 {att.violation_reason}
                            </span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-center">
                          <Badge
                            variant={
                              att.status === "SUBMITTED" || att.status === "GRADED"
                                ? "emerald"
                                : att.status === "IN_PROGRESS"
                                ? "indigo"
                                : att.status === "PAUSED"
                                ? "amber"
                                : "slate"
                            }
                          >
                            {att.status === "NOT_STARTED" ? "Belum Ujian" : att.status}
                          </Badge>
                        </td>

                        <td className="py-3 px-4 text-center">
                          {att.device_status === "ACTIVE" && (
                            <Badge variant="emerald">
                              <span className="flex items-center gap-1">
                                <CheckCircle className="w-3.5 h-3.5" />
                                Aktif & Terkunci
                              </span>
                            </Badge>
                          )}
                          {att.device_status === "BLOCKED" && (
                            <Badge variant="amber">
                              <span className="flex items-center gap-1">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                Terdeteksi Keluar
                              </span>
                            </Badge>
                          )}
                          {!att.device_status && <span className="text-slate-500">Belum Login</span>}
                        </td>

                        {/* Telemetry Column */}
                        <td className="py-3 px-4 text-center">
                          <div className="flex items-center justify-center gap-3 text-xs">
                            <span
                              className={`flex items-center gap-1 font-mono font-bold ${
                                att.battery_level !== undefined && att.battery_level !== null && att.battery_level <= 20
                                  ? "text-rose-400 animate-pulse"
                                  : "text-slate-300"
                              }`}
                            >
                              <BatteryCharging className="w-3.5 h-3.5" />
                              {att.battery_level !== undefined && att.battery_level !== null
                                ? `${att.battery_level}%`
                                : "-"}
                            </span>

                            <span className="flex items-center gap-1 font-mono text-[11px] text-slate-400">
                              <Wifi className="w-3.5 h-3.5 text-indigo-400" />
                              {att.ping_ms !== undefined && att.ping_ms !== null
                                ? att.ping_ms > 1000
                                  ? "Offline"
                                  : `${att.ping_ms}ms`
                                : "-"}
                            </span>
                          </div>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {att.status === "IN_PROGRESS" && (
                              <Button
                                variant="danger"
                                size="sm"
                                leftIcon={<Lock className="w-3 h-3" />}
                                onClick={() => handleOpenCommandModal(att, "lock")}
                              >
                                Kunci
                              </Button>
                            )}
                            {att.status === "PAUSED" && (
                              <Button
                                variant="primary"
                                size="sm"
                                leftIcon={<Unlock className="w-3 h-3" />}
                                onClick={() => handleOpenCommandModal(att, "unlock")}
                              >
                                Buka Kunci
                              </Button>
                            )}
                            {att.status !== "SUBMITTED" && att.status !== "GRADED" && (
                              <Button
                                variant="outline"
                                size="sm"
                                leftIcon={<RefreshCw className="w-3 h-3 text-amber-400" />}
                                onClick={() => handleOpenCommandModal(att, "reset")}
                              >
                                Rebind Perangkat
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Card List View (< md) */}
            <div className="space-y-3 block md:hidden">
              {filteredAttempts.map((att) => {
                const isRed = att.monitoring_card_state === "RED";
                const isYellow = att.monitoring_card_state === "YELLOW";
                return (
                  <div
                    key={att.student_id}
                    className={`p-4 rounded-2xl border flex flex-col gap-3 transition-colors ${
                      isRed
                        ? "bg-rose-950/40 border-rose-500/50 text-rose-200"
                        : isYellow
                        ? "bg-amber-950/30 border-amber-500/50 text-amber-200"
                        : "bg-slate-900/60 border-slate-800 text-slate-200"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="font-black text-sm text-slate-100">{att.student_name}</div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {att.student_username} {att.nisn ? `| NISN: ${att.nisn}` : ""}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <Badge
                          variant={
                            att.status === "SUBMITTED" || att.status === "GRADED"
                              ? "emerald"
                              : att.status === "IN_PROGRESS"
                              ? "indigo"
                              : att.status === "PAUSED"
                              ? "amber"
                              : "slate"
                          }
                        >
                          {att.status === "NOT_STARTED" ? "Belum Ujian" : att.status}
                        </Badge>

                        {/* Status Perangkat Badge on Mobile */}
                        {att.device_status === "ACTIVE" && (
                          <span className="text-[10px] text-emerald-400 font-semibold flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> HP Terkunci
                          </span>
                        )}
                        {att.device_status === "BLOCKED" && (
                          <span className="text-[10px] text-amber-400 font-semibold flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Terdeteksi Keluar
                          </span>
                        )}
                      </div>
                    </div>

                    {att.violation_reason && (
                      <div className="p-2 bg-rose-500/20 rounded-xl border border-rose-500/30 text-[11px] font-bold text-rose-300">
                        🚨 Pelanggaran: {att.violation_reason}
                      </div>
                    )}

                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 text-xs pt-2 border-t border-slate-800/80">
                      <div className="flex items-center justify-between sm:justify-start gap-3 bg-slate-950/60 p-2 rounded-xl border border-slate-850">
                        <span
                          className={`flex items-center gap-1 font-mono font-bold ${
                            att.battery_level !== undefined && att.battery_level !== null && att.battery_level <= 20
                              ? "text-rose-400 animate-pulse"
                              : "text-slate-300"
                          }`}
                        >
                          <BatteryCharging className="w-3.5 h-3.5" />
                          {att.battery_level !== undefined && att.battery_level !== null ? `${att.battery_level}%` : "-"}
                        </span>
                        <span className="flex items-center gap-1 font-mono text-[11px] text-slate-400">
                          <Wifi className="w-3.5 h-3.5 text-indigo-400" />
                          {att.ping_ms !== undefined && att.ping_ms !== null ? (att.ping_ms > 1000 ? "Offline" : `${att.ping_ms}ms`) : "-"}
                        </span>
                      </div>

                      {/* Live Control Action Buttons on Mobile */}
                      <div className="flex items-center justify-end gap-2 pt-1 sm:pt-0">
                        {att.status === "IN_PROGRESS" && (
                          <Button
                            variant="danger"
                            size="sm"
                            leftIcon={<Lock className="w-3.5 h-3.5" />}
                            onClick={() => handleOpenCommandModal(att, "lock")}
                          >
                            Kunci
                          </Button>
                        )}
                        {att.status === "PAUSED" && (
                          <Button
                            variant="primary"
                            size="sm"
                            leftIcon={<Unlock className="w-3.5 h-3.5" />}
                            onClick={() => handleOpenCommandModal(att, "unlock")}
                          >
                            Buka Kunci
                          </Button>
                        )}
                        {att.status !== "SUBMITTED" && att.status !== "GRADED" && (
                          <Button
                            variant="outline"
                            size="sm"
                            leftIcon={<RefreshCw className="w-3.5 h-3.5 text-amber-400" />}
                            onClick={() => handleOpenCommandModal(att, "reset")}
                          >
                            Rebind HP
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        // Duties List View
        <div className="space-y-6">
          <div className="glass-panel p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="indigo">TEACHER PORTAL</Badge>
                <Badge variant="emerald">PENGAWAS UJIAN</Badge>
              </div>
              <h1 className="text-xl font-bold text-slate-100">Daftar Jadwal Pengawasan CBT</h1>
              <p className="text-xs text-slate-400 mt-1">Pilih jadwal pengawasan untuk membuka Live Control, Absen QR, dan Berita Acara (BAP).</p>
            </div>
            <Button variant="outline" size="sm" leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />} onClick={fetchDuties}>Refresh</Button>
          </div>

          <div className="flex justify-between items-center">
            <h3 className="font-bold text-slate-100 text-sm">Jadwal Tugas Pengawas ({filteredDuties.length})</h3>
            <div className="w-full sm:w-64">
              <Input placeholder="Cari jadwal pengawas..." leftIcon={<Search className="w-4 h-4 text-slate-400" />} value={dutySearchQuery} onChange={(e) => setDutySearchQuery(e.target.value)} />
            </div>
          </div>

          {isLoading ? (
            <div className="glass-panel p-12 text-center flex flex-col items-center gap-3"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" /><p className="text-xs text-slate-400">Memuat pengawasan...</p></div>
          ) : filteredDuties.length === 0 ? (
            <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
              <Clock className="w-12 h-12 text-slate-600" />
              <h3 className="text-sm font-bold text-slate-300">Belum Ada Tugas Pengawasan</h3>
              <p className="text-xs text-slate-500 max-w-sm">Jadwal pengawasan ujian akan muncul di sini jika diset oleh Administrator.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredDuties.map((duty) => {
                const isCancelled = duty.status === "CANCELLED";
                return (
                  <div key={duty.id} className={`glass-panel p-6 flex flex-col justify-between gap-5 border transition-all ${isCancelled ? "opacity-60 grayscale bg-slate-950/60 border-slate-800/60" : "border-slate-800 hover:border-slate-700"}`}>
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-bold text-slate-100 text-base">{duty.title}</h3>
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <Badge variant="indigo">{duty.class_name || "Kelas"}</Badge>
                            <Badge variant="slate">{duty.subject_name || "Mapel"}</Badge>
                          </div>
                        </div>
                        {isCancelled ? <Badge variant="slate">DIBATALKAN</Badge> : <Badge variant="emerald">AKTIF</Badge>}
                      </div>

                      <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1 text-slate-400">
                        <div className="flex justify-between"><span>Waktu Mulai:</span><span className="font-semibold text-slate-200">{formatDateTime(duty.start_time)}</span></div>
                        <div className="flex justify-between"><span>Waktu Selesai:</span><span className="font-semibold text-slate-200">{formatDateTime(duty.end_time)}</span></div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <Button variant="primary" className="w-full" disabled={isCancelled} onClick={() => setActiveDuty(duty)}>Masuk Live Monitoring</Button>
                      <div className="grid grid-cols-2 gap-2">
                        <Button variant="outline" size="sm" disabled={isCancelled} onClick={() => handleOpenQr(duty)}>QR Absen</Button>
                        <Button variant="outline" size="sm" disabled={isCancelled} onClick={() => handleOpenBap(duty)}>BAP</Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 📢 FEATURE #3: Modal Broadcast Pengumuman & Perpanjangan Waktu */}
      <Modal isOpen={isBroadcastModalOpen} onClose={() => setIsBroadcastModalOpen(false)} title="📢 Broadcast & Perpanjang Waktu Ujian" maxWidth="md">
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">Pesan broadcast akan muncul melayang di layar lembar ujian seluruh siswa kelas <strong>{activeDuty?.class_name}</strong>.</p>
          <div>
            <label className="block text-slate-400 mb-1 font-semibold">Isi Pesan Broadcast Pengumuman:</label>
            <textarea
              className="w-full p-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              rows={3}
              placeholder="Contoh: Perhatikan instruksi soal nomor 15. Dilarang membuka kalkulator!"
              value={broadcastMsg}
              onChange={(e) => setBroadcastMsg(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1 font-semibold">Tambah Durasi Waktu Ujian (Opsional):</label>
            <div className="flex items-center gap-2">
              {[5, 10, 15, 30].map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setExtraMinutes(extraMinutes === m ? null : m)}
                  className={`px-3 py-1.5 rounded-xl border text-xs font-bold transition-all ${
                    extraMinutes === m
                      ? "bg-amber-500 text-slate-950 border-amber-400"
                      : "bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  +{m} Menit
                </button>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setIsBroadcastModalOpen(false)}>Batal</Button>
            <Button variant="primary" leftIcon={<Send className="w-4 h-4" />} isLoading={isSendingBroadcast} onClick={handleSendBroadcast}>
              Kirim Broadcast Sekarang
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal QR Code */}
      <Modal isOpen={isQrOpen} onClose={() => setIsQrOpen(false)} title={`QR Absenssi: ${qrDuty?.title || ""}`} maxWidth="sm">
        <div className="space-y-4 text-center text-xs">
          <p className="text-slate-300">Tampilkan QR Code ini di laptop pengawas agar discan oleh HP siswa.</p>
          {qrToken ? (
            <div className="p-4 bg-white rounded-2xl inline-block border-4 border-indigo-500/40">
              <img src={`https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(qrToken)}`} alt="QR Token Absen" className="w-56 h-56 mx-auto" />
            </div>
          ) : (
            <div className="w-56 h-56 mx-auto bg-slate-900 rounded-2xl flex items-center justify-center"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" /></div>
          )}
          <div className="flex items-center justify-center gap-2 text-slate-400 font-mono text-[11px]"><RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" /> Auto refresh dalam <strong>{qrCountdown} detik</strong></div>
        </div>
      </Modal>

      {/* Modal BAP */}
      <Modal isOpen={isBapOpen} onClose={() => setIsBapOpen(false)} title={`Berita Acara (BAP): ${bapDuty?.title || ""}`} maxWidth="lg">
        <div className="space-y-4 text-xs">
          {isLoadingBap ? (
            <div className="p-8 text-center"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto" /><p className="text-slate-400 mt-2">Memuat Berita Acara...</p></div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-850">
                <div><span className="text-slate-500 block">Mata Pelajaran:</span><strong className="text-slate-200">{bapDuty?.subject_name}</strong></div>
                <div><span className="text-slate-500 block">Kelas:</span><strong className="text-slate-200">{bapDuty?.class_name}</strong></div>
                <div><span className="text-slate-500 block">Total Peserta:</span><strong className="text-indigo-400">{attempts.length} Siswa</strong></div>
                <div><span className="text-slate-500 block">Status BAP:</span><strong className="text-emerald-400">SIAP DITERBITKAN</strong></div>
              </div>

              {/* Student Attendance List Breakdown in BAP */}
              <div className="space-y-2">
                <label className="block text-slate-400 font-semibold">Daftar Kehadiran & Status Siswa Dalam BAP ({attempts.length} Siswa):</label>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 border border-slate-800 rounded-xl p-2.5 bg-slate-950/60">
                  {attempts.length === 0 ? (
                    <p className="text-slate-500 text-center py-3 italic">Buka "Live Monitoring" terlebih dahulu untuk sinkronisasi daftar siswa kelas.</p>
                  ) : (
                    attempts.map((att) => (
                      <div key={att.student_id} className="p-2 bg-slate-900/80 rounded-xl border border-slate-850 flex items-center justify-between gap-2">
                        <div>
                          <span className="font-bold text-slate-200 block text-[11px]">{att.student_name}</span>
                          <span className="text-[10px] text-slate-400 font-mono">{att.student_username} {att.nisn ? `| NISN: ${att.nisn}` : ""}</span>
                        </div>
                        <Badge
                          variant={
                            att.status === "SUBMITTED" || att.status === "GRADED"
                              ? "emerald"
                              : att.status === "IN_PROGRESS"
                              ? "indigo"
                              : att.status === "PAUSED"
                              ? "amber"
                              : "slate"
                          }
                        >
                          {att.status === "NOT_STARTED" ? "Belum Ujian" : att.status}
                        </Badge>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-semibold">Catatan Kejadian & Incident Log (Auto BAP):</label>
                <textarea className="w-full p-3 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 text-xs focus:border-indigo-500 focus:outline-none" rows={3} value={proctorNotes} onChange={(e) => setProctorNotes(e.target.value)} placeholder="Catatan insiden ujian atau siswa berhalangan..." />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button variant="outline" onClick={() => setIsBapOpen(false)}>Batal</Button>
                <Button variant="primary" isLoading={isSubmittingBap} onClick={handleSubmitBap}>Simpan & Submit BAP</Button>
              </div>
            </>
          )}
        </div>
      </Modal>

      {/* Modal Command Confirm */}
      <Modal isOpen={!!commandType} onClose={() => setCommandType(null)} title={`Konfirmasi Perintah ${commandType?.toUpperCase()}`}>
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">Eksekusi perintah <strong>{commandType}</strong> untuk siswa <strong>{selectedAttempt?.student_name}</strong>?</p>
          <Input label="Alasan Pengawas (Opsional)" placeholder="Contoh: Siswa terindikasi menengok HP" value={commandReason} onChange={(e) => setCommandReason(e.target.value)} />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setCommandType(null)}>Batal</Button>
            <Button variant="primary" isLoading={isSendingCommand} onClick={handleExecuteCommand}>Jalankan Perintah</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
