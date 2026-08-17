import React, { useState, useEffect, useMemo } from "react";
import {
  FileCheck,
  RefreshCw,
  FolderDot,
  CheckCircle2,
  AlertCircle,
  Search,
  Edit2,
  CalendarDays,
  GraduationCap,
  BookOpen,
  RotateCcw,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { MessageBox } from "../../components/ui/MessageBox";
import { Select } from "../../components/ui/Select";
import { useToast } from "../../context/ToastContext";
import { teacherDashboardApi } from "../../api/teacherDashboard";
import type { TeacherAssignment } from "../../api/teacherDashboard";
import { teacherContentApi } from "../../api/teacherContent";
import type { QuestionPackage } from "../../api/teacherContent";

export function TeacherAssignmentsView() {
  const { showToast } = useToast();
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);
  const [packages, setPackages] = useState<QuestionPackage[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Search Filter by Class / Exam Title
  const [searchQuery, setSearchQuery] = useState("");

  // Modal State
  const [selectedAssignment, setSelectedAssignment] = useState<TeacherAssignment | null>(null);
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [isFinalizing, setIsFinalizing] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [assigns, pkgs] = await Promise.all([
        teacherDashboardApi.listAssignments(),
        teacherContentApi.listPackages(),
      ]);
      setAssignments(assigns);
      setPackages(pkgs.filter((p) => p.status === "READY"));
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Data",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Configuration Options for Teacher Assignment
  const [lockBrowserOption, setLockBrowserOption] = useState<boolean>(true);
  const [eydEvalOption, setEydEvalOption] = useState<boolean>(false);
  const [randomizePerTypeOption, setRandomizePerTypeOption] = useState<boolean>(true);

  // Helper for strict grade level matching
  const isGradeMatchStrict = (pkgClassLevel?: string, targetGradeOrClassName?: string): boolean => {
    if (!pkgClassLevel || !targetGradeOrClassName) return true;
    const pG = pkgClassLevel.trim().toUpperCase();
    const tC = targetGradeOrClassName.trim().toUpperCase();

    if (pG === tC) return true;
    if (tC.startsWith(pG + "-") || tC.startsWith(pG + " ") || tC === pG) return true;
    if ((pG === "X" || pG === "10") && (tC.startsWith("X") || tC.startsWith("10"))) return true;
    if ((pG === "XI" || pG === "11") && (tC.startsWith("XI") || tC.startsWith("11"))) return true;
    if ((pG === "XII" || pG === "12") && (tC.startsWith("XII") || tC.startsWith("12"))) return true;
    return false;
  };

  const availablePackagesForSelected = useMemo(() => {
    if (!selectedAssignment) return [];
    const targetGrade = selectedAssignment.grade_level || selectedAssignment.class_name || "";
    const subjName = selectedAssignment.subject_name?.toLowerCase() || "";

    // STRICT FILTER: Only include packages that match the target grade level AND subject
    return packages.filter((p) => {
      const matchGrade = isGradeMatchStrict(p.class_level, targetGrade);
      const matchSubj = !p.subject || p.subject.toLowerCase() === subjName || p.name.toLowerCase().includes(subjName);
      return matchGrade && matchSubj;
    });
  }, [selectedAssignment, packages]);

  // Handle open modal for assigning / changing package
  const handleOpenAddModal = (assign: TeacherAssignment) => {
    setSelectedAssignment(assign);
    setLockBrowserOption(true);
    setEydEvalOption(false);
    setRandomizePerTypeOption(true);

    const targetGrade = assign.grade_level || assign.class_name || "";
    const subjName = assign.subject_name?.toLowerCase() || "";
    const matchPkgs = packages.filter((p) => isGradeMatchStrict(p.class_level, targetGrade) && (!p.subject || p.subject.toLowerCase() === subjName || p.name.toLowerCase().includes(subjName)));

    if (assign.assigned_package_public_id && matchPkgs.some((p) => p.public_id === assign.assigned_package_public_id)) {
      setSelectedPackageId(assign.assigned_package_public_id);
    } else if (matchPkgs.length > 0) {
      setSelectedPackageId(matchPkgs[0].public_id);
    } else {
      setSelectedPackageId("");
    }
  };

  const handleFinalize = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAssignment || !selectedPackageId) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Silakan pilih paket soal." });
      return;
    }

    setIsFinalizing(true);
    try {
      await teacherDashboardApi.finalizeAssignment(selectedAssignment.public_id, selectedPackageId, {
        lock_browser: lockBrowserOption,
        eyd_language_evaluation: eydEvalOption,
        randomize_per_type: randomizePerTypeOption,
      });
      showToast({
        type: "success",
        title: selectedAssignment.has_snapshot ? "Paket Soal Diperbarui" : "Paket Soal Terkunci",
        message: "Paket soal dan konfigurasi ujian berhasil disiapkan.",
      });
      setSelectedAssignment(null);
      fetchData();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memproses Paket Soal", message: err?.message || "Gagal memproses." });
    } finally {
      setIsFinalizing(false);
    }
  };

  // Unassign MessageBox Confirm State
  const [unassigningAssign, setUnassigningAssign] = useState<TeacherAssignment | null>(null);
  const [isUnassigning, setIsUnassigning] = useState(false);

  const handleConfirmUnassign = async () => {
    if (!unassigningAssign) return;
    setIsUnassigning(true);
    try {
      await teacherDashboardApi.unassignAssignment(unassigningAssign.public_id);
      showToast({
        type: "success",
        title: "Penugasan Dibatalkan",
        message: "Penugasan paket soal berhasil dibatalkan dan dikembalikan ke Draft.",
      });
      setSelectedAssignment(null);
      setUnassigningAssign(null);
      fetchData();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Membatalkan Penugasan", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsUnassigning(false);
    }
  };

  // Filtered Assignments by Search Query
  const filteredAssignments = useMemo(() => {
    if (!searchQuery.trim()) return assignments;
    const q = searchQuery.toLowerCase();
    return assignments.filter(
      (a) =>
        a.class_name?.toLowerCase().includes(q) ||
        a.title?.toLowerCase().includes(q) ||
        a.subject_name?.toLowerCase().includes(q) ||
        a.academic_year_name?.toLowerCase().includes(q)
    );
  }, [assignments, searchQuery]);

  const formatDateTime = (dtStr: string) => {
    try {
      const dt = new Date(dtStr);
      return dt.toLocaleString("id-ID", {
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
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-indigo-400" />
            <span>Penugasan Paket Ujian Tulis</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Kelola dan tetapkan paket soal berstatus <strong>READY</strong> untuk jadwal ujian mata pelajaran Anda.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="flex-1">
            <Input
              placeholder="Cari kelas atau judul ujian..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-slate-500" />}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={fetchData}
            disabled={isLoading}
            className="shrink-0"
          >
            Refresh
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="glass-panel p-12 flex flex-col items-center justify-center gap-3">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-xs text-slate-400">Memuat penugasan ujian...</p>
        </div>
      ) : filteredAssignments.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center justify-center gap-3 border-dashed">
          <FolderDot className="w-12 h-12 text-slate-600" />
          <h3 className="text-sm font-bold text-slate-300">
            {searchQuery ? "Kelas/Ujian Tidak Ditemukan" : "Belum Ada Penugasan Ujian"}
          </h3>
          <p className="text-xs text-slate-500 max-w-sm">
            {searchQuery
              ? `Tidak ada jadwal ujian yang cocok dengan kata kunci "${searchQuery}".`
              : "Anda belum di-assign sebagai guru pengampu untuk jadwal ujian yang aktif oleh School Admin."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredAssignments.map((item) => (
            <div
              key={item.id}
              className={`glass-panel p-5 space-y-4 border transition-all ${
                item.has_snapshot
                  ? "border-emerald-500/20 bg-emerald-950/5 hover:border-emerald-500/30"
                  : "border-slate-800 hover:border-slate-700"
              }`}
            >
              {/* Header Info */}
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    {item.academic_year_name && (
                      <span className="text-[10px] font-semibold text-indigo-400 bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-500/20 flex items-center gap-1">
                        <CalendarDays className="w-3 h-3" />
                        {item.academic_year_name}
                      </span>
                    )}
                    <span className="text-[10px] font-semibold text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 uppercase">
                      Status: {item.status}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-100 line-clamp-1">{item.title}</h3>
                  <div className="flex items-center gap-1.5 pt-0.5">
                    <Badge variant="indigo">
                      <span className="flex items-center gap-1">
                        <GraduationCap className="w-3 h-3" />
                        {item.class_name}
                      </span>
                    </Badge>
                    <Badge variant="slate">
                      <span className="flex items-center gap-1">
                        <BookOpen className="w-3 h-3" />
                        {item.subject_name}
                      </span>
                    </Badge>
                  </div>
                </div>
                {item.has_snapshot ? (
                  <Badge variant="emerald">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Terkunci
                    </span>
                  </Badge>
                ) : (
                  <Badge variant="amber">
                    <span className="flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Belum Ada Paket
                    </span>
                  </Badge>
                )}
              </div>

              {/* Time Schedule Details */}
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

              {/* Assigned Package or Action Button */}
              {item.has_snapshot ? (
                <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-850">
                  <div className="flex-1 min-w-0 bg-slate-900/50 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Paket Soal Terpasang:</span>
                    <span className="font-bold text-emerald-400 text-xs truncate block">
                      {item.snapshot_package_name || "Paket Soal Ujian"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={<Edit2 className="w-3.5 h-3.5 text-indigo-400" />}
                      onClick={() => handleOpenAddModal(item)}
                      title="Ubah Paket Soal"
                    >
                      Ubah Paket
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                      onClick={() => setUnassigningAssign(item)}
                      title="Batalkan Penugasan Paket (Draft)"
                    >
                      Batalkan (Draft)
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="pt-2">
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    leftIcon={<FileCheck className="w-4 h-4" />}
                    onClick={() => handleOpenAddModal(item)}
                  >
                    Tetapkan & Kunci Paket Soal
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Modal: Finalize / Change Assignment ── */}
      <Modal
        isOpen={selectedAssignment !== null}
        onClose={() => setSelectedAssignment(null)}
        title={selectedAssignment?.has_snapshot ? "Ubah Paket Soal Ujian" : "Tetapkan Paket Soal Ujian"}
        maxWidth="sm"
      >
        {selectedAssignment && (
          <form onSubmit={handleFinalize} className="space-y-4">
            <div className="bg-slate-900 p-4 rounded-xl space-y-2 border border-slate-800 text-xs">
              <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Detail Jadwal Ujian</h4>
              <p className="text-sm font-bold text-slate-100">{selectedAssignment.title}</p>
              <div className="text-slate-400 flex items-center gap-3 pt-1">
                <span>Tahun: <strong>{selectedAssignment.academic_year_name || "-"}</strong></span>
                <span>Kelas: <strong>{selectedAssignment.class_name}</strong></span>
              </div>
              <p className="text-slate-400">Pelajaran: <strong>{selectedAssignment.subject_name}</strong></p>
            </div>

            {availablePackagesForSelected.length === 0 ? (
              <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-300 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 shrink-0 text-amber-400" />
                <div className="space-y-1">
                  <p className="text-xs font-bold">Tidak Ada Paket Soal Sesuai Tingkat Kelas</p>
                  <p className="text-[10px] text-amber-400/80 leading-relaxed">
                    Tidak ditemukan paket soal berstatus <strong className="text-emerald-400">READY</strong> yang sesuai dengan jenjang tingkat kelas (<strong>{selectedAssignment.grade_level || selectedAssignment.class_name}</strong>) untuk mata pelajaran <strong>{selectedAssignment.subject_name}</strong>. Silakan buat paket soal khusus jenjang ini di menu Paket Soal.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-300">Pilih Paket Soal (Khusus Jenjang Kelas {selectedAssignment.grade_level || selectedAssignment.class_name})</label>
                  <Select
                    value={selectedPackageId}
                    onChange={(e) => setSelectedPackageId(e.target.value)}
                    options={availablePackagesForSelected.map((p) => ({
                      value: p.public_id,
                      label: `${p.name} (Tingkat ${p.class_level})`,
                    }))}
                    required
                  />
                  <p className="text-[10px] text-slate-500 mt-1">
                    💡 Paket soal disaring secara ketat khusus untuk jenjang kelas <strong>{selectedAssignment.grade_level || selectedAssignment.class_name}</strong>.
                  </p>
                </div>

                {/* 3 Opsi Konfigurasi & Keamanan Ujian Guru (Toggle Buttons) */}
                <div className="space-y-2.5 p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <span className="font-bold text-slate-200">Konfigurasi & Keamanan Ujian</span>
                    <span className="text-[10px] text-indigo-400 font-medium bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                      Pengaturan Guru
                    </span>
                  </div>

                  <div className="space-y-2 pt-1">
                    {/* 1. Mode Lockxam Browser Locking */}
                    <button
                      type="button"
                      onClick={() => setLockBrowserOption((prev) => !prev)}
                      className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all duration-200 ${
                        lockBrowserOption
                          ? "bg-indigo-600/15 border-indigo-500/40 text-indigo-300 shadow-sm shadow-indigo-500/10"
                          : "bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300"
                      }`}
                    >
                      <span>Mode Lockxam Browser Locking</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                        lockBrowserOption
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/30"
                          : "bg-slate-800 text-slate-500 border-slate-700"
                      }`}>
                        {lockBrowserOption ? "AKTIF" : "NON-AKTIF"}
                      </span>
                    </button>

                    {/* 2. Penilaian EYD & Tata Bahasa */}
                    <button
                      type="button"
                      onClick={() => setEydEvalOption((prev) => !prev)}
                      className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all duration-200 ${
                        eydEvalOption
                          ? "bg-indigo-600/15 border-indigo-500/40 text-indigo-300 shadow-sm shadow-indigo-500/10"
                          : "bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300"
                      }`}
                    >
                      <span>Penilaian EYD & Tata Bahasa</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                        eydEvalOption
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/30"
                          : "bg-slate-800 text-slate-500 border-slate-700"
                      }`}>
                        {eydEvalOption ? "AKTIF" : "NON-AKTIF"}
                      </span>
                    </button>

                    {/* 3. Acak Soal Berdasarkan Tipe Soal */}
                    <button
                      type="button"
                      onClick={() => setRandomizePerTypeOption((prev) => !prev)}
                      className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-xs font-semibold transition-all duration-200 ${
                        randomizePerTypeOption
                          ? "bg-indigo-600/15 border-indigo-500/40 text-indigo-300 shadow-sm shadow-indigo-500/10"
                          : "bg-slate-900/80 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-300"
                      }`}
                    >
                      <span>Acak Soal Berdasarkan Tipe Soal</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                        randomizePerTypeOption
                          ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/30"
                          : "bg-slate-800 text-slate-500 border-slate-700"
                      }`}>
                        {randomizePerTypeOption ? "AKTIF" : "NON-AKTIF"}
                      </span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between gap-2 pt-3 border-t border-slate-800">
              {selectedAssignment.has_snapshot ? (
                <Button
                  variant="danger"
                  size="sm"
                  type="button"
                  leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                  onClick={() => setUnassigningAssign(selectedAssignment)}
                  disabled={isFinalizing}
                >
                  Batalkan Penugasan
                </Button>
              ) : <div />}
              <div className="flex items-center gap-2">
                <Button variant="outline" type="button" onClick={() => setSelectedAssignment(null)}>
                  Batal
                </Button>
                <Button
                  variant="primary"
                  type="submit"
                  disabled={isFinalizing || availablePackagesForSelected.length === 0}
                  isLoading={isFinalizing}
                >
                  {selectedAssignment.has_snapshot ? "Simpan Perubahan" : "Kunci & Siapkan Ujian"}
                </Button>
              </div>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Custom Confirmation MessageBox: Unassign Package ── */}
      <MessageBox
        isOpen={unassigningAssign !== null}
        onClose={() => setUnassigningAssign(null)}
        type="warning"
        title="Batalkan Penugasan Paket Soal"
        message={
          <div>
            Apakah Anda yakin ingin membatalkan penugasan paket soal pada ujian <strong>"{unassigningAssign?.title}"</strong>?
            <p className="text-[11px] text-slate-400 mt-1">
              Jadwal akan dikembalikan ke status <strong>DRAFT</strong> sehingga siswa belum dapat mengakses ujian ini sampai ditugaskan kembali.
            </p>
          </div>
        }
        confirmText="Batalkan Penugasan"
        cancelText="Tutup"
        onConfirm={handleConfirmUnassign}
        isLoading={isUnassigning}
        confirmVariant="danger"
      />
    </div>
  );
}
