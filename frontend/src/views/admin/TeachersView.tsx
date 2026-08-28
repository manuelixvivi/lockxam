import { useState, useEffect, useCallback, useMemo } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import type { SelectOption } from "../../components/ui/Select";
import { Modal } from "../../components/ui/Modal";
import { MessageBox } from "../../components/ui/MessageBox";
import { Table } from "../../components/ui/Table";
import { useToast } from "../../context/ToastContext";
import { teacherApi } from "../../api/teacher";
import type { TeacherAccount } from "../../api/teacher";
import { subjectApi } from "../../api/subject";
import type { Subject } from "../../api/subject";
import { classApi } from "../../api/class";
import type { ClassEntity } from "../../api/class";
import { ImportExportBar } from "../../components/ui/ImportExportBar";
import { AddDataChoiceModal } from "../../components/ui/AddDataChoiceModal";
import { readXlsxFile } from "../../utils/xlsx";
import { downloadTeacherTemplate } from "../../utils/excelTemplates";
import { copyToClipboard } from "../../utils/clipboard";
import {
  Users,
  UserPlus,
  RefreshCw,
  KeyRound,
  Power,
  CheckCircle2,
  XCircle,
  Copy,
  Eye,
  EyeOff,
  Trash2,
  AlertTriangle,
  Loader2,
  Pencil,
  Search,
  BookOpen,
  GraduationCap,
  Download,
} from "lucide-react";

interface TeachersViewProps {
  onNavigate?: (href: string) => void;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TeachersView({ onNavigate }: TeachersViewProps) {
  const { showToast } = useToast();

  // State
  const [teachers, setTeachers] = useState<TeacherAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSubject, setFilterSubject] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  // Detail Modal State
  const [detailTarget, setDetailTarget] = useState<TeacherAccount | null>(null);

  // Master Data State
  const [masterSubjects, setMasterSubjects] = useState<Subject[]>([]);
  const [masterClasses, setMasterClasses] = useState<ClassEntity[]>([]);

  // Options states
  const [availableClasses, setAvailableClasses] = useState<string[]>([]);
  const [availableSubjects, setAvailableSubjects] = useState<string[]>([]);

  // Selection / Bulk delete states
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkDeleteProgress, setBulkDeleteProgress] = useState<{ current: number; total: number } | null>(null);

  // Add Teacher Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newNip, setNewNip] = useState("");
  const [newTeacherCode, setNewTeacherCode] = useState("");
  const [newGender, setNewGender] = useState("");
  const [newRegisteredYear, setNewRegisteredYear] = useState(new Date().getFullYear().toString());
  const [newClassesTaught, setNewClassesTaught] = useState<string[]>([]);
  const [newSubjectsTaught, setNewSubjectsTaught] = useState<string[]>([]);

  const [createdTeacherInfo, setCreatedTeacherInfo] = useState<{ username: string; default_password: string } | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState(false);
  const [isImportingXlsx, setIsImportingXlsx] = useState(false);

  // Edit Teacher Modal State
  const [editTarget, setEditTarget] = useState<TeacherAccount | null>(null);
  const [editName, setEditName] = useState("");
  const [editNip, setEditNip] = useState("");
  const [editTeacherCode, setEditTeacherCode] = useState("");
  const [editGender, setEditGender] = useState("");
  const [editRegisteredYear, setEditRegisteredYear] = useState("");
  const [editClassesTaught, setEditClassesTaught] = useState<string[]>([]);
  const [editSubjectsTaught, setEditSubjectsTaught] = useState<string[]>([]);
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // Reset Password Modal
  const [resetTarget, setResetTarget] = useState<TeacherAccount | null>(null);
  const [resetResult, setResetResult] = useState<{ username: string; new_password: string } | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);

  // Active/Delete states
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Load teachers, master subjects, and master classes
  const loadTeachers = useCallback(async () => {
    setIsLoading(true);
    try {
      const [teachersData, loadedSubjects, loadedClasses] = await Promise.all([
        teacherApi.listTeachers(),
        subjectApi.listSubjects(true).catch(() => []),
        classApi.listClasses().catch(() => []),
      ]);
      setTeachers(teachersData);
      setMasterSubjects(loadedSubjects);
      setMasterClasses(loadedClasses);
      setSelectedIds([]); // Clear selection

      // Extract subject names exclusively from master data
      const masterSubjectNames = loadedSubjects.map((s: Subject) => s.name);
      setAvailableSubjects(masterSubjectNames);

      // Extract class names exclusively from master data
      const masterClassNames = loadedClasses.map((c: ClassEntity) => c.name);
      setAvailableClasses(masterClassNames);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memuat daftar guru.", message: err?.message });
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadTeachers();
  }, [loadTeachers]);

  // Filtered list
  const filtered = useMemo(() => {
    return teachers.filter((t) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        (t.name || "").toLowerCase().includes(q) ||
        t.username.toLowerCase().includes(q) ||
        (t.nip || "").toLowerCase().includes(q) ||
        (t.teacher_code || "").toLowerCase().includes(q);

      const matchesSubject = filterSubject
        ? (t.subjects_taught || []).includes(filterSubject)
        : true;

      const matchesStatus =
        filterStatus === "active"
          ? t.is_active
          : filterStatus === "inactive"
          ? !t.is_active
          : true;

      return matchesSearch && matchesSubject && matchesStatus;
    });
  }, [teachers, searchQuery, filterSubject, filterStatus]);

  // Selection handlers
  const handleToggleSelect = (publicId: string) => {
    setSelectedIds((prev) =>
      prev.includes(publicId) ? prev.filter((id) => id !== publicId) : [...prev, publicId]
    );
  };

  const handleToggleAll = () => {
    const allFilteredIds = filtered.map((t) => t.public_id);
    const areAllSelected = allFilteredIds.every((id) => selectedIds.includes(id));
    if (areAllSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allFilteredIds.includes(id)));
    } else {
      setSelectedIds((prev) => {
        const union = new Set([...prev, ...allFilteredIds]);
        return Array.from(union);
      });
    }
  };

  // Bulk delete confirm states
  const [isBulkDeleteConfirmOpen, setIsBulkDeleteConfirmOpen] = useState(false);
  const [deletingTeacherObj, setDeletingTeacherObj] = useState<TeacherAccount | null>(null);

  const handleBulkDelete = () => {
    if (selectedIds.length === 0) return;
    setIsBulkDeleteConfirmOpen(true);
  };

  const handleExecuteBulkDelete = async () => {
    const count = selectedIds.length;
    if (count === 0) return;
    setIsBulkDeleteConfirmOpen(false);

    setBulkDeleteProgress({ current: 0, total: count });
    let successCount = 0;
    let failedCount = 0;

    for (let i = 0; i < count; i++) {
      const publicId = selectedIds[i];
      try {
        await teacherApi.deleteTeacher(publicId);
        successCount++;
      } catch {
        failedCount++;
      }
      setBulkDeleteProgress({ current: i + 1, total: count });
    }

    setBulkDeleteProgress(null);
    setSelectedIds([]);
    showToast({
      type: failedCount === 0 ? "success" : "warning",
      title: "Hapus Guru Selesai",
      message: `${successCount} guru berhasil dihapus. ${failedCount > 0 ? `${failedCount} gagal.` : ""}`,
    });
    await loadTeachers();
  };

  // Create teacher
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newNip.trim() || !newTeacherCode.trim() || !newGender || !newRegisteredYear) {
      showToast({
        type: "warning",
        title: "Validasi Gagal",
        message: "Nama Lengkap, NIP, Kode Guru, Jenis Kelamin, dan Tahun Terdaftar wajib diisi.",
      });
      return;
    }

    setIsCreating(true);
    try {
      const res = await teacherApi.createTeacher({
        name: newName.trim(),
        nip: newNip.trim(),
        teacher_code: newTeacherCode.trim().toUpperCase(),
        gender: newGender,
        registered_year: parseInt(newRegisteredYear, 10),
        classes_taught: newClassesTaught,
        subjects_taught: newSubjectsTaught,
      });
      setCreatedTeacherInfo({
        username: res.account.username,
        default_password: res.default_password,
      });
      showToast({ type: "success", title: `Akun guru berhasil dibuat.` });

      // Reset state fields
      setNewName("");
      setNewNip("");
      setNewTeacherCode("");
      setNewGender("");
      setNewRegisteredYear(new Date().getFullYear().toString());
      setNewClassesTaught([]);
      setNewSubjectsTaught([]);
      await loadTeachers();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal membuat akun guru.", message: err?.message });
    } finally {
      setIsCreating(false);
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (teacher: TeacherAccount) => {
    setEditTarget(teacher);
    setEditName(teacher.name || "");
    setEditNip(teacher.nip || "");
    setEditTeacherCode(teacher.teacher_code || "");
    setEditGender(teacher.gender || "");
    setEditRegisteredYear(teacher.registered_year ? teacher.registered_year.toString() : "");
    setEditClassesTaught(teacher.classes_taught || []);
    setEditSubjectsTaught(teacher.subjects_taught || []);
  };

  // Update teacher
  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTarget) return;
    if (!editName.trim() || !editNip.trim() || !editTeacherCode.trim() || !editGender || !editRegisteredYear) {
      showToast({
        type: "warning",
        title: "Validasi Gagal",
        message: "Nama Lengkap, NIP, Kode Guru, Jenis Kelamin, dan Tahun Terdaftar wajib diisi.",
      });
      return;
    }

    setIsSubmittingEdit(true);
    try {
      await teacherApi.updateTeacher(editTarget.public_id, {
        name: editName.trim(),
        nip: editNip.trim(),
        teacher_code: editTeacherCode.trim().toUpperCase(),
        gender: editGender,
        registered_year: parseInt(editRegisteredYear, 10),
        classes_taught: editClassesTaught,
        subjects_taught: editSubjectsTaught,
      });
      showToast({ type: "success", title: "Data guru berhasil diperbarui." });
      setEditTarget(null);
      await loadTeachers();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memperbarui data guru.", message: err?.message });
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  // Delete teacher
  const handleDelete = (teacher: TeacherAccount) => {
    setDeletingTeacherObj(teacher);
  };

  const handleConfirmSingleDelete = async () => {
    if (!deletingTeacherObj) return;
    setDeletingId(deletingTeacherObj.public_id);
    try {
      await teacherApi.deleteTeacher(deletingTeacherObj.public_id);
      showToast({ type: "success", title: "Akun guru berhasil dihapus." });
      setDeletingTeacherObj(null);
      await loadTeachers();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal menghapus akun guru.", message: err?.message });
    } finally {
      setDeletingId(null);
    }
  };

  // Toggle active
  const handleToggleActive = async (teacher: TeacherAccount) => {
    setTogglingId(teacher.public_id);
    try {
      await teacherApi.toggleActive(teacher.public_id);
      const action = teacher.is_active ? "dinonaktifkan" : "diaktifkan";
      showToast({ type: "success", title: `Akun '${teacher.username}' berhasil ${action}.` });
      await loadTeachers();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal mengubah status akun.", message: err?.message });
    } finally {
      setTogglingId(null);
    }
  };

  // Reset password
  const handleResetPassword = async () => {
    if (!resetTarget) return;
    setIsResetting(true);
    try {
      const result = await teacherApi.resetPassword(resetTarget.public_id);
      setResetResult({ username: result.username, new_password: result.new_password });
      showToast({ type: "success", title: "Kata sandi berhasil direset." });
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal mereset kata sandi.", message: err?.message });
    } finally {
      setIsResetting(false);
    }
  };

  const handleCopy = async (text: string) => {
    const success = await copyToClipboard(text);
    if (success) {
      showToast({ type: "success", title: "Disalin ke clipboard!" });
    } else {
      showToast({ type: "error", title: "Gagal menyalin secara otomatis." });
    }
  };

  const closeResetModal = () => {
    setResetTarget(null);
    setResetResult(null);
    setShowResetPassword(false);
  };

  // Stats
  const totalTeachers = teachers.length;
  const activeTeachers = teachers.filter((t) => t.is_active).length;
  const inactiveTeachers = teachers.filter((t) => !t.is_active).length;

  const genderOptions: SelectOption[] = [
    { value: "", label: "-- Pilih Jenis Kelamin --" },
    { value: "L", label: "Laki-laki (L)" },
    { value: "P", label: "Perempuan (P)" },
  ];

  return (
    <AppShell activeHref="/admin/teachers" onNavigate={onNavigate}>
      <Breadcrumb
        items={[
          { label: "School Admin", href: "/admin/profile" },
          { label: "Direktori Guru" },
        ]}
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Users className="w-5 h-5" />
            </div>
            Direktori Guru
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Kelola data staf pengajar, alokasi mata pelajaran ampu, kelas ajar, serta hak akses login guru.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="ghost"
            size="md"
            leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
            onClick={() => {
              const exportBar = document.getElementById("export-guru-btn");
              if (exportBar) exportBar.click();
            }}
          >
            Ekspor Excel
          </Button>
          <Button
            variant="primary"
            size="md"
            leftIcon={<UserPlus className="w-4 h-4" />}
            onClick={() => setIsAddChoiceOpen(true)}
          >
            Tambah Guru
          </Button>
        </div>
      </div>

      {/* Stats Bento Box on Mobile / 3-Column on Desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4 mb-6">
        <div className="glass-panel p-3.5 sm:p-4 flex items-center justify-between col-span-2 lg:col-span-1">
          <div className="flex items-center gap-3 sm:gap-3.5">
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
              <Users className="w-4 h-4 sm:w-5 sm:h-5 text-indigo-400" />
            </div>
            <div>
              <p className="text-[11px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Guru</p>
              <p className="text-xl sm:text-2xl font-black text-slate-100 mt-0.5">{totalTeachers}</p>
            </div>
          </div>
          <span className="text-[10px] font-medium text-slate-500 bg-slate-900/60 px-2.5 py-1 rounded-full border border-slate-800">
            Terdaftar
          </span>
        </div>

        <div className="glass-panel p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-2 col-span-1">
          <div className="flex items-center gap-2 sm:gap-3.5">
            <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Aktif</p>
              <p className="text-lg sm:text-2xl font-black text-emerald-400 mt-0.5">{activeTeachers}</p>
            </div>
          </div>
          <span className="text-[9px] sm:text-[10px] font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-emerald-500/20">
            {totalTeachers > 0 ? Math.round((activeTeachers / totalTeachers) * 100) : 0}%
          </span>
        </div>

        <div className="glass-panel p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-2 col-span-1">
          <div className="flex items-center gap-2 sm:gap-3.5">
            <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0">
              <XCircle className="w-4 h-4 sm:w-5 sm:h-5 text-rose-400" />
            </div>
            <div>
              <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Nonaktif</p>
              <p className="text-lg sm:text-2xl font-black text-rose-400 mt-0.5">{inactiveTeachers}</p>
            </div>
          </div>
          <span className="text-[9px] sm:text-[10px] font-semibold text-rose-400 bg-rose-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-rose-500/20">
            {inactiveTeachers} Akun
          </span>
        </div>
      </div>

      {/* Main Panel */}
      <div className="glass-panel p-6 space-y-4">
        {/* Filter & Toolbar */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 pb-3 border-b border-slate-850">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="flex-1">
              <Input
                placeholder="Cari nama guru, Kode Guru, NIP, atau username..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="w-4 h-4 text-slate-400" />}
              />
            </div>
            <Button
              variant="ghost"
              size="md"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadTeachers}
              isLoading={isLoading}
              title="Muat ulang data"
              className="shrink-0"
            >
              Refresh
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Filter Mapel */}
            <div className="w-48">
              <Select
                options={[
                  { value: "", label: "Semua Mapel" },
                  ...availableSubjects.map((s) => ({ value: s, label: s })),
                ]}
                value={filterSubject}
                onChange={(e) => setFilterSubject(e.target.value)}
              />
            </div>

            {/* Filter Status */}
            <div className="w-36">
              <Select
                options={[
                  { value: "", label: "Semua Status" },
                  { value: "active", label: "Aktif" },
                  { value: "inactive", label: "Nonaktif" },
                ]}
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Action Toolbar & Import/Export */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-1">
          {/* Hidden ImportExportBar helper for programmatic export & template */}
          <div className="hidden">
            <ImportExportBar<TeacherAccount>
              exportData={filtered}
              exportColumns={[
                { label: "Nama Lengkap", key: "name" },
                { label: "NIP", key: "nip" },
                { label: "Kode Guru", key: "teacher_code" },
                { label: "Jenis Kelamin", key: "gender" },
                { label: "Tahun Terdaftar", key: "registered_year" },
                { label: "Kelas diampu", key: "classes_taught" },
                { label: "Mapel diampu", key: "subjects_taught" },
                { label: "Username", key: "username" },
                { label: "Status", key: "is_active" },
                { label: "Login Terakhir", key: "last_login" },
                { label: "Terdaftar", key: "created_at" },
              ]}
              exportFilename="daftar-guru"
              sheetName="Guru"
              templateHeaders={["Nama Lengkap", "NIP", "Kode Guru", "Jenis Kelamin (L/P)", "Tahun Terdaftar", "Kelas diampu", "Mapel diampu"]}
              templateSamples={[
                {
                  "Nama Lengkap": "Drs. H. Mulyadi",
                  NIP: "197508222002121003",
                  "Kode Guru": "MULYADI",
                  "Jenis Kelamin (L/P)": "L",
                  "Tahun Terdaftar": "2024",
                  "Kelas diampu": masterClasses.length > 0 ? masterClasses.slice(0, 2).map((c) => c.name).join("; ") : "X-MIPA-1; X-MIPA-2",
                  "Mapel diampu": masterSubjects.length > 0 ? masterSubjects.slice(0, 2).map((s) => s.name).join("; ") : "Matematika; Fisika",
                },
              ]}
              templateFilename="template-import-guru"
              onImportRow={async () => null}
              onImportDone={loadTeachers}
            />
          </div>

          <span className="text-xs text-slate-400 font-mono">
            Menampilkan <strong className="text-slate-200">{filtered.length}</strong> dari {totalTeachers} guru
          </span>
        </div>

        {/* Selection Alert Banner */}
        {selectedIds.length > 0 && (
          <div className="flex items-center justify-between p-3 rounded-xl bg-rose-950/30 border border-rose-500/30 text-xs animate-fade-in">
            <div className="flex items-center gap-2 text-rose-300 font-semibold">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Terpilih {selectedIds.length} guru</span>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setSelectedIds([])}>
                Batal
              </Button>
              <Button
                variant="danger"
                size="sm"
                leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                onClick={handleBulkDelete}
              >
                Hapus Terpilih
              </Button>
            </div>
          </div>
        )}

        {/* Bulk Delete Progress Bar */}
        {bulkDeleteProgress && (
          <div className="flex items-center gap-3 p-3 rounded-xl bg-rose-950/20 border border-rose-500/30">
            <Loader2 className="w-4 h-4 animate-spin text-rose-400 shrink-0" />
            <div className="flex-1">
              <div className="flex justify-between text-xs text-rose-300 font-medium mb-1">
                <span>Menghapus data guru terpilih…</span>
                <span>{bulkDeleteProgress.current}/{bulkDeleteProgress.total}</span>
              </div>
              <div className="h-1.5 rounded-full bg-rose-950/50">
                <div
                  className="h-1.5 rounded-full bg-rose-500 transition-all"
                  style={{ width: `${(bulkDeleteProgress.current / bulkDeleteProgress.total) * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* ── Mobile card list (hidden on md+) ── */}
        <div className="block md:hidden space-y-3">
          {isLoading ? (
            <p className="text-center text-xs text-slate-500 py-8">Memuat data...</p>
          ) : filtered.length === 0 ? (
            <p className="text-center text-xs text-slate-500 py-8">
              {searchQuery || filterSubject || filterStatus
                ? "Tidak ada guru yang memenuhi kriteria pencarian/filter."
                : "Belum ada akun guru. Klik 'Tambah Guru' untuk membuat akun pertama."}
            </p>
          ) : (
            filtered.map((item) => (
              <div
                key={item.public_id}
                className={`rounded-xl border p-4 space-y-3 transition-colors ${
                  selectedIds.includes(item.public_id)
                    ? "border-rose-500/40 bg-rose-950/10"
                    : "border-slate-800 bg-slate-900/50"
                }`}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900 cursor-pointer shrink-0 mt-1"
                    checked={selectedIds.includes(item.public_id)}
                    onChange={() => handleToggleSelect(item.public_id)}
                  />
                  <div className="w-10 h-10 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-sm font-bold text-indigo-300 shrink-0">
                    {(item.name || item.username).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-200 truncate">
                      {item.name || "—"}
                    </p>
                    <p className="text-xs font-mono text-slate-400 mt-0.5 truncate">
                      {item.username}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5 font-mono">
                      NIP: {item.nip || "—"}
                    </p>
                  </div>
                  {item.is_active ? (
                    <Badge variant="emerald" size="sm">Aktif</Badge>
                  ) : (
                    <Badge variant="crimson" size="sm">Nonaktif</Badge>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<Eye className="w-3.5 h-3.5 text-indigo-400" />}
                    onClick={() => setDetailTarget(item)}
                    className="flex-1"
                  >
                    Detail
                  </Button>
                  <Button
                    variant={item.is_active ? "ghost" : "primary"}
                    size="sm"
                    leftIcon={<Power className="w-3.5 h-3.5" />}
                    onClick={() => handleToggleActive(item)}
                    isLoading={togglingId === item.public_id}
                    className="flex-1"
                  >
                    {item.is_active ? "Matikan" : "Aktifkan"}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                    onClick={() => handleDelete(item)}
                    isLoading={deletingId === item.public_id}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        {/* ── Desktop Clean Table (Nama, Username, Status, Aksi: Detail, Power, Hapus) ── */}
        <div className="hidden md:block">
          <Table<TeacherAccount>
            keyExtractor={(item) => item.public_id}
            isLoading={isLoading}
            emptyMessage={
              searchQuery || filterSubject || filterStatus
                ? "Tidak ada guru yang memenuhi filter."
                : "Belum ada guru terdaftar. Klik 'Tambah Guru' untuk mendaftarkan akun."
            }
            data={filtered}
            columns={[
              {
                key: "select",
                header: (
                  <input
                    type="checkbox"
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900 cursor-pointer"
                    checked={filtered.length > 0 && filtered.every((t) => selectedIds.includes(t.public_id))}
                    onChange={handleToggleAll}
                  />
                ),
                width: "44px",
                render: (item) => (
                  <input
                    type="checkbox"
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900 cursor-pointer"
                    checked={selectedIds.includes(item.public_id)}
                    onChange={() => handleToggleSelect(item.public_id)}
                  />
                ),
              },
              {
                key: "teacher_info",
                header: "Nama Guru & NIP",
                render: (item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-xs font-bold text-indigo-300 shrink-0">
                      {(item.name || item.username).charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-slate-100 truncate">{item.name || "—"}</div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        NIP: {item.nip || "—"} | Kode: <span className="text-indigo-400 font-bold">{item.teacher_code || "—"}</span>
                      </div>
                    </div>
                  </div>
                ),
              },
              {
                key: "username",
                header: "Username",
                width: "180px",
                render: (item) => (
                  <span className="font-mono text-xs text-indigo-300 bg-slate-900/80 border border-slate-800 px-2.5 py-1 rounded-lg">
                    {item.username}
                  </span>
                ),
              },
              {
                key: "is_active",
                header: "Status",
                width: "120px",
                render: (item) =>
                  item.is_active ? (
                    <Badge variant="emerald" size="sm">● Aktif</Badge>
                  ) : (
                    <Badge variant="crimson" size="sm">● Nonaktif</Badge>
                  ),
              },
              {
                key: "actions",
                header: "Aksi",
                align: "right",
                width: "220px",
                render: (item) => (
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      leftIcon={<Eye className="w-3.5 h-3.5 text-indigo-400" />}
                      onClick={() => setDetailTarget(item)}
                      title="Lihat profil detail & opsi lainnya"
                    >
                      Detail
                    </Button>
                    <Button
                      variant={item.is_active ? "ghost" : "primary"}
                      size="sm"
                      leftIcon={<Power className="w-3.5 h-3.5" />}
                      onClick={() => handleToggleActive(item)}
                      isLoading={togglingId === item.public_id}
                      title={item.is_active ? "Nonaktifkan akun" : "Aktifkan akun"}
                    >
                      {item.is_active ? "Nonaktifkan" : "Aktifkan"}
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                      onClick={() => handleDelete(item)}
                      isLoading={deletingId === item.public_id}
                      title="Hapus akun permanen"
                    />
                  </div>
                ),
              },
            ]}
          />
        </div>
      </div>

      {/* ── Modal: Choice Add Data ── */}
      <AddDataChoiceModal
        isOpen={isAddChoiceOpen}
        onClose={() => setIsAddChoiceOpen(false)}
        entityName="Guru"
        onSelectManual={() => {
          setCreatedTeacherInfo(null);
          setShowAddModal(true);
        }}
        onDownloadTemplate={downloadTeacherTemplate}
        onImportXlsx={async (file) => {
          setIsImportingXlsx(true);
          try {
            const rows = await readXlsxFile(file);
            if (rows.length === 0) {
              showToast({ type: "error", title: "File Kosong", message: "File XLSX tidak berisi data." });
              return;
            }

            const payloadTeachers = rows.map((row, idx) => {
              const name = String(row["Nama Lengkap"] || "").trim();
              const rawNip = String(row["NIP"] || "").trim().replace(/\D/g, "");
              const nip = rawNip || undefined;
              const rawTeacherCode = String(row["Kode Guru"] || "").trim();
              const teacherCode = rawTeacherCode || undefined;
              const rawGender = String(row["Jenis Kelamin (L/P)"] || "").trim().toUpperCase();
              const gender = rawGender === "L" || rawGender === "LAKI-LAKI" ? "L" : rawGender === "P" || rawGender === "PEREMPUAN" ? "P" : "";
              const registeredYearRaw = String(row["Tahun Terdaftar"] || "").trim();
              const registeredYear = registeredYearRaw ? parseInt(registeredYearRaw, 10) : undefined;

              return {
                name,
                nip,
                teacher_code: teacherCode,
                gender,
                registered_year: registeredYear,
                row_num: idx + 2,
              };
            }).filter(t => t.name || t.nip);

            const result = await teacherApi.importTeachers({ teachers: payloadTeachers });
            showToast({
              type: "success",
              title: "Impor Berhasil",
              message: `Berhasil mengimpor ${result.imported_count} guru.`,
            });
            await loadTeachers();
          } catch (err: any) {
            const errMsg = err?.response?.data?.message || err?.message || "Format file salah.";
            showToast({ type: "error", title: "Gagal Memproses Impor", message: errMsg });
          } finally {
            setIsImportingXlsx(false);
          }
        }}
        isLoadingImport={isImportingXlsx}
      />

      {/* ── Modal: Detail Guru ── */}
      <Modal
        isOpen={!!detailTarget}
        onClose={() => setDetailTarget(null)}
        title="Profil Guru"
        maxWidth="md"
      >
        {detailTarget && (
          <div className="space-y-4">
            {/* Header Hero Card */}
            <div className="relative overflow-hidden p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-xl font-black text-indigo-300 shadow-inner">
                    {(detailTarget.name || detailTarget.username).charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-slate-100">{detailTarget.name || "—"}</h3>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="inline-flex items-center gap-1 font-mono text-xs text-indigo-300 bg-indigo-950/60 border border-indigo-500/20 px-2 py-0.5 rounded-md">
                        {detailTarget.username}
                        <button
                          type="button"
                          onClick={() => handleCopy(detailTarget.username)}
                          className="hover:text-white p-0.5"
                          title="Salin Username"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </span>
                      {detailTarget.is_active ? (
                        <Badge variant="emerald" size="sm">● Akun Aktif</Badge>
                      ) : (
                        <Badge variant="crimson" size="sm">● Nonaktif</Badge>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Structured Info Card */}
            <div className="grid grid-cols-2 gap-3 p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">NIP</span>
                <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-slate-200">
                  <span>{detailTarget.nip || "—"}</span>
                  {detailTarget.nip && (
                    <button
                      type="button"
                      onClick={() => handleCopy(detailTarget.nip!)}
                      className="text-slate-500 hover:text-indigo-400 p-0.5"
                      title="Salin NIP"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Kode Guru</span>
                <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-slate-200">
                  <span>{detailTarget.teacher_code || "—"}</span>
                  {detailTarget.teacher_code && (
                    <button
                      type="button"
                      onClick={() => handleCopy(detailTarget.teacher_code!)}
                      className="text-slate-500 hover:text-indigo-400 p-0.5"
                      title="Salin Kode Guru"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-1 pt-2 border-t border-slate-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Jenis Kelamin</span>
                <p className="text-xs font-bold text-slate-200">
                  {detailTarget.gender === "L" ? "Laki-laki (L)" : detailTarget.gender === "P" ? "Perempuan (P)" : "—"}
                </p>
              </div>

              <div className="space-y-1 pt-2 border-t border-slate-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Tahun Terdaftar</span>
                <p className="font-mono text-xs font-bold text-slate-200">{detailTarget.registered_year || "—"}</p>
              </div>

              <div className="space-y-1 pt-2 border-t border-slate-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Login Terakhir</span>
                <p className="font-mono text-xs text-slate-300">{formatDate(detailTarget.last_login)}</p>
              </div>
            </div>

            {/* Mata Pelajaran Diampu */}
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-indigo-400" />
                  Mata Pelajaran yang Diampu
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  {detailTarget.subjects_taught?.length || 0} Mapel
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {detailTarget.subjects_taught && detailTarget.subjects_taught.length > 0 ? (
                  detailTarget.subjects_taught.map((s) => (
                    <Badge key={s} variant="indigo" size="sm">
                      {s}
                    </Badge>
                  ))
                ) : (
                  <p className="text-xs text-slate-500 italic py-1">Belum ada mata pelajaran yang di-assign.</p>
                )}
              </div>
            </div>

            {/* Kelas yang Diajar */}
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <GraduationCap className="w-4 h-4 text-indigo-400" />
                  Kelas yang Diajar
                </span>
                <span className="text-[11px] font-mono text-slate-500">
                  {(detailTarget.classes_taught || []).filter((c) =>
                    availableClasses.some((ac) => ac.toLowerCase() === c.toLowerCase())
                  ).length} Kelas
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {(() => {
                  const validClasses = (detailTarget.classes_taught || []).filter((c) =>
                    availableClasses.some((ac) => ac.toLowerCase() === c.toLowerCase())
                  );
                  return validClasses.length > 0 ? (
                    validClasses.map((c) => (
                      <Badge key={c} variant="slate" size="sm">
                        {c}
                      </Badge>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 italic py-1">Belum ada kelas aktif yang di-assign.</p>
                  );
                })()}
              </div>
            </div>

            {/* Footer Action Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Pencil className="w-3.5 h-3.5 text-indigo-400" />}
                  onClick={() => {
                    const t = detailTarget;
                    setDetailTarget(null);
                    handleOpenEdit(t);
                  }}
                >
                  Edit Data
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<KeyRound className="w-3.5 h-3.5 text-amber-400" />}
                  onClick={() => {
                    const t = detailTarget;
                    setDetailTarget(null);
                    setResetTarget(t);
                    setResetResult(null);
                  }}
                >
                  Reset Sandi
                </Button>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setDetailTarget(null)}
              >
                Tutup
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Modal: Tambah Guru Baru ── */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false);
          setCreatedTeacherInfo(null);
        }}
        title={createdTeacherInfo ? "Akun Guru Berhasil Dibuat" : "Tambah Akun Guru Baru"}
        maxWidth="lg"
      >
        {createdTeacherInfo ? (
          <div className="space-y-5">
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-center space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
              <h4 className="text-base font-black text-slate-100">Pendaftaran Guru Sukses!</h4>
              <p className="text-xs text-slate-400">
                Berikan informasi akun berikut kepada guru yang bersangkutan. Guru dapat mengubah sandi saat pertama kali login.
              </p>
            </div>

            <div className="space-y-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">Username / Login:</span>
                <div className="flex items-center gap-2 font-mono font-bold text-slate-200">
                  <span>{createdTeacherInfo.username}</span>
                  <button
                    onClick={() => handleCopy(createdTeacherInfo.username)}
                    className="p-1 hover:text-indigo-400 transition-colors"
                    title="Salin Username"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-slate-800 pt-3">
                <span className="text-xs text-slate-400 font-medium">Kata Sandi Default:</span>
                <div className="flex items-center gap-2 font-mono font-bold text-indigo-300">
                  <span>{createdTeacherInfo.default_password}</span>
                  <button
                    onClick={() => handleCopy(createdTeacherInfo.default_password)}
                    className="p-1 hover:text-indigo-400 transition-colors"
                    title="Salin Kata Sandi"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                onClick={() => {
                  setShowAddModal(false);
                  setCreatedTeacherInfo(null);
                }}
              >
                Selesai & Tutup
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Input
                label="Nama Lengkap Guru (Wajib)"
                placeholder="Contoh: Drs. H. Mulyadi, M.Pd"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
              />
              <Input
                label="NIP (Nomor Induk Pegawai)"
                placeholder="Contoh: 197508222002121003"
                value={newNip}
                onChange={(e) => setNewNip(e.target.value)}
                required
              />
              <Input
                label="Kode Guru (Wajib)"
                placeholder="Contoh: MULYADI"
                value={newTeacherCode}
                onChange={(e) => setNewTeacherCode(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Jenis Kelamin"
                options={genderOptions}
                value={newGender}
                onChange={(e) => setNewGender(e.target.value)}
                required
              />
              <Input
                label="Tahun Terdaftar / Masuk"
                type="number"
                placeholder="Contoh: 2024"
                value={newRegisteredYear}
                onChange={(e) => setNewRegisteredYear(e.target.value)}
              />
            </div>

            {/* Mata Pelajaran Diampu Multi-Select */}
            <div className="space-y-2 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300 block">
                  Mata Pelajaran yang Diampu <span className="text-slate-500 font-normal">(Opsional)</span>
                </label>
                {onNavigate && (
                  <button
                    type="button"
                    onClick={() => onNavigate("/admin/subjects")}
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 underline"
                  >
                    Kelola Master Mapel
                  </button>
                )}
              </div>
              {availableSubjects.length === 0 ? (
                <p className="text-[11px] text-slate-400 italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                  Belum ada mata pelajaran di Master. Daftarkan di menu <strong>Master Mata Pelajaran</strong> terlebih dahulu.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                  {availableSubjects.map((s) => {
                    const isChecked = newSubjectsTaught.includes(s);
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() =>
                          setNewSubjectsTaught((prev) =>
                            isChecked ? prev.filter((item) => item !== s) : [...prev, s]
                          )
                        }
                        className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                          isChecked
                            ? "bg-indigo-600 border-indigo-500 text-white font-medium shadow-sm shadow-indigo-600/30"
                            : "bg-slate-900 border-slate-750 text-slate-400 hover:border-slate-600"
                        }`}
                      >
                        {isChecked ? "✓ " : "+ "}
                        {s}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Kelas Diampu Multi-Select */}
            <div className="space-y-2 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300 block">
                  Kelas yang Diajar <span className="text-slate-500 font-normal">(Opsional)</span>
                </label>
                {onNavigate && (
                  <button
                    type="button"
                    onClick={() => onNavigate("/admin/classes")}
                    className="text-[11px] text-indigo-400 hover:text-indigo-300 underline"
                  >
                    Kelola Master Kelas
                  </button>
                )}
              </div>
              {availableClasses.length === 0 ? (
                <p className="text-[11px] text-slate-400 italic bg-slate-950/40 p-2.5 rounded-lg border border-slate-800">
                  Belum ada rombel kelas di Master. Buat kelas di menu <strong>Manajemen Kelas</strong> terlebih dahulu.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                  {availableClasses.map((c) => {
                    const isChecked = newClassesTaught.includes(c);
                    return (
                      <button
                        key={c}
                        type="button"
                        onClick={() =>
                          setNewClassesTaught((prev) =>
                            isChecked ? prev.filter((item) => item !== c) : [...prev, c]
                          )
                        }
                        className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                          isChecked
                            ? "bg-indigo-600 border-indigo-500 text-white font-medium shadow-sm shadow-indigo-600/30"
                            : "bg-slate-900 border-slate-750 text-slate-400 hover:border-slate-600"
                        }`}
                      >
                        {isChecked ? "✓ " : "+ "}
                        {c}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button type="button" variant="ghost" onClick={() => setShowAddModal(false)}>
                Batal
              </Button>
              <Button
                type="submit"
                variant="primary"
                leftIcon={<UserPlus className="w-4 h-4" />}
                isLoading={isCreating}
              >
                Daftarkan Akun Guru
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Modal: Edit Guru ── */}
      <Modal
        isOpen={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={`Edit Data Guru: ${editTarget?.name || editTarget?.username}`}
        maxWidth="lg"
      >
        <form onSubmit={handleUpdate} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input
              label="Nama Lengkap"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              required
            />
            <Input
              label="NIP"
              value={editNip}
              onChange={(e) => setEditNip(e.target.value)}
              required
            />
            <Input
              label="Kode Guru"
              value={editTeacherCode}
              onChange={(e) => setEditTeacherCode(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Jenis Kelamin"
              options={genderOptions}
              value={editGender}
              onChange={(e) => setEditGender(e.target.value)}
              required
            />
            <Input
              label="Tahun Terdaftar"
              type="number"
              value={editRegisteredYear}
              onChange={(e) => setEditRegisteredYear(e.target.value)}
              required
            />
          </div>

          {/* Edit Mapel */}
          <div className="space-y-2 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-300 block">
                Mata Pelajaran yang Diampu <span className="text-slate-500 font-normal">(Opsional)</span>
              </label>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => {
                    setEditTarget(null);
                    onNavigate("/admin/subjects");
                  }}
                  className="text-[11px] text-indigo-400 hover:text-indigo-300 underline"
                >
                  Kelola Master Mapel
                </button>
              )}
            </div>
            {availableSubjects.length === 0 ? (
              <p className="text-[11px] text-amber-400/90 italic bg-amber-950/20 p-2.5 rounded-lg border border-amber-500/20">
                Belum ada mata pelajaran di Master. Daftarkan di menu <strong>Master Mata Pelajaran</strong>.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                {availableSubjects.map((s) => {
                  const isChecked = editSubjectsTaught.includes(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() =>
                        setEditSubjectsTaught((prev) =>
                          isChecked ? prev.filter((item) => item !== s) : [...prev, s]
                        )
                      }
                      className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                        isChecked
                          ? "bg-indigo-600 border-indigo-500 text-white font-medium shadow-sm"
                          : "bg-slate-900 border-slate-755 text-slate-400 hover:border-slate-600"
                      }`}
                    >
                      {isChecked ? "✓ " : "+ "}
                      {s}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Edit Kelas */}
          <div className="space-y-2 p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-300 block">
                Kelas yang Diajar <span className="text-slate-500 font-normal">(Opsional)</span>
              </label>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => {
                    setEditTarget(null);
                    onNavigate("/admin/classes");
                  }}
                  className="text-[11px] text-indigo-400 hover:text-indigo-300 underline"
                >
                  Kelola Master Kelas
                </button>
              )}
            </div>
            {availableClasses.length === 0 ? (
              <p className="text-[11px] text-amber-400/90 italic bg-amber-950/20 p-2.5 rounded-lg border border-amber-500/20">
                Belum ada rombel kelas di Master. Buat kelas di menu <strong>Manajemen Kelas</strong>.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                {availableClasses.map((c) => {
                  const isChecked = editClassesTaught.includes(c);
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() =>
                        setEditClassesTaught((prev) =>
                          isChecked ? prev.filter((item) => item !== c) : [...prev, c]
                        )
                      }
                      className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                        isChecked
                          ? "bg-indigo-600 border-indigo-500 text-white font-medium shadow-sm"
                          : "bg-slate-900 border-slate-755 text-slate-400 hover:border-slate-600"
                      }`}
                    >
                      {isChecked ? "✓ " : "+ "}
                      {c}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button type="button" variant="ghost" onClick={() => setEditTarget(null)}>
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isSubmittingEdit}
            >
              Simpan Perubahan
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Reset Password Guru ── */}
      <Modal
        isOpen={!!resetTarget}
        onClose={closeResetModal}
        title={`Reset Kata Sandi: ${resetTarget?.name || resetTarget?.username}`}
        maxWidth="sm"
      >
        {resetResult ? (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-center space-y-1.5">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
              <h4 className="text-sm font-bold text-slate-200">Kata Sandi Berhasil Direset!</h4>
            </div>

            <div className="space-y-2 bg-slate-900 p-3.5 rounded-xl border border-slate-800 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Username:</span>
                <span className="font-mono font-bold text-slate-200">{resetResult.username}</span>
              </div>
              <div className="flex justify-between items-center border-t border-slate-800 pt-2">
                <span className="text-slate-400">Kata Sandi Baru:</span>
                <div className="flex items-center gap-1.5 font-mono font-bold text-indigo-300">
                  <span>{showResetPassword ? resetResult.new_password : "••••••••••••"}</span>
                  <button
                    type="button"
                    onClick={() => setShowResetPassword(!showResetPassword)}
                    className="p-1 hover:text-indigo-400"
                  >
                    {showResetPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCopy(resetResult.new_password)}
                    className="p-1 hover:text-indigo-400"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button variant="primary" onClick={closeResetModal}>
                Selesai
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 text-xs">
            <p className="text-slate-300">
              Apakah Anda yakin ingin mereset kata sandi akun guru{" "}
              <strong className="text-white">{resetTarget?.name || resetTarget?.username}</strong>?
            </p>
            <p className="text-slate-400">
              Sistem akan membuat kata sandi acak baru yang aman. Guru akan diminta untuk mengganti kata sandi tersebut saat pertama kali login kembali.
            </p>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <Button variant="ghost" onClick={closeResetModal}>
                Batal
              </Button>
              <Button
                variant="primary"
                leftIcon={<KeyRound className="w-4 h-4" />}
                onClick={handleResetPassword}
                isLoading={isResetting}
              >
                Reset Sekarang
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Custom Confirmation MessageBox: Single Delete Teacher ── */}
      <MessageBox
        isOpen={deletingTeacherObj !== null}
        onClose={() => setDeletingTeacherObj(null)}
        type="warning"
        title="Hapus Akun Guru"
        message={
          <div>
            Apakah Anda yakin ingin menghapus guru <strong>"{deletingTeacherObj?.name || deletingTeacherObj?.username}"</strong> secara permanen?
            <p className="text-[11px] text-slate-400 mt-1">
              Akun guru ini dan penugasannya akan terhapus dari sistem.
            </p>
          </div>
        }
        confirmText="Hapus Guru"
        cancelText="Batal"
        onConfirm={handleConfirmSingleDelete}
        isLoading={deletingId !== null}
        confirmVariant="danger"
      />

      {/* ── Custom Confirmation MessageBox: Bulk Delete Teachers ── */}
      <MessageBox
        isOpen={isBulkDeleteConfirmOpen}
        onClose={() => setIsBulkDeleteConfirmOpen(false)}
        type="warning"
        title="Hapus Guru Terpilih"
        message={
          <div>
            Apakah Anda yakin ingin menghapus <strong>{selectedIds.length} guru terpilih</strong> secara permanen?
            <p className="text-[11px] text-slate-400 mt-1">
              Seluruh data dan penugasan guru terpilih akan terhapus dari sistem.
            </p>
          </div>
        }
        confirmText={`Hapus ${selectedIds.length} Guru`}
        cancelText="Batal"
        onConfirm={handleExecuteBulkDelete}
        isLoading={bulkDeleteProgress !== null}
        confirmVariant="danger"
      />
    </AppShell>
  );
}

// Batch 3 Bulk Import Remediation Verified

