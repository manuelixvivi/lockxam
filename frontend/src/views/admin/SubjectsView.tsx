import React, { useState, useEffect, useMemo } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Table } from "../../components/ui/Table";
import type { Column } from "../../components/ui/Table";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { subjectApi } from "../../api/subject";
import type { Subject, TeacherCandidate } from "../../api/subject";
import { teacherApi } from "../../api/teacher";
import type { TeacherAccount } from "../../api/teacher";
import { AddDataChoiceModal } from "../../components/ui/AddDataChoiceModal";
import { readXlsxFile, exportToXlsx } from "../../utils/xlsx";
import { downloadSubjectTemplate } from "../../utils/excelTemplates";
import {
  BookOpen,
  Plus,
  Search,
  RefreshCw,
  Edit2,
  Trash2,
  CheckCircle,
  XCircle,
  Users,
  Sparkles,
  AlertCircle,
  GraduationCap,
  Download,
} from "lucide-react";

interface SubjectsViewProps {
  onNavigate?: (path: string) => void;
}

export const SubjectsView: React.FC<SubjectsViewProps> = ({ onNavigate }) => {
  const { showToast } = useToast();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [teachers, setTeachers] = useState<TeacherAccount[]>([]);
  const [qualifiedCounts, setQualifiedCounts] = useState<Record<number, number>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Modal: Create / Edit Subject
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState<boolean>(false);
  const [isImportingXlsx, setIsImportingXlsx] = useState<boolean>(false);
  const [selectedSubjectIds, setSelectedSubjectIds] = useState<number[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState<boolean>(false);
  const [isBulkDeactivating, setIsBulkDeactivating] = useState<boolean>(false);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [formCode, setFormCode] = useState<string>("");
  const [formName, setFormName] = useState<string>("");
  const [formDescription, setFormDescription] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Modal: Manage Teacher Competencies
  const [competencySubject, setCompetencySubject] = useState<Subject | null>(null);
  const [qualifiedTeachers, setQualifiedTeachers] = useState<TeacherCandidate[]>([]);
  const [loadingCompetencies, setLoadingCompetencies] = useState<boolean>(false);
  const [teacherSearch, setTeacherSearch] = useState<string>("");
  const [togglingTeacherId, setTogglingTeacherId] = useState<number | null>(null);

  // Delete target
  const [deletingSubject, setDeletingSubject] = useState<Subject | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Load Data
  const loadData = async () => {
    setIsLoading(true);
    try {
      const [subjectsData, teachersData] = await Promise.all([
        subjectApi.listSubjects(),
        teacherApi.listTeachers(),
      ]);
      setSubjects(subjectsData);
      setTeachers(teachersData);

      // Load qualified teacher counts for each subject
      const counts: Record<number, number> = {};
      await Promise.all(
        subjectsData.map(async (subj) => {
          try {
            const qualified = await subjectApi.listQualifiedTeachers(subj.id);
            counts[subj.id] = qualified.length;
          } catch {
            counts[subj.id] = 0;
          }
        })
      );
      setQualifiedCounts(counts);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Data",
        message: err?.message || "Terjadi kesalahan saat memuat mata pelajaran.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Filtered subjects
  const filteredSubjects = useMemo(() => {
    return subjects.filter((s) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        s.code.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        (s.description || "").toLowerCase().includes(q);

      const matchesStatus =
        statusFilter === "active"
          ? s.is_active
          : statusFilter === "inactive"
          ? !s.is_active
          : true;

      return matchesSearch && matchesStatus;
    });
  }, [subjects, searchQuery, statusFilter]);

  // Check if all selected items are inactive for smart bulk button toggle
  const allSelectedAreInactive = useMemo(() => {
    if (selectedSubjectIds.length === 0) return false;
    const selectedSubs = subjects.filter((s) => selectedSubjectIds.includes(s.id));
    return selectedSubs.length > 0 && selectedSubs.every((s) => !s.is_active);
  }, [selectedSubjectIds, subjects]);

  // Handle Open Create
  const handleOpenCreate = () => {
    setEditingSubject(null);
    setFormCode("");
    setFormName("");
    setFormDescription("");
    setIsModalOpen(true);
  };

  // Handle Open Edit
  const handleOpenEdit = (subject: Subject) => {
    setEditingSubject(subject);
    setFormCode(subject.code);
    setFormName(subject.name);
    setFormDescription(subject.description || "");
    setIsModalOpen(true);
  };

  // Handle Submit Form
  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formCode.trim() || !formName.trim()) {
      showToast({
        type: "warning",
        title: "Validasi Gagal",
        message: "Kode dan Nama Mata Pelajaran wajib diisi.",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingSubject) {
        await subjectApi.updateSubject(editingSubject.public_id, {
          code: formCode.trim().toUpperCase(),
          name: formName.trim(),
          description: formDescription.trim() || null,
          is_active: editingSubject.is_active,
        });
        showToast({
          type: "success",
          title: "Berhasil Diperbarui",
          message: `Mata pelajaran '${formName}' berhasil disimpan.`,
        });
      } else {
        await subjectApi.createSubject({
          code: formCode.trim().toUpperCase(),
          name: formName.trim(),
          description: formDescription.trim() || null,
        });
        showToast({
          type: "success",
          title: "Berhasil Dibuat",
          message: `Mata pelajaran '${formName}' berhasil didaftarkan.`,
        });
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menyimpan",
        message: err?.message || "Terjadi kesalahan saat menyimpan mata pelajaran.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Toggle Active
  const handleToggleActive = async (subject: Subject) => {
    const nextActiveState = !subject.is_active;

    // Optimistic UI state update so item stays in table and badge updates instantly
    setSubjects((prev) =>
      prev.map((s) => (s.id === subject.id ? { ...s, is_active: nextActiveState } : s))
    );

    try {
      await subjectApi.updateSubject(subject.public_id, {
        code: subject.code,
        name: subject.name,
        description: subject.description,
        is_active: nextActiveState,
      });
      showToast({
        type: "success",
        title: nextActiveState ? "Mapel Diaktifkan" : "Mapel Dinonaktifkan",
        message: `Status '${subject.name}' diubah menjadi ${nextActiveState ? "Aktif" : "Nonaktif"}.`,
      });
      await loadData();
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengubah Status",
        message: err?.message || "Terjadi kesalahan.",
      });
      await loadData();
    }
  };

  // Handle Delete Subject
  const handleDeleteConfirm = async () => {
    if (!deletingSubject) return;
    setIsDeleting(true);
    try {
      await subjectApi.deleteSubject(deletingSubject.public_id);
      showToast({
        type: "success",
        title: "Berhasil Dihapus",
        message: `Mata pelajaran '${deletingSubject.name}' telah dihapus.`,
      });
      setDeletingSubject(null);
      await loadData();
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menghapus",
        message: err?.message || "Mata pelajaran tidak dapat dihapus.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Handle Open Manage Assignment Modal
  const handleOpenCompetencyModal = async (subject: Subject) => {
    setCompetencySubject(subject);
    setTeacherSearch("");
    setLoadingCompetencies(true);
    try {
      const qualified = await subjectApi.listQualifiedTeachers(subject.id);
      setQualifiedTeachers(qualified);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Guru Pengampu",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setLoadingCompetencies(false);
    }
  };

  // Toggle Single Teacher Assignment
  const handleToggleCompetency = async (teacher: TeacherAccount, isCurrentlyQualified: boolean) => {
    if (!competencySubject) return;
    setTogglingTeacherId(teacher.id);

    try {
      if (isCurrentlyQualified) {
        // Unassign
        await subjectApi.unassignTeacherCompetency(competencySubject.id, teacher.id);
        setQualifiedTeachers((prev) => prev.filter((t) => t.teacher_id !== teacher.id));
        setQualifiedCounts((prev) => ({
          ...prev,
          [competencySubject.id]: Math.max(0, (prev[competencySubject.id] || 1) - 1),
        }));
        showToast({
          type: "success",
          title: "Penugasan Dicabut",
          message: `Penugasan mengampu ${competencySubject.name} dicabut dari ${teacher.name || teacher.username}.`,
        });
      } else {
        // Assign
        await subjectApi.assignTeacherCompetency(competencySubject.id, teacher.id);
        setQualifiedTeachers((prev) => [
          ...prev,
          {
            teacher_id: teacher.id,
            public_id: teacher.public_id,
            name: teacher.name || teacher.username,
            username: teacher.username,
            nip: teacher.nip,
            is_active: teacher.is_active,
            status: "ACTIVE",
          },
        ]);
        setQualifiedCounts((prev) => ({
          ...prev,
          [competencySubject.id]: (prev[competencySubject.id] || 0) + 1,
        }));
        showToast({
          type: "success",
          title: "Guru Berhasil Ditugaskan",
          message: `${teacher.name || teacher.username} berhasil ditugaskan mengampu mapel ${competencySubject.name}.`,
        });
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Mengubah Penugasan",
        message: err?.message || "Terjadi kesalahan saat memproses penugasan guru.",
      });
    } finally {
      setTogglingTeacherId(null);
    }
  };

  // Filtered teacher candidates in modal
  const filteredTeacherList = useMemo(() => {
    return teachers.filter((t) => {
      const q = teacherSearch.toLowerCase();
      return (
        (t.name || "").toLowerCase().includes(q) ||
        t.username.toLowerCase().includes(q) ||
        (t.nip || "").toLowerCase().includes(q)
      );
    });
  }, [teachers, teacherSearch]);

  // Columns definition for table
  const columns: Column<Subject>[] = [
    {
      key: "select",
      header: (
        <input
          type="checkbox"
          className="rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-0 cursor-pointer"
          checked={selectedSubjectIds.length > 0 && selectedSubjectIds.length === filteredSubjects.length}
          onChange={() => {
            if (selectedSubjectIds.length === filteredSubjects.length) {
              setSelectedSubjectIds([]);
            } else {
              setSelectedSubjectIds(filteredSubjects.map((s) => s.id));
            }
          }}
        />
      ),
      width: "40px",
      render: (item) => (
        <input
          type="checkbox"
          className="rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-0 cursor-pointer"
          checked={selectedSubjectIds.includes(item.id)}
          onChange={() => {
            setSelectedSubjectIds((prev) =>
              prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]
            );
          }}
        />
      ),
    },
    {
      key: "code",
      header: "Kode Mapel",
      width: "140px",
      render: (item) => (
        <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-950/60 border border-indigo-500/30 px-2.5 py-1 rounded-lg">
          {item.code}
        </span>
      ),
    },
    {
      key: "name",
      header: "Nama Mata Pelajaran",
      render: (item) => (
        <div className="min-w-0">
          <div className="text-sm font-bold text-slate-100">{item.name}</div>
          {item.description && (
            <div className="text-xs text-slate-400 mt-0.5 truncate max-w-md">
              {item.description}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "teachers",
      header: "Guru Pengampu",
      width: "180px",
      render: (item) => {
        const count = qualifiedCounts[item.id] || 0;
        return (
          <button
            onClick={() => handleOpenCompetencyModal(item)}
            className="flex items-center gap-2 group text-left hover:opacity-90 transition-opacity"
            title="Klik untuk mengelola penugasan guru mapel"
          >
            <div className="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-300 group-hover:bg-indigo-500/25 transition-colors shrink-0">
              <Users className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="text-xs font-bold text-slate-200 block group-hover:text-indigo-300">
                {count} Guru
              </span>
              <span className="text-[10px] text-indigo-400 font-medium underline">
                Tugaskan Guru
              </span>
            </div>
          </button>
        );
      },
    },
    {
      key: "status",
      header: "Status",
      width: "120px",
      render: (item) => (
        <Badge variant={item.is_active ? "emerald" : "crimson"}>
          {item.is_active ? "Aktif" : "Nonaktif"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "Aksi",
      width: "180px",
      render: (item) => (
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleOpenEdit(item)}
            title="Edit Mata Pelajaran"
            className="px-2"
          >
            <Edit2 className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-300" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleToggleActive(item)}
            title={item.is_active ? "Nonaktifkan Mata Pelajaran" : "Aktifkan Mata Pelajaran"}
            className="px-2"
          >
            {item.is_active ? (
              <XCircle className="w-3.5 h-3.5 text-amber-400" />
            ) : (
              <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDeletingSubject(item)}
            title="Hapus Mata Pelajaran"
            className="px-2 hover:bg-rose-500/20"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
          </Button>
        </div>
      ),
    },
  ];

  // Total metrics
  const activeCount = subjects.filter((s) => s.is_active).length;
  const inactiveCount = subjects.filter((s) => !s.is_active).length;

  return (
    <AppShell activeHref="/admin/subjects" onNavigate={onNavigate}>
      <Breadcrumb
        items={[
          { label: "School Admin", href: "/admin/dashboard" },
          { label: "Master Mata Pelajaran" },
        ]}
      />

      <div className="space-y-6">
        {/* Header & Title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
              <BookOpen className="w-6 h-6 text-indigo-400 shrink-0" />
              Master Mata Pelajaran
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Kelola kurikulum mata pelajaran sekolah dan tetapkan sertifikasi kompetensi guru pengampu.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="ghost"
              size="md"
              leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
              onClick={() => {
                const rows = filteredSubjects.map((s) => ({
                  "Kode Mapel": s.code,
                  "Nama Mata Pelajaran": s.name,
                  "Deskripsi": s.description || "",
                  "Status": s.is_active ? "Aktif" : "Nonaktif",
                }));
                exportToXlsx(rows, "daftar-mata-pelajaran", "Mata Pelajaran");
              }}
            >
              Ekspor Excel
            </Button>
            <Button
              variant="primary"
              size="md"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => setIsAddChoiceOpen(true)}
            >
              Tambah Mapel
            </Button>
          </div>
        </div>

        {/* Bento Box Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400">Total Mapel</p>
              <p className="text-xl font-black text-slate-100">{subjects.length}</p>
            </div>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0">
              <CheckCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400">Mapel Aktif</p>
              <p className="text-xl font-black text-emerald-400">{activeCount}</p>
            </div>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shrink-0">
              <XCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400">Nonaktif</p>
              <p className="text-xl font-black text-amber-400">{inactiveCount}</p>
            </div>
          </div>

          <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/25 flex items-center justify-center text-purple-400 shrink-0">
              <GraduationCap className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400">Total Guru</p>
              <p className="text-xl font-black text-purple-300">{teachers.length}</p>
            </div>
          </div>
        </div>

        {/* Toolbar Filter & Search */}
        <div className="glass-panel p-4 rounded-2xl border border-slate-800 bg-slate-900/40 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1 max-w-md">
            <div className="flex-1">
              <Input
                placeholder="Cari kode atau nama mapel…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="w-4 h-4 text-slate-500" />}
              />
            </div>
            <Button
              variant="ghost"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
              onClick={loadData}
              isLoading={isLoading}
              title="Muat Ulang"
              className="shrink-0"
            >
              Refresh
            </Button>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="w-40">
              <Select
                options={[
                  { value: "", label: "Semua Status (Default)" },
                  { value: "active", label: "Aktif Saja" },
                  { value: "inactive", label: "Nonaktif Saja" },
                ]}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Bulk Action Toolbar */}
        {selectedSubjectIds.length > 0 && (
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-indigo-950/90 border border-indigo-500/40 text-xs text-indigo-100 shadow-lg mb-4 animate-fade-in">
            <span className="font-semibold">
              Terpilih <strong className="text-indigo-300 font-mono text-sm">{selectedSubjectIds.length}</strong> mata pelajaran
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                className={
                  allSelectedAreInactive
                    ? "text-emerald-300 hover:bg-emerald-500/20 border border-emerald-500/30"
                    : "text-amber-300 hover:bg-amber-500/20 border border-amber-500/30"
                }
                isLoading={isBulkDeactivating}
                onClick={async () => {
                  setIsBulkDeactivating(true);
                  try {
                    if (allSelectedAreInactive) {
                      await subjectApi.bulkActivateSubjects(selectedSubjectIds);
                      showToast({ type: "success", title: "Aktivasi Masal Berhasil", message: `${selectedSubjectIds.length} mata pelajaran berhasil diaktifkan kembali.` });
                    } else {
                      await subjectApi.bulkDeactivateSubjects(selectedSubjectIds);
                      showToast({ type: "success", title: "Nonaktif Masal Berhasil", message: `${selectedSubjectIds.length} mata pelajaran dinonaktifkan.` });
                    }
                    setSelectedSubjectIds([]);
                    await loadData();
                  } catch (err: any) {
                    showToast({ type: "error", title: "Gagal Memproses", message: err?.message || "Terjadi kesalahan." });
                  } finally {
                    setIsBulkDeactivating(false);
                  }
                }}
              >
                {allSelectedAreInactive ? "Aktifkan Terpilih" : "Nonaktifkan Terpilih"}
              </Button>
              <Button
                variant="danger"
                size="sm"
                isLoading={isBulkDeleting}
                onClick={async () => {
                  if (!window.confirm(`Apakah Anda yakin ingin menghapus ${selectedSubjectIds.length} mata pelajaran terpilih?`)) return;
                  setIsBulkDeleting(true);
                  try {
                    await subjectApi.bulkDeleteSubjects(selectedSubjectIds);
                    showToast({ type: "success", title: "Hapus Masal Berhasil", message: `${selectedSubjectIds.length} mata pelajaran berhasil dihapus.` });
                    setSelectedSubjectIds([]);
                    await loadData();
                  } catch (err: any) {
                    showToast({ type: "error", title: "Gagal Hapus", message: err?.message || "Gagal menghapus data." });
                  } finally {
                    setIsBulkDeleting(false);
                  }
                }}
              >
                Hapus Terpilih
              </Button>
            </div>
          </div>
        )}

        {/* Mobile View: Cards */}
        <div className="block md:hidden space-y-3">
          {isLoading ? (
            <div className="glass-panel p-8 text-center text-xs text-slate-400">Memuat data mapel…</div>
          ) : filteredSubjects.length === 0 ? (
            <div className="glass-panel p-8 text-center text-xs text-slate-400">Tidak ada mata pelajaran ditemukan.</div>
          ) : (
            filteredSubjects.map((item) => (
              <div key={item.public_id} className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      className="mt-1 rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-0 cursor-pointer"
                      checked={selectedSubjectIds.includes(item.id)}
                      onChange={() => {
                        setSelectedSubjectIds((prev) =>
                          prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]
                        );
                      }}
                    />
                    <div>
                      <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-950/60 border border-indigo-500/30 px-2 py-0.5 rounded">
                        {item.code}
                      </span>
                      <h3 className="text-sm font-bold text-slate-100 mt-1.5">{item.name}</h3>
                      {item.description && (
                        <p className="text-xs text-slate-400 mt-0.5">{item.description}</p>
                      )}
                    </div>
                  </div>
                  <Badge variant={item.is_active ? "emerald" : "crimson"} size="sm">
                    {item.is_active ? "Aktif" : "Nonaktif"}
                  </Badge>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
                  <button
                    onClick={() => handleOpenCompetencyModal(item)}
                    className="flex items-center gap-1.5 text-xs text-indigo-400 font-semibold hover:underline"
                  >
                    <Users className="w-3.5 h-3.5" />
                    <span>{qualifiedCounts[item.id] || 0} Guru Kompeten</span>
                  </button>

                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => handleOpenEdit(item)}>
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleToggleActive(item)}>
                      {item.is_active ? "Nonaktifkan" : "Aktifkan"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeletingSubject(item)} className="text-rose-400">
                      Hapus
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Desktop View: Table */}
        <div className="hidden md:block">
          <Table
            columns={columns}
            data={filteredSubjects}
            isLoading={isLoading}
            keyExtractor={(item) => item.public_id}
            emptyMessage="Belum ada mata pelajaran. Klik tombol Tambah Mata Pelajaran di atas."
          />
        </div>
      </div>

      {/* ── Modal: Choice Add Data ── */}
      <AddDataChoiceModal
        isOpen={isAddChoiceOpen}
        onClose={() => setIsAddChoiceOpen(false)}
        entityName="Mata Pelajaran"
        onSelectManual={() => {
          handleOpenCreate();
        }}
        onDownloadTemplate={downloadSubjectTemplate}
        onImportXlsx={async (file) => {
          setIsImportingXlsx(true);
          try {
            const rows = await readXlsxFile(file);
            if (rows.length === 0) {
              showToast({ type: "error", title: "File Kosong", message: "File XLSX tidak berisi data." });
              return;
            }

            const payloadSubjects = rows.map((row, idx) => ({
              code: String(row["Kode Mapel"] || "").trim(),
              name: String(row["Nama Mata Pelajaran"] || "").trim(),
              description: String(row["Deskripsi"] || "").trim() || undefined,
              row_num: idx + 2
            })).filter(s => s.code || s.name);

            const result = await subjectApi.importSubjects({ subjects: payloadSubjects });
            showToast({
              type: "success",
              title: "Impor Berhasil",
              message: `Berhasil mengimpor ${result.imported_count} mata pelajaran.`,
            });
            await loadData();
          } catch (err: any) {
            const errMsg = err?.response?.data?.message || err?.message || "Format file salah.";
            showToast({ type: "error", title: "Gagal Memproses Impor", message: errMsg });
          } finally {
            setIsImportingXlsx(false);
          }
        }}
        isLoadingImport={isImportingXlsx}
      />

      {/* ── Modal: Tambah / Edit Mata Pelajaran ── */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingSubject ? `Edit Mata Pelajaran: ${editingSubject.name}` : "Tambah Mata Pelajaran Baru"}
        maxWidth="md"
      >
        <form onSubmit={handleSubmitForm} className="space-y-4">
          <Input
            label="Kode Mata Pelajaran (Wajib)"
            placeholder="Contoh: MAT-10, BIO-11, ENG-12"
            value={formCode}
            onChange={(e) => setFormCode(e.target.value.toUpperCase())}
            required
            disabled={!!editingSubject}
            helperText={editingSubject ? "Kode mata pelajaran bersifat immutable (tidak dapat diubah)." : "Gunakan kode singkat huruf kapital & angka."}
          />

          <Input
            label="Nama Mata Pelajaran (Wajib)"
            placeholder="Contoh: Matematika Peminatan X"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            required
          />

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">Deskripsi / Keterangan (Opsional)</label>
            <textarea
              className="w-full bg-slate-900/80 border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              rows={3}
              placeholder="Deskripsi silabus, kelompok kurikulum, atau catatan tambahan…"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Batal
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              {editingSubject ? "Simpan Perubahan" : "Daftarkan Mapel"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Penugasan Guru Mapel (Teacher Subject Assignment) ── */}
      <Modal
        isOpen={!!competencySubject}
        onClose={() => setCompetencySubject(null)}
        title={`Penugasan Guru: ${competencySubject?.name} (${competencySubject?.code})`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="p-3.5 bg-indigo-950/30 border border-indigo-500/30 rounded-xl flex items-start gap-3 text-xs text-indigo-300">
            <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <span>
              Pilih atau tugaskan guru yang mengajar mata pelajaran ini. Guru yang ditugaskan di sini dapat dipilih sebagai <strong>Guru Pengampu</strong> saat menyusun jadwal pelajaran dan struktur rombel kelas.
            </span>
          </div>

          <Input
            placeholder="Cari nama guru, NIP, atau username…"
            value={teacherSearch}
            onChange={(e) => setTeacherSearch(e.target.value)}
            leftIcon={<Search className="w-4 h-4 text-slate-500" />}
          />

          <div className="max-h-80 overflow-y-auto space-y-2 pr-1 divide-y divide-slate-800/60">
            {loadingCompetencies ? (
              <p className="text-center text-xs text-slate-400 py-8">Memuat daftar guru…</p>
            ) : filteredTeacherList.length === 0 ? (
              <p className="text-center text-xs text-slate-400 py-8">Tidak ada guru ditemukan.</p>
            ) : (
              filteredTeacherList.map((teacher) => {
                const isQualified = qualifiedTeachers.some((q) => q.teacher_id === teacher.id);
                const isToggling = togglingTeacherId === teacher.id;

                return (
                  <div
                    key={teacher.public_id}
                    className={`flex items-center justify-between p-3 rounded-xl transition-colors ${
                      isQualified ? "bg-indigo-950/20 border border-indigo-500/20" : "hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                          isQualified
                            ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {(teacher.name || teacher.username).charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-slate-100 truncate">
                          {teacher.name || "—"}
                        </p>
                        <p className="text-xs text-slate-400 font-mono">
                          {teacher.username} {teacher.nip ? `• NIP: ${teacher.nip}` : ""}
                        </p>
                      </div>
                    </div>

                    <button
                      disabled={isToggling}
                      onClick={() => handleToggleCompetency(teacher, isQualified)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        isQualified
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/40"
                          : "bg-slate-800 text-slate-300 border border-slate-700 hover:border-indigo-500 hover:text-indigo-300"
                      }`}
                    >
                      {isToggling ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : isQualified ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Ditugaskan</span>
                        </>
                      ) : (
                        <>
                          <Plus className="w-3.5 h-3.5" />
                          <span>Tugaskan</span>
                        </>
                      )}
                    </button>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex justify-end pt-3 border-t border-slate-800">
            <Button variant="primary" onClick={() => setCompetencySubject(null)}>
              Selesai
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Hapus Mata Pelajaran ── */}
      <Modal
        isOpen={!!deletingSubject}
        onClose={() => setDeletingSubject(null)}
        title="Konfirmasi Hapus Mata Pelajaran"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3.5 bg-rose-950/30 border border-rose-500/30 rounded-xl text-xs text-rose-300">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-slate-100">Apakah Anda yakin ingin menghapus mapel ini?</p>
              <p className="mt-1 text-slate-400">
                Mata pelajaran <strong>{deletingSubject?.name} ({deletingSubject?.code})</strong> akan dihapus permanen.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setDeletingSubject(null)}>
              Batal
            </Button>
            <Button variant="danger" isLoading={isDeleting} onClick={handleDeleteConfirm}>
              Hapus Mapel
            </Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
};
