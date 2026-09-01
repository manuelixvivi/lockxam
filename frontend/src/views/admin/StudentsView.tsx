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
import { studentApi } from "../../api/student";
import type { StudentAccount } from "../../api/student";
import { classApi } from "../../api/class";
import type { ClassEntity } from "../../api/class";
import { academicApi } from "../../api/academic";
import { ImportExportBar } from "../../components/ui/ImportExportBar";
import { readXlsxFile } from "../../utils/xlsx";
import { downloadStudentTemplate } from "../../utils/excelTemplates";
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
  Pencil,
  Trash2,
  AlertTriangle,
  Loader2,
  Search,
  GraduationCap,
  Download,
} from "lucide-react";
import { AddDataChoiceModal } from "../../components/ui/AddDataChoiceModal";
import { copyToClipboard } from "../../utils/clipboard";

interface StudentsViewProps {
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

function formatBirthDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function StudentsView({ onNavigate }: StudentsViewProps) {
  const { showToast } = useToast();

  // State
  const [students, setStudents] = useState<StudentAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterClass, setFilterClass] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  // Detail Modal State
  const [detailTarget, setDetailTarget] = useState<StudentAccount | null>(null);

  // Selection / Bulk delete states
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkDeleteProgress, setBulkDeleteProgress] = useState<{ current: number; total: number } | null>(null);

  // Add Student State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newNisn, setNewNisn] = useState("");
  const [newNis, setNewNis] = useState("");
  const [newBirthDate, setNewBirthDate] = useState("");
  const [newGender, setNewGender] = useState("");
  const [newClassName, setNewClassName] = useState("");
  const [newRegisteredYear, setNewRegisteredYear] = useState(new Date().getFullYear().toString());
  const [createdStudentInfo, setCreatedStudentInfo] = useState<{ username: string; default_password: string } | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState(false);
  const [isImportingXlsx, setIsImportingXlsx] = useState(false);
  const [activeYearId, setActiveYearId] = useState<number | null>(null);
  const [importErrors, setImportErrors] = useState<Array<{ row: number; field: string; value?: string; message: string }> | null>(null);

  // Edit Student State
  const [editTarget, setEditTarget] = useState<StudentAccount | null>(null);
  const [editName, setEditName] = useState("");
  const [editNisn, setEditNisn] = useState("");
  const [editNis, setEditNis] = useState("");
  const [editBirthDate, setEditBirthDate] = useState("");
  const [editGender, setEditGender] = useState("");
  const [editClassName, setEditClassName] = useState("");
  const [editRegisteredYear, setEditRegisteredYear] = useState("");
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // Reset Password Modal
  const [resetTarget, setResetTarget] = useState<StudentAccount | null>(null);
  const [resetResult, setResetResult] = useState<{ username: string; new_password: string } | null>(null);
  const [isResetting, setIsResetting] = useState(false);
  const [showResetPassword, setShowResetPassword] = useState(false);

  // Active/Delete states
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Master Classes State
  const [masterClasses, setMasterClasses] = useState<ClassEntity[]>([]);

  // Load students and master classes
  const loadStudents = useCallback(async () => {
    setIsLoading(true);
    try {
      const [data, classes, years] = await Promise.all([
        studentApi.listStudents(),
        classApi.listClasses().catch(() => []),
        academicApi.getAcademicYears().catch(() => []),
      ]);
      setStudents(data);
      setMasterClasses(classes);

      const activeYear = years.find((y: any) => y.status === "ACTIVE") || years[0];
      if (activeYear) {
        setActiveYearId(activeYear.id);
      }

      setSelectedIds([]); // Clear selection on reload
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memuat daftar siswa.", message: err?.message });
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadStudents();
  }, [loadStudents]);

  // Combined class options for Add/Edit forms
  const classFormOptions: SelectOption[] = useMemo(() => {
    const list: SelectOption[] = [
      { value: "", label: "Tanpa Kelas (Belum Diassign)" },
    ];
    masterClasses.forEach((c) => {
      list.push({ value: c.name, label: `${c.name} (${c.grade_level || "Rombel"})` });
    });
    // Add existing student classes if not already present
    students.forEach((s) => {
      if (s.class_name && !list.some((o) => o.value === s.class_name)) {
        list.push({ value: s.class_name, label: s.class_name });
      }
    });
    return list;
  }, [masterClasses, students]);

  // Combined class options for filter bar
  const filterClassOptions: SelectOption[] = useMemo(() => {
    return [
      { value: "", label: "Semua Kelas" },
      { value: "UNASSIGNED", label: "Tanpa Kelas (Belum Diassign)" },
      ...classFormOptions.filter((o) => o.value !== ""),
    ];
  }, [classFormOptions]);

  // Filtered list
  const filtered = useMemo(() => {
    return students.filter((s) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        s.username.toLowerCase().includes(q) ||
        (s.name || "").toLowerCase().includes(q) ||
        (s.nis || "").toLowerCase().includes(q) ||
        (s.nisn || "").toLowerCase().includes(q);

      const matchesClass = filterClass
        ? filterClass === "UNASSIGNED"
          ? !s.class_name || s.class_name.trim() === ""
          : s.class_name === filterClass
        : true;
      const matchesStatus =
        filterStatus === "active"
          ? s.is_active
          : filterStatus === "inactive"
          ? !s.is_active
          : true;

      return matchesSearch && matchesClass && matchesStatus;
    });
  }, [students, searchQuery, filterClass, filterStatus]);

  // Pagination State (25 per page by default)
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, filterClass, filterStatus, pageSize]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));

  const paginatedStudents = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, currentPage, pageSize]);

  // Selection handlers
  const handleToggleSelect = (publicId: string) => {
    setSelectedIds((prev) =>
      prev.includes(publicId) ? prev.filter((id) => id !== publicId) : [...prev, publicId]
    );
  };

  const handleToggleAll = () => {
    const allFilteredIds = filtered.map((s) => s.public_id);
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
  const [deletingStudentObj, setDeletingStudentObj] = useState<StudentAccount | null>(null);

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
        await studentApi.deleteStudent(publicId);
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
      title: "Hapus Siswa Selesai",
      message: `${successCount} siswa berhasil dihapus. ${failedCount > 0 ? `${failedCount} gagal.` : ""}`,
    });
    await loadStudents();
  };

  const handleDelete = (student: StudentAccount) => {
    setDeletingStudentObj(student);
  };

  const handleConfirmSingleDelete = async () => {
    if (!deletingStudentObj) return;
    setDeletingId(deletingStudentObj.public_id);
    try {
      await studentApi.deleteStudent(deletingStudentObj.public_id);
      showToast({ type: "success", title: "Akun siswa berhasil dihapus." });
      setDeletingStudentObj(null);
      await loadStudents();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal menghapus akun siswa.", message: err?.message });
    } finally {
      setDeletingId(null);
    }
  };

  // Create student
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newNisn.trim() || !newGender) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Nama, NISN, dan Jenis Kelamin wajib diisi." });
      return;
    }

    setIsCreating(true);
    try {
      const res = await studentApi.createStudent({
        name: newName.trim(),
        nisn: newNisn.trim(),
        gender: newGender,
        nis: newNis.trim() || undefined,
        birth_date: newBirthDate || undefined,
        class_name: newClassName.trim() || undefined,
        registered_year: newRegisteredYear ? parseInt(newRegisteredYear, 10) : undefined,
      });

      setCreatedStudentInfo({
        username: res.account.username,
        default_password: res.default_password,
      });

      showToast({ type: "success", title: "Akun siswa berhasil dibuat." });

      // Reset state fields
      setNewName("");
      setNewNisn("");
      setNewNis("");
      setNewBirthDate("");
      setNewGender("");
      setNewClassName("");
      setNewRegisteredYear(new Date().getFullYear().toString());
      await loadStudents();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal membuat akun siswa.", message: err?.message });
    } finally {
      setIsCreating(false);
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (student: StudentAccount) => {
    setEditTarget(student);
    setEditName(student.name || "");
    setEditNisn(student.nisn || "");
    setEditNis(student.nis || "");
    setEditBirthDate(student.birth_date || "");
    setEditGender(student.gender || "");
    setEditClassName(student.class_name || "");
    setEditRegisteredYear(student.registered_year ? student.registered_year.toString() : "");
  };

  // Update student
  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTarget) return;
    if (!editName.trim() || !editNisn.trim() || !editGender) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Nama, NISN, dan Jenis Kelamin wajib diisi." });
      return;
    }

    setIsSubmittingEdit(true);
    try {
      await studentApi.updateStudent(editTarget.public_id, {
        name: editName.trim(),
        nisn: editNisn.trim(),
        gender: editGender,
        nis: editNis.trim() ? editNis.trim() : null,
        birth_date: editBirthDate ? editBirthDate : null,
        class_name: editClassName.trim() ? editClassName.trim() : null,
        registered_year: editRegisteredYear ? parseInt(editRegisteredYear, 10) : null,
      });
      showToast({ type: "success", title: "Data siswa berhasil diperbarui." });
      setEditTarget(null);
      await loadStudents();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal memperbarui data siswa.", message: err?.message });
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  // Toggle active
  const handleToggleActive = async (student: StudentAccount) => {
    setTogglingId(student.public_id);
    try {
      await studentApi.toggleActive(student.public_id);
      const action = student.is_active ? "dinonaktifkan" : "diaktifkan";
      showToast({ type: "success", title: `Akun '${student.username}' berhasil ${action}.` });
      await loadStudents();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal mengubah status akun.", message: err?.message });
    } finally {
      setTogglingId(null);
    }
  };

  // Clear student device session
  const [clearingSessionId, setClearingSessionId] = useState<string | null>(null);

  const handleClearSessions = async (student: StudentAccount) => {
    setClearingSessionId(student.public_id);
    try {
      const res = await studentApi.clearSessions(student.public_id);
      showToast({
        type: "success",
        title: "Riwayat Device Berhasil Dihapus",
        message: res.message,
      });
      await loadStudents();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal menghapus riwayat device.", message: err?.message });
    } finally {
      setClearingSessionId(null);
    }
  };

  // Reset password
  const handleResetPassword = async () => {
    if (!resetTarget) return;
    setIsResetting(true);
    try {
      const result = await studentApi.resetPassword(resetTarget.public_id);
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
  const totalStudents = students.length;
  const activeStudents = students.filter((s) => s.is_active).length;
  const inactiveStudents = students.filter((s) => !s.is_active).length;

  const genderOptions: SelectOption[] = [
    { value: "", label: "-- Pilih Jenis Kelamin --" },
    { value: "L", label: "Laki-laki (L)" },
    { value: "P", label: "Perempuan (P)" },
  ];

  return (
    <AppShell activeHref="/admin/students" onNavigate={onNavigate}>
      <Breadcrumb
        items={[
          { label: "School Admin", href: "/admin/profile" },
          { label: "Direktori Siswa" },
        ]}
      />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <GraduationCap className="w-5 h-5" />
            </div>
            Direktori Siswa
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Kelola data peserta ujian — kelas, NISN, status akun, dan reset sandi siswa.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="ghost"
            size="md"
            leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
            onClick={() => {
              const exportBar = document.getElementById("export-siswa-btn");
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
            Tambah Siswa
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
              <p className="text-[11px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Siswa</p>
              <p className="text-xl sm:text-2xl font-black text-slate-100 mt-0.5">{totalStudents}</p>
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
              <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Siswa Aktif</p>
              <p className="text-lg sm:text-2xl font-black text-emerald-400 mt-0.5">{activeStudents}</p>
            </div>
          </div>
          <span className="text-[9px] sm:text-[10px] font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-emerald-500/20">
            {totalStudents > 0 ? Math.round((activeStudents / totalStudents) * 100) : 0}%
          </span>
        </div>

        <div className="glass-panel p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-2 col-span-1">
          <div className="flex items-center gap-2 sm:gap-3.5">
            <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0">
              <XCircle className="w-4 h-4 sm:w-5 sm:h-5 text-rose-400" />
            </div>
            <div>
              <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Nonaktif</p>
              <p className="text-lg sm:text-2xl font-black text-rose-400 mt-0.5">{inactiveStudents}</p>
            </div>
          </div>
          <span className="text-[9px] sm:text-[10px] font-semibold text-rose-400 bg-rose-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-rose-500/20">
            {inactiveStudents} Akun
          </span>
        </div>
      </div>

      {/* Main Panel */}
      <div className="glass-panel p-6 space-y-4">
        {/* Filter & Toolbar */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 pb-3 border-b border-slate-855">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="flex-1">
              <Input
                placeholder="Cari nama siswa, NISN, NIS, atau username..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="w-4 h-4 text-slate-400" />}
              />
            </div>
            <Button
              variant="ghost"
              size="md"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadStudents}
              isLoading={isLoading}
              title="Muat ulang data"
              className="shrink-0"
            >
              Refresh
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Filter Kelas */}
            <div className="w-56">
              <Select
                options={filterClassOptions}
                value={filterClass}
                onChange={(e) => setFilterClass(e.target.value)}
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

        {/* Hidden ImportExportBar helper for programmatic export & template */}
        <div className="hidden">
          <ImportExportBar<StudentAccount>
            exportData={filtered}
            exportColumns={[
              { label: "Nama Lengkap", key: "name" },
              { label: "NISN", key: "nisn" },
              { label: "NIS", key: "nis" },
              { label: "Kelas", key: "class_name" },
              { label: "Tahun Terdaftar", key: "registered_year" },
              { label: "Jenis Kelamin", key: "gender" },
              { label: "Tanggal Lahir", key: "birth_date" },
              { label: "Username", key: "username" },
              { label: "Status", key: "is_active" },
              { label: "Login Terakhir", key: "last_login" },
              { label: "Terdaftar", key: "created_at" },
            ]}
            exportFilename="daftar-siswa"
            sheetName="Siswa"
            templateHeaders={["Nama Lengkap", "NISN", "Jenis Kelamin (L/P)", "NIS", "Tanggal Lahir (YYYY-MM-DD)", "Kelas", "Tahun Terdaftar"]}
            templateSamples={[
              {
                "Nama Lengkap": "Ahmad Dani",
                NISN: "0051234567",
                "Jenis Kelamin (L/P)": "L",
                NIS: "22001024",
                "Tanggal Lahir (YYYY-MM-DD)": "2008-05-12",
                Kelas: masterClasses.length > 0 ? masterClasses[0].name : "",
                "Tahun Terdaftar": "2024",
              },
            ]}
            templateFilename="template-import-siswa"
            onImportRow={async () => null}
            onImportDone={loadStudents}
          />
        </div>

        {/* Selection Alert Banner */}
        {selectedIds.length > 0 && (
          <div className="flex items-center justify-between p-3 rounded-xl bg-rose-950/30 border border-rose-500/30 text-xs animate-fade-in">
            <div className="flex items-center gap-2 text-rose-300 font-semibold">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>Terpilih {selectedIds.length} siswa</span>
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
                <span>Menghapus data siswa terpilih…</span>
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
              {searchQuery || filterClass || filterStatus
                ? "Tidak ada siswa yang memenuhi kriteria pencarian/filter."
                : "Belum ada akun siswa. Klik 'Tambah Siswa' untuk membuat akun pertama."}
            </p>
          ) : (
            paginatedStudents.map((item) => (
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
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900 mt-1 shrink-0"
                    checked={selectedIds.includes(item.public_id)}
                    onChange={() => handleToggleSelect(item.public_id)}
                  />
                  <div className="w-10 h-10 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-sm font-bold text-indigo-300 shrink-0 mt-0.5">
                    {(item.name || item.username).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-200 truncate">
                      {item.name || "—"}
                    </p>
                    <p className="text-xs font-mono text-slate-400 mt-0.5 truncate">
                      {item.username}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-slate-500 font-mono">NISN: {item.nisn || "—"}</span>
                      {item.class_name ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-500/20 font-medium">
                          {item.class_name}
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/60 text-slate-400 border border-slate-700/40 italic">
                          Tanpa Kelas
                        </span>
                      )}
                    </div>
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
          <Table<StudentAccount>
            keyExtractor={(item) => item.public_id}
            isLoading={isLoading}
            emptyMessage={
              searchQuery || filterClass || filterStatus
                ? "Tidak ada siswa yang memenuhi filter."
                : "Belum ada siswa terdaftar. Klik 'Tambah Siswa' untuk mendaftarkan akun."
            }
            data={paginatedStudents}
            columns={[
              {
                key: "select",
                header: (
                  <input
                    type="checkbox"
                    className="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-900 cursor-pointer"
                    checked={filtered.length > 0 && filtered.every((s) => selectedIds.includes(s.public_id))}
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
                key: "student_info",
                header: "Nama Siswa & NISN",
                render: (item) => (
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center text-xs font-bold text-indigo-300 shrink-0">
                      {(item.name || item.username).charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-slate-100 truncate">{item.name || "—"}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] font-mono text-slate-400">NISN: {item.nisn || "—"}</span>
                        {item.class_name ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-500/20 font-medium">
                            {item.class_name}
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/60 text-slate-400 border border-slate-700/40 italic">
                            Tanpa Kelas
                          </span>
                        )}
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

        {/* ── Pagination Bar (rendered on both mobile & desktop) ── */}
        {filtered.length > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-xs shadow-md">
            <div className="flex flex-wrap items-center gap-3 text-slate-400">
              <span>
                Menampilkan{" "}
                <strong className="text-slate-200">
                  {(currentPage - 1) * pageSize + 1} - {Math.min(currentPage * pageSize, filtered.length)}
                </strong>{" "}
                dari <strong className="text-slate-200">{filtered.length}</strong> siswa (Total: {students.length})
              </span>

              <div className="flex items-center gap-1.5 sm:border-l sm:border-slate-800 sm:pl-3">
                <span className="text-slate-400">Per Halaman:</span>
                <select
                  className="bg-slate-950 border border-slate-700/60 rounded-lg px-2.5 py-1 text-slate-200 font-mono text-xs focus:outline-none focus:border-indigo-500 cursor-pointer"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(parseInt(e.target.value, 10));
                    setCurrentPage(1);
                  }}
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={500}>500</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                Sebelumnya
              </Button>

              <span className="px-3 py-1 text-indigo-300 font-mono font-bold text-xs bg-indigo-950/80 border border-indigo-500/30 rounded-lg shadow-inner">
                Halaman {currentPage} / {totalPages}
              </span>

              <Button
                variant="ghost"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                Selanjutnya
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* ── Modal: Choice Add Data ── */}
      <AddDataChoiceModal
        isOpen={isAddChoiceOpen}
        onClose={() => setIsAddChoiceOpen(false)}
        entityName="Siswa"
        onSelectManual={() => {
          setCreatedStudentInfo(null);
          setShowAddModal(true);
        }}
        onDownloadTemplate={downloadStudentTemplate}
        onImportXlsx={async (file) => {
          setIsImportingXlsx(true);
          setImportErrors(null);
          try {
            const rows = await readXlsxFile(file);
            if (rows.length === 0) {
              showToast({ type: "error", title: "File Kosong", message: "File XLSX tidak berisi data." });
              return;
            }

            if (!activeYearId) {
              showToast({ type: "error", title: "Tahun Ajaran Aktif Tidak Ditemukan", message: "Harap buat tahun ajaran aktif terlebih dahulu." });
              return;
            }

            const payloadRows = rows.map((row) => {
              const name = String(row["Nama Lengkap"] || "").trim();
              const nisn = String(row["NISN"] || "").trim().replace(/\D/g, "");
              const rawGender = String(row["Jenis Kelamin (L/P)"] || "").trim().toUpperCase();
              const gender = rawGender === "L" || rawGender === "LAKI-LAKI" ? "L" : rawGender === "P" || rawGender === "PEREMPUAN" ? "P" : "";
              const nis = String(row["NIS"] || "").trim().replace(/\D/g, "") || undefined;
              const rawBirthDate = String(row["Tanggal Lahir (YYYY-MM-DD)"] || "").trim();
              const birthDate = /^\d{4}-\d{2}-\d{2}$/.test(rawBirthDate) ? rawBirthDate : undefined;
              const rawClassName = String(row["Kelas"] || "").trim();
              const rawRegYear = String(row["Tahun Terdaftar"] || "").trim();
              const regYear = rawRegYear ? parseInt(rawRegYear, 10) : undefined;

              return {
                name: name || undefined,
                nisn: nisn || undefined,
                gender: gender || undefined,
                nis: nis || undefined,
                birth_date: birthDate || undefined,
                class_name: rawClassName || undefined,
                registered_year: regYear || undefined,
              };
            });

            const result = await studentApi.importStudents({
              academic_year_id: activeYearId,
              rows: payloadRows,
            });

            if (result.status === "success") {
              const skippedCount = result.skipped?.length || 0;
              let msg = `Berhasil mengimpor ${result.imported_count} siswa.`;
              if (skippedCount > 0) {
                msg = `Berhasil mengimpor ${result.imported_count} siswa, ${skippedCount} siswa dilewati karena sudah ada di database.`;
              }
              showToast({
                type: "success",
                title: "Impor Berhasil",
                message: msg,
              });
              await loadStudents();
            } else {
              setImportErrors(result.errors || []);
            }
          } catch (err: any) {
            const serverErrors = err.response?.data?.errors;
            const serverMsg = err.response?.data?.message;

            if (serverErrors && Array.isArray(serverErrors)) {
              setImportErrors(serverErrors);
              showToast({
                type: "error",
                title: "Impor Dibatalkan",
                message: "Tidak ada data siswa yang disimpan. Silakan periksa kesalahan validasi.",
              });
            } else {
              showToast({
                type: "error",
                title: "Impor Gagal",
                message: serverMsg || err.message || "Terjadi kesalahan saat memproses impor data.",
              });
            }
          } finally {
            setIsImportingXlsx(false);
          }
        }}
        isLoadingImport={isImportingXlsx}
      />

      {/* ── Modal: Detail Siswa ── */}
      <Modal
        isOpen={!!detailTarget}
        onClose={() => setDetailTarget(null)}
        title="Profil Siswa"
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

            {/* Data Akademik Card */}
            <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <GraduationCap className="w-4 h-4 text-indigo-400" />
                Data Akademik & Siswa
              </span>
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="space-y-1">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">NISN</span>
                  <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-slate-200">
                    <span>{detailTarget.nisn || "—"}</span>
                    {detailTarget.nisn && (
                      <button
                        type="button"
                        onClick={() => handleCopy(detailTarget.nisn!)}
                        className="text-slate-500 hover:text-indigo-400 p-0.5"
                        title="Salin NISN"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">NIS</span>
                  <p className="font-mono text-xs font-bold text-slate-200">{detailTarget.nis || "—"}</p>
                </div>

                <div className="space-y-1 pt-2 border-t border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Kelas</span>
                  <div>
                    {detailTarget.class_name ? (
                      <Badge variant="indigo" size="sm">{detailTarget.class_name}</Badge>
                    ) : (
                      <span className="text-xs text-slate-500 italic">Belum diassign</span>
                    )}
                  </div>
                </div>

                <div className="space-y-1 pt-2 border-t border-slate-800">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Tahun Terdaftar</span>
                  <p className="font-mono text-xs font-bold text-slate-200">{detailTarget.registered_year || "—"}</p>
                </div>
              </div>
            </div>

            {/* Data Pribadi & Akun Card */}
            <div className="grid grid-cols-2 gap-3 p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80">
              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Jenis Kelamin</span>
                <p className="text-xs font-bold text-slate-200">
                  {detailTarget.gender === "L" ? "Laki-laki (L)" : detailTarget.gender === "P" ? "Perempuan (P)" : "—"}
                </p>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Tanggal Lahir</span>
                <p className="text-xs font-bold text-slate-200">{formatBirthDate(detailTarget.birth_date)}</p>
              </div>

              <div className="space-y-1 col-span-2 pt-2 border-t border-slate-800">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Login Terakhir</span>
                <p className="font-mono text-xs text-slate-300">{formatDate(detailTarget.last_login)}</p>
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
                    const s = detailTarget;
                    setDetailTarget(null);
                    handleOpenEdit(s);
                  }}
                >
                  Edit Data
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<KeyRound className="w-3.5 h-3.5 text-amber-400" />}
                  onClick={() => {
                    const s = detailTarget;
                    setDetailTarget(null);
                    setResetTarget(s);
                    setResetResult(null);
                  }}
                >
                  Reset Sandi
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-amber-400 hover:text-amber-300 border-amber-500/30"
                  leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${clearingSessionId === detailTarget.public_id ? "animate-spin" : ""}`} />}
                  onClick={() => {
                    const s = detailTarget;
                    handleClearSessions(s);
                  }}
                >
                  Reset Sesi Device
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

      {/* ── Modal: Tambah Siswa Baru ── */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false);
          setCreatedStudentInfo(null);
        }}
        title={createdStudentInfo ? "Akun Siswa Berhasil Dibuat" : "Tambah Akun Siswa Baru"}
        maxWidth="lg"
      >
        {createdStudentInfo ? (
          <div className="space-y-5">
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-center space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
              <h4 className="text-base font-black text-slate-100">Pendaftaran Siswa Sukses!</h4>
              <p className="text-xs text-slate-400">
                Berikan informasi akun berikut kepada siswa yang bersangkutan untuk login pada aplikasi CBT / ujian.
              </p>
            </div>

            <div className="space-y-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">Username / Login:</span>
                <div className="flex items-center gap-2 font-mono font-bold text-slate-200">
                  <span>{createdStudentInfo.username}</span>
                  <button
                    onClick={() => handleCopy(createdStudentInfo.username)}
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
                  <span>{createdStudentInfo.default_password}</span>
                  <button
                    onClick={() => handleCopy(createdStudentInfo.default_password)}
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
                  setCreatedStudentInfo(null);
                }}
              >
                Selesai & Tutup
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Nama Lengkap Siswa (Wajib)"
                placeholder="Contoh: Ahmad Dani Prasetyo"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
              />
              <Input
                label="NISN (Nomor Induk Siswa Nasional)"
                placeholder="Contoh: 0051234567"
                value={newNisn}
                onChange={(e) => setNewNisn(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="NIS (Nomor Induk Sekolah - Opsional)"
                placeholder="Contoh: 22001024"
                value={newNis}
                onChange={(e) => setNewNis(e.target.value)}
              />
              <Select
                label="Jenis Kelamin"
                options={genderOptions}
                value={newGender}
                onChange={(e) => setNewGender(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Input
                label="Tanggal Lahir"
                type="date"
                value={newBirthDate}
                onChange={(e) => setNewBirthDate(e.target.value)}
              />
              <Select
                label="Kelas Rombel (Opsional)"
                options={classFormOptions}
                value={newClassName}
                onChange={(e) => setNewClassName(e.target.value)}
                helperText={masterClasses.length === 0 ? "Belum ada rombel di Master Kelas. Siswa otomatis Tanpa Kelas." : "Bisa dikosongkan sebelum ditarik ke struktur kelas."}
              />
              <Input
                label="Tahun Terdaftar / Masuk"
                type="number"
                placeholder="Contoh: 2024"
                value={newRegisteredYear}
                onChange={(e) => setNewRegisteredYear(e.target.value)}
              />
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
                Daftarkan Siswa
              </Button>
            </div>
          </form>
        )}
      </Modal>

      {/* ── Modal: Edit Siswa ── */}
      <Modal
        isOpen={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={`Edit Data Siswa: ${editTarget?.name || editTarget?.username}`}
        maxWidth="lg"
      >
        <form onSubmit={handleUpdate} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Nama Lengkap"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              required
            />
            <Input
              label="NISN"
              value={editNisn}
              onChange={(e) => setEditNisn(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="NIS"
              value={editNis}
              onChange={(e) => setEditNis(e.target.value)}
            />
            <Select
              label="Jenis Kelamin"
              options={genderOptions}
              value={editGender}
              onChange={(e) => setEditGender(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Input
              label="Tanggal Lahir"
              type="date"
              value={editBirthDate}
              onChange={(e) => setEditBirthDate(e.target.value)}
            />
            <Select
              label="Kelas Rombel (Opsional)"
              options={classFormOptions}
              value={editClassName}
              onChange={(e) => setEditClassName(e.target.value)}
              helperText="Pilih kelas atau 'Tanpa Kelas' jika ingin melepaskan siswa dari kelas."
            />
            <Input
              label="Tahun Terdaftar"
              type="number"
              value={editRegisteredYear}
              onChange={(e) => setEditRegisteredYear(e.target.value)}
            />
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

      {/* ── Modal: Reset Password Siswa ── */}
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
              Apakah Anda yakin ingin mereset kata sandi akun siswa{" "}
              <strong className="text-white">{resetTarget?.name || resetTarget?.username}</strong>?
            </p>
            <p className="text-slate-400">
              Sistem akan membuat kata sandi acak baru yang aman untuk siswa bersangkutan.
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

      {/* ── Custom Confirmation MessageBox: Single Delete Student ── */}
      <MessageBox
        isOpen={deletingStudentObj !== null}
        onClose={() => setDeletingStudentObj(null)}
        type="warning"
        title="Hapus Akun Siswa"
        message={
          <div>
            Apakah Anda yakin ingin menghapus siswa <strong>"{deletingStudentObj?.name || deletingStudentObj?.username}"</strong> secara permanen?
            <p className="text-[11px] text-slate-400 mt-1">
              Seluruh riwayat ujian, nilai, dan sesi pengerjaan siswa bersangkutan akan terhapus.
            </p>
          </div>
        }
        confirmText="Hapus Siswa"
        cancelText="Batal"
        onConfirm={handleConfirmSingleDelete}
        isLoading={deletingId !== null}
        confirmVariant="danger"
      />

      {/* ── Custom Confirmation MessageBox: Bulk Delete Students ── */}
      <MessageBox
        isOpen={isBulkDeleteConfirmOpen}
        onClose={() => setIsBulkDeleteConfirmOpen(false)}
        type="warning"
        title="Hapus Siswa Terpilih"
        message={
          <div>
            Apakah Anda yakin ingin menghapus <strong>{selectedIds.length} siswa terpilih</strong> secara permanen?
            <p className="text-[11px] text-slate-400 mt-1">
              Seluruh data dan riwayat ujian siswa terpilih akan terhapus dari sistem.
            </p>
          </div>
        }
        confirmText={`Hapus ${selectedIds.length} Siswa`}
        cancelText="Batal"
        onConfirm={handleExecuteBulkDelete}
        isLoading={bulkDeleteProgress !== null}
        confirmVariant="danger"
      />
      {/* ── Modal: Loading Impor Siswa ── */}
      <Modal
        isOpen={isImportingXlsx}
        onClose={() => {}}
        title="Mengimpor Data Siswa"
        maxWidth="sm"
      >
        <div className="flex flex-col items-center justify-center p-8 space-y-4 text-center">
          <Loader2 className="w-10 h-10 animate-spin text-indigo-400" />
          <h4 className="text-sm font-bold text-slate-200">Sedang memproses file Excel...</h4>
          <p className="text-xs text-slate-400">
            Harap tunggu sebentar, sistem sedang melakukan validasi dan mengimpor data siswa ke server.
          </p>
        </div>
      </Modal>

      {/* ── Modal: Kesalahan Validasi Impor Siswa ── */}
      <Modal
        isOpen={importErrors !== null}
        onClose={() => setImportErrors(null)}
        title="Impor Dibatalkan — Terdapat Kesalahan Validasi"
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs">
          <div className="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 font-medium">
            Tidak ada data siswa yang disimpan ke database karena terdapat kesalahan pada file Excel yang Anda unggah.
          </div>
          <div className="max-h-60 overflow-y-auto space-y-2.5 pr-1">
            {importErrors?.map((err, idx) => (
              <div key={idx} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                <div className="px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 font-bold shrink-0">
                  Baris {err.row}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-200">
                    Kolom/Field: <span className="font-mono text-indigo-400">{err.field}</span>
                  </p>
                  {err.value && (
                    <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                      Nilai Input: <span className="italic">"{err.value}"</span>
                    </p>
                  )}
                  <p className="text-[11px] text-rose-300 mt-1 font-medium">{err.message}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-end pt-2">
            <Button variant="primary" onClick={() => setImportErrors(null)}>
              Tutup
            </Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
};
