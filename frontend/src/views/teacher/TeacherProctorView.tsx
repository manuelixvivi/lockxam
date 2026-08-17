import React, { useState, useEffect, useMemo } from "react";
import {
  ShieldCheck,
  RefreshCw,
  Clock,
  Play,
  Lock,
  Unlock,
  AlertTriangle,
  FileSpreadsheet,
  CheckCircle,
  XCircle,
  UserCheck,
  QrCode,
  Search,
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
  const [bapSearchQuery, setBapSearchQuery] = useState("");

  // Active Live Proctoring
  const [activeDuty, setActiveDuty] = useState<TeacherProctorAssignment | null>(null);
  const [attempts, setAttempts] = useState<StudentAttemptProctor[]>([]);

  // Live Commands
  const [selectedAttempt, setSelectedAttempt] = useState<StudentAttemptProctor | null>(null);
  const [commandReason, setCommandReason] = useState("");
  const [commandType, setCommandType] = useState<"lock" | "unlock" | "reset" | null>(null);
  const [isSendingCommand, setIsSendingCommand] = useState(false);

  // BAP (Berita Acara / Attendance Log) State
  const [isBapOpen, setIsBapOpen] = useState(false);
  const [bapDuty, setBapDuty] = useState<TeacherProctorAssignment | null>(null);
  const [bauDoc, setBauDoc] = useState<any | null>(null);
  const [students, setStudents] = useState<any[]>([]);
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
    const interval = setInterval(fetchAttempts, 3000); // poll every 3 sec
    return () => clearInterval(interval);
  }, [activeDuty]);

  // QR Code Auto Refresh — fetches signed token from backend and rotates every 30 seconds
  const generateNewQrToken = async (duty: TeacherProctorAssignment) => {
    try {
      const res = await apiClient.get<{ token: string; expires_in_seconds: number }>(
        `/api/v1/exam/schedules/${duty.id}/qr-token`
      );
      setQrToken(res.token);
      setQrCountdown(30);
    } catch {
      // Fallback: generate unsigned placeholder so UI still renders
      setQrToken(`LOCKXAM_ABSEN_${duty.id}_${Date.now()}`);
      setQrCountdown(30);
    }
  };

  const handleOpenQr = (duty: TeacherProctorAssignment) => {
    setQrDuty(duty);
    generateNewQrToken(duty);
    setIsQrOpen(true);
  };

  const handleCloseQr = () => {
    setIsQrOpen(false);
    setQrDuty(null);
    setQrToken("");
    setQrCountdown(30);
  };

  useEffect(() => {
    if (!isQrOpen || !qrDuty) return;

    const timer = setInterval(() => {
      setQrCountdown((prev) => {
        if (prev <= 1) {
          generateNewQrToken(qrDuty);
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isQrOpen, qrDuty]);

  // Live Proctor Actions
  const handleOpenCommandModal = (attempt: StudentAttemptProctor, type: "lock" | "unlock" | "reset") => {
    setSelectedAttempt(attempt);
    setCommandType(type);
    setCommandReason("");
  };

  const handleSendCommand = async () => {
    if (!selectedAttempt || !commandType || !activeDuty || !activeDuty.exam_session_id) return;
    setIsSendingCommand(true);
    try {
      let endpoint = "lock";
      if (commandType === "unlock") endpoint = "unlock";
      if (commandType === "reset") endpoint = "device-reset";

      await apiClient.post(`/api/v1/proctor/commands/${endpoint}`, {
        exam_session_id: activeDuty.exam_session_id,
        proctor_assignment_id: activeDuty.id,
        attempt_id: selectedAttempt.attempt_id,
        reason: commandReason || `${commandType} command issued by proctor`,
      });

      showToast({
        type: "success",
        title: "Perintah Terkirim",
        message: `Perintah ${commandType.toUpperCase()} berhasil dikirim ke perangkat ${selectedAttempt.student_name}.`,
      });
      setSelectedAttempt(null);
      setCommandType(null);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Mengirim Perintah", message: err?.message || "Gagal memproses aksi proctor." });
    } finally {
      setIsSendingCommand(false);
    }
  };

  // BAP Actions
  const handleOpenBap = async (duty: TeacherProctorAssignment) => {
    setBapDuty(duty);
    setIsLoadingBap(true);
    setIsBapOpen(true);
    setBapSearchQuery("");
    try {
      const resBau = await apiClient.post(`/api/v1/proctor/assignments/${duty.id}/bau`, {});
      setBauDoc(resBau);
      setProctorNotes(resBau.proctor_notes || "");

      const listStuds = await teacherDashboardApi.listClassStudents(duty.class_id);
      setStudents(listStuds);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat BAP", message: err?.message || "Gagal mengambil Berita Acara." });
      setIsBapOpen(false);
    } finally {
      setIsLoadingBap(false);
    }
  };

  const handleUpdateStudentAttendance = async (studentId: number, status: string) => {
    if (!bauDoc || !bapDuty) return;
    try {
      const res = await apiClient.put(`/api/v1/proctor/bau/${bauDoc.id}/attendance`, {
        student_id: studentId,
        attendance_status: status,
        reason: "",
      });

      const updatedAtts = [...(bauDoc.attendances || [])];
      const existIdx = updatedAtts.findIndex((a: any) => a.student_id === studentId);
      if (existIdx >= 0) {
        updatedAtts[existIdx] = res;
      } else {
        updatedAtts.push(res);
      }
      setBauDoc({ ...bauDoc, attendances: updatedAtts });
      showToast({ type: "success", title: "Kehadiran Diupdate" });
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Mengubah Kehadiran", message: err?.message || "Gagal." });
    }
  };

  const handleSubmitBap = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bauDoc) return;
    setIsSubmittingBap(true);
    try {
      const res = await apiClient.post(`/api/v1/proctor/bau/${bauDoc.id}/submit`, {
        proctor_notes: proctorNotes.trim(),
      });
      setBauDoc(res);
      showToast({ type: "success", title: "BAP Berhasil Disubmit", message: "Berita Acara Ujian telah dikunci." });
      setIsBapOpen(false);
      fetchDuties();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Submit BAP", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsSubmittingBap(false);
    }
  };

  const getAttendanceStatusForStudent = (studentId: number) => {
    if (!bauDoc || !bauDoc.attendances) return "ALPA";
    const att = bauDoc.attendances.find((a: any) => a.student_id === studentId);
    return att ? att.attendance_status : "ALPA";
  };

  // Search Filtered Memo Collections
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

  const filteredBapStudents = useMemo(() => {
    if (!bapSearchQuery.trim()) return students;
    const q = bapSearchQuery.toLowerCase();
    return students.filter(
      (s) =>
        s.student_name.toLowerCase().includes(q) ||
        (s.nisn && s.nisn.toLowerCase().includes(q)) ||
        (s.student_username && s.student_username.toLowerCase().includes(q))
    );
  }, [students, bapSearchQuery]);

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

          <div className="glass-panel p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>Daftar Seluruh Siswa & Status Perangkat ({attempts.length} Siswa)</span>
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
                    <th className="py-3 px-4 font-bold text-center">Status Attempt</th>
                    <th className="py-3 px-4 font-bold text-center">Status Perangkat</th>
                    <th className="py-3 px-4 font-bold">IP & Device ID</th>
                    <th className="py-3 px-4 font-bold text-right">Aksi Live Control</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {filteredAttempts.map((att) => (
                    <tr key={att.student_id} className="hover:bg-slate-900/40">
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-200">{att.student_name}</div>
                        <div className="text-[10px] text-slate-500">{att.student_username} {att.nisn ? `| NISN: ${att.nisn}` : ""}</div>
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
                        {att.device_status === "INVALIDATED" && (
                          <Badge variant="crimson">
                            <span className="flex items-center gap-1">
                              <XCircle className="w-3.5 h-3.5" />
                              Invalidated
                            </span>
                          </Badge>
                        )}
                        {!att.device_status && <span className="text-slate-500">Belum Login</span>}
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-[10px]">
                        <div>IP: {att.ip_address || "-"}</div>
                        <div className="text-[9px] text-slate-500 truncate max-w-[120px]">{att.device_id || "-"}</div>
                      </td>
                      <td className="py-3 px-4 text-right space-x-1.5">
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
                        {att.attempt_id ? (
                          <Button
                            variant="outline"
                            size="sm"
                            leftIcon={<RefreshCw className="w-3 h-3" />}
                            onClick={() => handleOpenCommandModal(att, "reset")}
                          >
                            Rebind HP
                          </Button>
                        ) : (
                          <span className="text-[11px] text-slate-500 italic">Belum Ujian</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredAttempts.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500">
                        {monitorSearchQuery ? "Siswa tidak ditemukan." : "Belum ada data siswa."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Mobile Card View */}
            <div className="space-y-3 block md:hidden">
              {filteredAttempts.map((att) => (
                <div key={att.student_id} className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-bold text-slate-100 text-sm">{att.student_name}</h4>
                      <p className="text-[11px] text-slate-400 font-mono">
                        {att.student_username} {att.nisn ? `• NISN: ${att.nisn}` : ""}
                      </p>
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

                  <div className="flex items-center justify-between gap-2 p-2.5 bg-slate-950/70 rounded-lg border border-slate-850 text-xs">
                    <span className="text-slate-400">Status Perangkat:</span>
                    <div>
                      {att.device_status === "ACTIVE" && (
                        <Badge variant="emerald">
                          <span className="flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" />
                            Aktif & Terkunci
                          </span>
                        </Badge>
                      )}
                      {att.device_status === "BLOCKED" && (
                        <Badge variant="amber">
                          <span className="flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            Terdeteksi Keluar
                          </span>
                        </Badge>
                      )}
                      {att.device_status === "INVALIDATED" && (
                        <Badge variant="crimson">
                          <span className="flex items-center gap-1">
                            <XCircle className="w-3 h-3" />
                            Invalidated
                          </span>
                        </Badge>
                      )}
                      {!att.device_status && <span className="text-slate-500 font-medium">Belum Login</span>}
                    </div>
                  </div>

                  <div className="text-[10px] text-slate-400 font-mono flex items-center justify-between px-1">
                    <span>IP: {att.ip_address || "-"}</span>
                    <span className="truncate max-w-[150px]">ID: {att.device_id || "-"}</span>
                  </div>

                  <div className="pt-2 flex flex-wrap gap-2 border-t border-slate-850">
                    {att.status === "IN_PROGRESS" && (
                      <Button
                        variant="danger"
                        size="sm"
                        className="flex-1"
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
                        className="flex-1"
                        leftIcon={<Unlock className="w-3.5 h-3.5" />}
                        onClick={() => handleOpenCommandModal(att, "unlock")}
                      >
                        Buka Kunci
                      </Button>
                    )}
                    {att.attempt_id ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                        onClick={() => handleOpenCommandModal(att, "reset")}
                      >
                        Rebind HP
                      </Button>
                    ) : (
                      <div className="w-full text-center text-[11px] text-slate-500 italic">
                        Belum Ujian
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {filteredAttempts.length === 0 && (
                <div className="p-8 text-center text-slate-500 text-xs">
                  {monitorSearchQuery ? "Siswa tidak ditemukan." : "Belum ada data siswa."}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        // Duties List View
        <div className="space-y-6 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-400" />
                <span>Jadwal Pengawasan & Berita Acara (BAP)</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Daftar sesi ujian sekolah di mana Anda ditugaskan sebagai Pengawas. Aktifkan Live Dashboard monitoring, QR Code Absen, atau isi Berita Acara Ujian (BAP).
              </p>
            </div>
            <div className="w-full sm:w-72">
              <Input
                placeholder="Cari jadwal, kelas, atau mapel..."
                leftIcon={<Search className="w-4 h-4 text-slate-400" />}
                value={dutySearchQuery}
                onChange={(e) => setDutySearchQuery(e.target.value)}
              />
            </div>
          </div>

          {isLoading ? (
            <div className="glass-panel p-12 flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
              <p className="text-xs text-slate-400">Memuat penugasan pengawas...</p>
            </div>
          ) : filteredDuties.length === 0 ? (
            <div className="glass-panel p-12 text-center flex flex-col items-center justify-center gap-3 border-dashed">
              <ShieldCheck className="w-12 h-12 text-slate-600" />
              <h3 className="text-sm font-bold text-slate-300">
                {dutySearchQuery ? "Tidak Ada Hasil Pencarian" : "Tidak Ada Tugas Mengawas"}
              </h3>
              <p className="text-xs text-slate-500 max-w-sm">
                {dutySearchQuery
                  ? `Tidak ada jadwal yang sesuai dengan kata kunci "${dutySearchQuery}".`
                  : "Anda tidak terdaftar sebagai pengawas untuk jadwal ujian saat ini."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredDuties.map((item) => (
                <div key={item.id} className="glass-panel p-5 space-y-4 border border-slate-800 hover:border-slate-700">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-bold text-slate-200">{item.title}</h3>
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <Badge variant="indigo">{item.class_name}</Badge>
                        <Badge variant="slate">{item.subject_name}</Badge>
                      </div>
                    </div>
                    {item.exam_session_status === "ACTIVE" ? (
                      <Badge variant="emerald">Live / Ujian Jalan</Badge>
                    ) : item.status === "READY" ? (
                      <Badge variant="emerald">READY (SIAP UJIAN)</Badge>
                    ) : (
                      <Badge variant="slate">{item.status}</Badge>
                    )}
                  </div>

                  <div className="text-[11px] text-slate-400 space-y-1 bg-slate-900/60 p-3 rounded-lg border border-slate-800">
                    <div className="flex justify-between">
                      <span>Waktu Mulai:</span>
                      <span className="font-semibold text-slate-300">{formatDateTime(item.start_time)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Waktu Selesai:</span>
                      <span className="font-semibold text-slate-300">{formatDateTime(item.end_time)}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 pt-1.5">
                    {item.exam_session_id || item.status === "READY" || item.status === "ACTIVE" ? (
                      <Button
                        variant="primary"
                        size="sm"
                        className="flex-1"
                        leftIcon={<Play className="w-4 h-4" />}
                        onClick={() => setActiveDuty(item)}
                      >
                        Monitor Live
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                        disabled
                      >
                        Ujian Belum Dimulai
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={<QrCode className="w-4 h-4 text-indigo-400" />}
                      onClick={() => handleOpenQr(item)}
                    >
                      QR Absen
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={<FileSpreadsheet className="w-4 h-4" />}
                      onClick={() => handleOpenBap(item)}
                    >
                      BAP
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Modal: Live Command Proctor ── */}
      <Modal
        isOpen={selectedAttempt !== null}
        onClose={() => {
          setSelectedAttempt(null);
          setCommandType(null);
        }}
        title={`Live Control: ${commandType?.toUpperCase()} Siswa`}
        maxWidth="sm"
      >
        {selectedAttempt && (
          <div className="space-y-4">
            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 space-y-1">
              <p className="text-xs text-slate-400">Siswa Terpilih</p>
              <p className="text-sm font-bold text-slate-200">{selectedAttempt.student_name}</p>
              <p className="text-[10px] text-slate-500 font-mono">Username: {selectedAttempt.student_username}</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Alasan/Catatan Tindakan</label>
              <Input
                placeholder="Misal: Mencurigakan melirik keluar, restart perangkat, dll."
                value={commandReason}
                onChange={(e) => setCommandReason(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                type="button"
                onClick={() => {
                  setSelectedAttempt(null);
                  setCommandType(null);
                }}
              >
                Batal
              </Button>
              <Button
                variant="danger"
                onClick={handleSendCommand}
                disabled={isSendingCommand}
                isLoading={isSendingCommand}
              >
                Kirim Perintah Live
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Modal: QR Code Absensi ── */}
      <Modal
        isOpen={isQrOpen}
        onClose={handleCloseQr}
        title="QR Code Absensi Ujian (Diperbarui 30s)"
        maxWidth="sm"
      >
        {qrDuty && (
          <div className="space-y-4 text-center p-2">
            <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 text-left">
              <h4 className="font-bold text-slate-200 text-sm">{qrDuty.title}</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Kelas: {qrDuty.class_name} | Pelajaran: {qrDuty.subject_name}
              </p>
            </div>

            <div className="p-4 bg-white rounded-2xl inline-block border-4 border-indigo-500/30 shadow-2xl shadow-indigo-500/10">
              <img
                src={`https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(qrToken)}`}
                alt="QR Code Absen"
                className="w-52 h-52 mx-auto"
              />
            </div>

            <div className="flex items-center justify-center gap-2">
              <Badge variant="indigo">
                <span className="flex items-center gap-1.5 font-mono">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                  Regenerasi otomatis dalam {qrCountdown} detik
                </span>
              </Badge>
            </div>

            <p className="text-[11px] text-slate-400 bg-slate-950 p-2.5 rounded-lg border border-slate-850 text-left">
              ⚡ Siswa dapat memindai QR Code ini menggunakan aplikasi siswa untuk mencatat kehadiran otomatis. Token diperbarui setiap 30 detik. Menutup modal ini akan menghancurkan token lama.
            </p>

            <div className="pt-2 flex justify-end">
              <Button variant="outline" onClick={handleCloseQr}>
                Tutup QR Code
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Modal: Berita Acara Ujian (BAP) ── */}
      <Modal
        isOpen={isBapOpen}
        onClose={() => setIsBapOpen(false)}
        title="Berita Acara Ujian & Absensi"
        maxWidth="md"
      >
        {isLoadingBap ? (
          <div className="p-12 text-center flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
            <p className="text-xs text-slate-400">Memuat Berita Acara...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmitBap} className="space-y-4 max-h-[80vh] overflow-y-auto pr-1">
            {bapDuty && bauDoc && (
              <>
                <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500 block">Jadwal Ujian</span>
                    <strong className="text-slate-200 block text-sm mt-0.5">{bapDuty.title}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Status BAP</span>
                    <Badge variant={bauDoc.status === "SUBMITTED" ? "emerald" : "amber"}>
                      {bauDoc.status === "SUBMITTED" ? "TERKIRIM (Bisa Diedit Dalam 24 Jam)" : bauDoc.status}
                    </Badge>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <h4 className="text-xs font-bold text-slate-300 flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-indigo-400" />
                      <span>Daftar Absensi & Kehadiran Kelas ({students.length} Siswa)</span>
                    </h4>
                    <div className="w-full sm:w-56">
                      <Input
                        placeholder="Cari nama atau NISN siswa..."
                        leftIcon={<Search className="w-3.5 h-3.5 text-slate-400" />}
                        value={bapSearchQuery}
                        onChange={(e) => setBapSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="divide-y divide-slate-850 max-h-[250px] overflow-y-auto border border-slate-800 rounded-lg p-2 bg-slate-900/30">
                    {filteredBapStudents.map((student) => {
                      const curStatus = getAttendanceStatusForStudent(student.student_id);

                      return (
                        <div key={student.student_id} className="py-2.5 flex items-center justify-between gap-4 text-xs">
                          <div>
                            <span className="font-bold text-slate-200 block">{student.student_name}</span>
                            <span className="text-[9px] text-slate-500 block">NISN: {student.nisn || "-"}</span>
                          </div>
                          
                          <select
                            value={curStatus}
                            onChange={(e) => handleUpdateStudentAttendance(student.student_id, e.target.value)}
                            className="bg-slate-950 text-slate-200 border border-slate-800 rounded-md py-1 px-2 text-xs focus:ring-1 focus:ring-indigo-500 font-semibold"
                          >
                            <option value="HADIR">Hadir (HADIR)</option>
                            <option value="ALPA">Tidak Hadir (ALPA)</option>
                            <option value="SAKIT">Sakit (SAKIT)</option>
                            <option value="IZIN">Izin (IZIN)</option>
                          </select>
                        </div>
                      );
                    })}
                    {filteredBapStudents.length === 0 && (
                      <p className="text-center py-4 text-slate-500 text-xs">
                        {bapSearchQuery ? "Siswa tidak ditemukan." : "Tidak ada siswa yang terdaftar di kelas ini."}
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-300">Catatan Pengawas (Proctor Notes)</label>
                  <textarea
                    placeholder="Masukkan kejadian penting selama ujian (misal: listrik padam, siswa terlambat, dll.)"
                    value={proctorNotes}
                    onChange={(e) => setProctorNotes(e.target.value)}
                    rows={4}
                    className="w-full bg-slate-950 border border-slate-850 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-3">
                  <Button variant="outline" type="button" onClick={() => setIsBapOpen(false)}>
                    Tutup
                  </Button>
                  <Button
                    variant="primary"
                    type="submit"
                    disabled={isSubmittingBap}
                    isLoading={isSubmittingBap}
                  >
                    Simpan / Submit BAP
                  </Button>
                </div>
              </>
            )}
          </form>
        )}
      </Modal>
    </div>
  );
}
