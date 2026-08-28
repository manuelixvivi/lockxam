import React, { useState, useEffect, useMemo } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { classApi } from "../../api/class";
import type {
  ClassEntity,
  StudentEnrollment,
  ClassSubject,
  TeacherCandidate,
} from "../../api/class";
import { studentApi } from "../../api/student";
import type { StudentAccount } from "../../api/student";
import { subjectApi } from "../../api/subject";
import type { Subject } from "../../api/subject";
import {
  GraduationCap,
  Plus,
  Search,
  RefreshCw,
  CheckCircle,
  Users,
  BookOpen,
  UserPlus,
  AlertCircle,
  ArrowLeft,
  CheckSquare,
  Square,
  Trash2,
} from "lucide-react";

interface ClassStructureViewProps {
  classEntity: ClassEntity;
  academicYearName?: string;
  onClose: () => void;
  onNavigate?: (path: string) => void;
}

export const ClassStructureView: React.FC<ClassStructureViewProps> = ({
  classEntity,
  academicYearName,
  onClose,
  onNavigate,
}) => {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<"students" | "subjects" | "teachers">("students");

  // Tab 1: Enrolled Students
  const [enrolledStudents, setEnrolledStudents] = useState<StudentEnrollment[]>([]);
  const [loadingStudents, setLoadingStudents] = useState<boolean>(false);
  const [studentSearch, setStudentSearch] = useState<string>("");
  const [selectedStudentIds, setSelectedStudentIds] = useState<number[]>([]);
  const [isBulkRemovingStudents, setIsBulkRemovingStudents] = useState<boolean>(false);

  // Modal: Bulk Enroll Student from Master
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState<boolean>(false);
  const [masterStudents, setMasterStudents] = useState<StudentAccount[]>([]);
  const [loadingMasterStudents, setLoadingMasterStudents] = useState<boolean>(false);
  const [enrollSearch, setEnrollSearch] = useState<string>("");
  const [filterUnassignedOnly, setFilterUnassignedOnly] = useState<boolean>(false);
  const [selectedMasterStudentIds, setSelectedMasterStudentIds] = useState<number[]>([]);
  const [isBulkEnrolling, setIsBulkEnrolling] = useState<boolean>(false);

  // Tab 2: Class Subjects
  const [classSubjects, setClassSubjects] = useState<ClassSubject[]>([]);
  const [loadingClassSubjects, setLoadingClassSubjects] = useState<boolean>(false);
  const [selectedSubjectIds, setSelectedSubjectIds] = useState<number[]>([]);
  const [isBulkRemovingSubjects, setIsBulkRemovingSubjects] = useState<boolean>(false);

  // Modal: Bulk Add Subject to Class
  const [isAddSubjectModalOpen, setIsAddSubjectModalOpen] = useState<boolean>(false);
  const [allSubjects, setAllSubjects] = useState<Subject[]>([]);
  const [loadingAllSubjects, setLoadingAllSubjects] = useState<boolean>(false);
  const [selectedMasterSubjectIds, setSelectedMasterSubjectIds] = useState<number[]>([]);
  const [isBulkAssigningSubjects, setIsBulkAssigningSubjects] = useState<boolean>(false);

  // Tab 3 / Modal: Assign Teacher Candidate
  const [assigningSubject, setAssigningSubject] = useState<ClassSubject | null>(null);
  const [teacherCandidates, setTeacherCandidates] = useState<TeacherCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);

  const loadEnrolledStudents = async (classId: number) => {
    setLoadingStudents(true);
    try {
      const data = await classApi.listEnrolledStudents(classId);
      setEnrolledStudents(data);
      setSelectedStudentIds([]);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Siswa",
        message: err?.message || "Terjadi kesalahan saat memuat siswa kelas.",
      });
    } finally {
      setLoadingStudents(false);
    }
  };

  const loadClassSubjects = async (classId: number) => {
    setLoadingClassSubjects(true);
    try {
      const data = await classApi.listClassSubjects(classId);
      setClassSubjects(data);
      setSelectedSubjectIds([]);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Mapel Kelas",
        message: err?.message || "Terjadi kesalahan saat memuat mata pelajaran kelas.",
      });
    } finally {
      setLoadingClassSubjects(false);
    }
  };

  useEffect(() => {
    loadEnrolledStudents(classEntity.id);
    loadClassSubjects(classEntity.id);
  }, [classEntity.id]);

  // Bulk Student Operations
  const filteredEnrolledStudents = useMemo(() => {
    if (!studentSearch.trim()) return enrolledStudents;
    const q = studentSearch.toLowerCase();
    return enrolledStudents.filter(
      (e) =>
        (e.student_name || "").toLowerCase().includes(q) ||
        (e.nisn || "").toLowerCase().includes(q) ||
        (e.nis || "").toLowerCase().includes(q) ||
        (e.student_username || "").toLowerCase().includes(q)
    );
  }, [enrolledStudents, studentSearch]);

  const toggleSelectStudent = (studentId: number) => {
    setSelectedStudentIds((prev) =>
      prev.includes(studentId) ? prev.filter((id) => id !== studentId) : [...prev, studentId]
    );
  };

  const toggleSelectAllStudents = () => {
    if (selectedStudentIds.length === filteredEnrolledStudents.length) {
      setSelectedStudentIds([]);
    } else {
      setSelectedStudentIds(filteredEnrolledStudents.map((e) => e.student_id));
    }
  };

  const handleBulkRemoveStudents = async () => {
    if (selectedStudentIds.length === 0) return;
    const confirmRemove = window.confirm(
      `Apakah Anda yakin ingin melepas ${selectedStudentIds.length} siswa terpilih dari kelas '${classEntity.name}'?`
    );
    if (!confirmRemove) return;
    setIsBulkRemovingStudents(true);
    try {
      await classApi.bulkRemoveStudents(classEntity.id, selectedStudentIds);
      showToast({
        type: "success",
        title: "Siswa Dilepas",
        message: `${selectedStudentIds.length} siswa berhasil dilepas dari kelas '${classEntity.name}'.`,
      });
      await loadEnrolledStudents(classEntity.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Melepas Siswa", message: err?.message || "Gagal memproses." });
    } finally {
      setIsBulkRemovingStudents(false);
    }
  };

  // Bulk Enroll Modal Logic
  const handleOpenEnrollModal = async () => {
    setIsEnrollModalOpen(true);
    setLoadingMasterStudents(true);
    setSelectedMasterStudentIds([]);
    setEnrollSearch("");
    try {
      const data = await studentApi.listStudents();
      setMasterStudents(data);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat Master Siswa", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setLoadingMasterStudents(false);
    }
  };

  const filteredMasterStudents = useMemo(() => {
    return masterStudents.filter((st) => {
      const q = enrollSearch.toLowerCase();
      const matchesSearch =
        (st.name || "").toLowerCase().includes(q) ||
        (st.nisn || "").toLowerCase().includes(q) ||
        (st.nis || "").toLowerCase().includes(q) ||
        st.username.toLowerCase().includes(q);

      const matchesUnassigned = filterUnassignedOnly ? !st.class_name : true;
      return matchesSearch && matchesUnassigned;
    });
  }, [masterStudents, enrollSearch, filterUnassignedOnly]);

  const toggleSelectMasterStudent = (studentId: number) => {
    setSelectedMasterStudentIds((prev) =>
      prev.includes(studentId) ? prev.filter((id) => id !== studentId) : [...prev, studentId]
    );
  };

  const handleBulkEnrollSubmit = async () => {
    if (selectedMasterStudentIds.length === 0) return;
    setIsBulkEnrolling(true);
    try {
      await classApi.bulkEnrollStudents(classEntity.id, selectedMasterStudentIds);
      showToast({
        type: "success",
        title: "Siswa Berhasil Didaftarkan",
        message: `${selectedMasterStudentIds.length} siswa berhasil dimasukkan ke kelas ${classEntity.name}.`,
      });
      setIsEnrollModalOpen(false);
      await loadEnrolledStudents(classEntity.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memasukkan Siswa", message: err?.message || "Gagal memproses." });
    } finally {
      setIsBulkEnrolling(false);
    }
  };

  // Bulk Subject Operations
  const toggleSelectSubject = (subjectId: number) => {
    setSelectedSubjectIds((prev) =>
      prev.includes(subjectId) ? prev.filter((id) => id !== subjectId) : [...prev, subjectId]
    );
  };

  const toggleSelectAllSubjects = () => {
    if (selectedSubjectIds.length === classSubjects.length) {
      setSelectedSubjectIds([]);
    } else {
      setSelectedSubjectIds(classSubjects.map((cs) => cs.subject_id));
    }
  };

  const handleBulkRemoveSubjects = async () => {
    if (selectedSubjectIds.length === 0) return;
    const confirmRemove = window.confirm(
      `Apakah Anda yakin ingin menghapus ${selectedSubjectIds.length} mata pelajaran terpilih dari kelas ini?`
    );
    if (!confirmRemove) return;
    setIsBulkRemovingSubjects(true);
    try {
      await classApi.bulkRemoveSubjects(classEntity.id, selectedSubjectIds);
      showToast({
        type: "success",
        title: "Mapel Dihapus",
        message: `${selectedSubjectIds.length} mata pelajaran dilepas dari kelas.`,
      });
      await loadClassSubjects(classEntity.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Melepas Mapel", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsBulkRemovingSubjects(false);
    }
  };

  // Bulk Add Subject Modal Logic
  const handleOpenAddSubjectModal = async () => {
    setIsAddSubjectModalOpen(true);
    setLoadingAllSubjects(true);
    setSelectedMasterSubjectIds([]);
    try {
      const data = await subjectApi.listSubjects();
      setAllSubjects(data.filter((s) => s.is_active));
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat Mapel Master", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setLoadingAllSubjects(false);
    }
  };

  const toggleSelectMasterSubject = (subjectId: number) => {
    setSelectedMasterSubjectIds((prev) =>
      prev.includes(subjectId) ? prev.filter((id) => id !== subjectId) : [...prev, subjectId]
    );
  };

  const handleBulkAssignSubjectsSubmit = async () => {
    if (selectedMasterSubjectIds.length === 0) return;
    setIsBulkAssigningSubjects(true);
    try {
      await classApi.bulkAssignSubjects(classEntity.id, selectedMasterSubjectIds);
      showToast({
        type: "success",
        title: "Mapel Berhasil Ditambahkan",
        message: `${selectedMasterSubjectIds.length} mata pelajaran ditambahkan ke kelas ${classEntity.name}.`,
      });
      setIsAddSubjectModalOpen(false);
      await loadClassSubjects(classEntity.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menambahkan Mapel", message: err?.message || "Gagal memproses." });
    } finally {
      setIsBulkAssigningSubjects(false);
    }
  };

  // Candidate Teacher Modal
  const handleOpenTeacherCandidateModal = async (cs: ClassSubject) => {
    setAssigningSubject(cs);
    setLoadingCandidates(true);
    try {
      const candidates = await classApi.getTeacherCandidates(classEntity.id, cs.subject_id);
      setTeacherCandidates(candidates);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat Guru Kandidat", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleAssignTeacherConfirm = async (teacherId: number, teacherName: string) => {
    if (!assigningSubject) return;
    try {
      await classApi.assignTeacher(classEntity.id, assigningSubject.subject_id, teacherId);
      showToast({
        type: "success",
        title: "Guru Pengampu Ditugaskan",
        message: `'${teacherName}' ditugaskan mengampu mapel ${assigningSubject.subject_name}.`,
      });
      setAssigningSubject(null);
      await loadClassSubjects(classEntity.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menugaskan Guru", message: err?.message || "Gagal memproses." });
    }
  };

  return (
    <AppShell activeHref="/admin/classes" onNavigate={onNavigate}>
      <Breadcrumb
        items={[
          { label: "School Admin", href: "/admin/dashboard" },
          { label: "Manajemen Kelas", href: "#" },
          { label: `Struktur: ${classEntity.name}` },
        ]}
      />

      <div className="space-y-6 animate-fade-in">
        {/* Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel p-5 rounded-2xl border border-indigo-500/30 bg-indigo-950/20">
          <div>
            <button
              onClick={onClose}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-2"
            >
              <ArrowLeft className="w-4 h-4" />
              Kembali ke Daftar Kelas
            </button>
            <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
              <GraduationCap className="w-7 h-7 text-indigo-400 shrink-0" />
              Struktur Rombel: {classEntity.name}
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Tingkat: <strong className="text-indigo-300">{classEntity.grade_level || "—"}</strong> | Tahun Ajaran:{" "}
              <strong className="text-slate-200">{academicYearName || "Aktif"}</strong>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <span className="text-xs text-slate-400 block">Total Anggota Siswa:</span>
              <span className="text-lg font-bold text-emerald-400">{enrolledStudents.length} Siswa</span>
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              Selesai & Kembali
            </Button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <button
            onClick={() => setActiveTab("students")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === "students"
                ? "bg-indigo-600/25 text-indigo-300 border border-indigo-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Anggota Siswa ({enrolledStudents.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("subjects")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
              activeTab === "subjects"
                ? "bg-indigo-600/25 text-indigo-300 border border-indigo-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Kurikulum Mapel & Guru ({classSubjects.length})</span>
          </button>
        </div>

        {/* ── TAB 1: ANGGOTA SISWA (BULK OPERATIONS) ── */}
        {activeTab === "students" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 glass-panel p-4 rounded-xl border border-slate-800">
              <div className="w-full sm:w-80">
                <Input
                  placeholder="Cari nama siswa atau NISN..."
                  value={studentSearch}
                  onChange={(e) => setStudentSearch(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-slate-500" />}
                />
              </div>

              <div className="flex items-center gap-2">
                {selectedStudentIds.length > 0 && (
                  <Button
                    variant="danger"
                    size="sm"
                    leftIcon={<Trash2 className="w-4 h-4" />}
                    onClick={handleBulkRemoveStudents}
                    isLoading={isBulkRemovingStudents}
                  >
                    Lepas ({selectedStudentIds.length}) Siswa Terpilih
                  </Button>
                )}

                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<UserPlus className="w-4 h-4" />}
                  onClick={handleOpenEnrollModal}
                >
                  Tarik Siswa dari Master
                </Button>
              </div>
            </div>

            {/* Student Table */}
            <div className="glass-panel border border-slate-800 rounded-2xl overflow-hidden">
              {loadingStudents ? (
                <div className="p-12 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                  <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin" />
                  Memuat daftar siswa kelas...
                </div>
              ) : filteredEnrolledStudents.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-400">
                  Belum ada siswa terdaftar dalam kelas ini. Klik "Tarik Siswa dari Master" di atas.
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  <div className="bg-slate-900/80 px-4 py-3 text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <button onClick={toggleSelectAllStudents} className="text-slate-400 hover:text-slate-200">
                        {selectedStudentIds.length === filteredEnrolledStudents.length ? (
                          <CheckSquare className="w-4 h-4 text-indigo-400" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                      <span>Siswa ({filteredEnrolledStudents.length})</span>
                    </div>
                    <span>Status Membership</span>
                  </div>

                  {filteredEnrolledStudents.map((enr) => {
                    const isSelected = selectedStudentIds.includes(enr.student_id);
                    return (
                      <div
                        key={enr.id}
                        className={`px-4 py-3 flex items-center justify-between transition-colors ${
                          isSelected ? "bg-indigo-950/30" : "hover:bg-slate-800/30"
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <button onClick={() => toggleSelectStudent(enr.student_id)}>
                            {isSelected ? (
                              <CheckSquare className="w-4 h-4 text-indigo-400" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-600" />
                            )}
                          </button>
                          <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-xs font-bold shrink-0">
                            {(enr.student_name || enr.student_username || "S").charAt(0).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-slate-100 truncate">{enr.student_name || "—"}</p>
                            <p className="text-[11px] text-slate-400 font-mono">
                              NISN: {enr.nisn || "—"} • NIS: {enr.nis || "—"} • Username: {enr.student_username}
                            </p>
                          </div>
                        </div>

                        <Badge variant="emerald" size="sm">
                          AKTIF
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 2: KURIKULUM MAPEL & GURU ── */}
        {activeTab === "subjects" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 glass-panel p-4 rounded-xl border border-slate-800">
              <p className="text-xs text-slate-400">
                Daftar mata pelajaran terdaftar untuk kelas ini beserta penetapan Guru Pengampu.
              </p>

              <div className="flex items-center gap-2">
                {selectedSubjectIds.length > 0 && (
                  <Button
                    variant="danger"
                    size="sm"
                    leftIcon={<Trash2 className="w-4 h-4" />}
                    onClick={handleBulkRemoveSubjects}
                    isLoading={isBulkRemovingSubjects}
                  >
                    Lepas ({selectedSubjectIds.length}) Mapel Terpilih
                  </Button>
                )}

                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={handleOpenAddSubjectModal}
                >
                  Tambah Mapel ke Kelas
                </Button>
              </div>
            </div>

            {/* Subject Table */}
            <div className="glass-panel border border-slate-800 rounded-2xl overflow-hidden">
              {loadingClassSubjects ? (
                <div className="p-12 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                  <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin" />
                  Memuat mata pelajaran kelas...
                </div>
              ) : classSubjects.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-400">
                  Belum ada mata pelajaran yang ditambahkan ke kelas ini.
                </div>
              ) : (
                <div className="divide-y divide-slate-800">
                  <div className="bg-slate-900/80 px-4 py-3 text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <button onClick={toggleSelectAllSubjects} className="text-slate-400 hover:text-slate-200">
                        {selectedSubjectIds.length === classSubjects.length ? (
                          <CheckSquare className="w-4 h-4 text-indigo-400" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                      <span>Mata Pelajaran ({classSubjects.length})</span>
                    </div>
                    <span>Guru Pengampu</span>
                  </div>

                  {classSubjects.map((cs) => {
                    const isSelected = selectedSubjectIds.includes(cs.subject_id);
                    return (
                      <div
                        key={cs.id}
                        className={`px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-0 transition-colors ${
                          isSelected ? "bg-indigo-950/30" : "hover:bg-slate-800/30"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <button onClick={() => toggleSelectSubject(cs.subject_id)}>
                            {isSelected ? (
                              <CheckSquare className="w-4 h-4 text-indigo-400" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-600" />
                            )}
                          </button>
                          <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-950/60 border border-indigo-500/30 px-2 py-0.5 rounded">
                            {cs.subject_code || "MAPEL"}
                          </span>
                          <div>
                            <p className="text-xs font-bold text-slate-100">{cs.subject_name}</p>
                          </div>
                        </div>

                        <div className="flex items-center justify-between sm:justify-end gap-3 w-full sm:w-auto pl-7 sm:pl-0">
                          {cs.teacher_name ? (
                            <span className="text-xs text-emerald-300 font-semibold flex items-center gap-1">
                              <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                              {cs.teacher_name}
                            </span>
                          ) : (
                            <span className="text-xs text-amber-400 italic flex items-center gap-1">
                              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                              Belum Ada Guru
                            </span>
                          )}

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenTeacherCandidateModal(cs)}
                            className="text-xs"
                          >
                            {cs.teacher_name ? "Ganti Guru" : "Tugaskan Guru"}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Modal: Bulk Enroll Student from Master ── */}
      <Modal
        isOpen={isEnrollModalOpen}
        onClose={() => setIsEnrollModalOpen(false)}
        title={`Tarik & Enroll Siswa ke Kelas: ${classEntity.name}`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="flex-1">
              <Input
                placeholder="Cari nama siswa, NISN, atau NIS…"
                value={enrollSearch}
                onChange={(e) => setEnrollSearch(e.target.value)}
                leftIcon={<Search className="w-4 h-4 text-slate-500" />}
              />
            </div>
            <button
              onClick={() => setFilterUnassignedOnly(!filterUnassignedOnly)}
              className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
                filterUnassignedOnly
                  ? "bg-indigo-600/30 text-indigo-300 border-indigo-500/50"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {filterUnassignedOnly ? "✓ Hanya Tanpa Kelas" : "Tampilkan Semua Siswa"}
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto space-y-2 pr-1 divide-y divide-slate-800/60">
            {loadingMasterStudents ? (
              <p className="text-center text-xs text-slate-400 py-8">Memuat data siswa master…</p>
            ) : filteredMasterStudents.length === 0 ? (
              <p className="text-center text-xs text-slate-400 py-8">Tidak ada siswa yang sesuai pencarian.</p>
            ) : (
              filteredMasterStudents.map((st) => {
                const isSelected = selectedMasterStudentIds.includes(st.id);
                return (
                  <div
                    key={st.public_id}
                    onClick={() => toggleSelectMasterStudent(st.id)}
                    className={`flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-colors ${
                      isSelected ? "bg-indigo-950/40 border border-indigo-500/30" : "hover:bg-slate-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-indigo-400 shrink-0" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-600 shrink-0" />
                      )}
                      <div className="w-8 h-8 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center text-xs font-bold shrink-0">
                        {(st.name || st.username).charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-100 truncate">{st.name || "—"}</p>
                        <p className="text-[11px] text-slate-400 font-mono">
                          NISN: {st.nisn || "—"} • NIS: {st.nis || "—"} • Kelas Saat Ini: {st.class_name || "Tanpa Kelas"}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <span className="text-xs text-slate-400">
              Terpilih: <strong>{selectedMasterStudentIds.length}</strong> siswa
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setIsEnrollModalOpen(false)}>
                Batal
              </Button>
              <Button
                variant="primary"
                onClick={handleBulkEnrollSubmit}
                disabled={selectedMasterStudentIds.length === 0 || isBulkEnrolling}
                isLoading={isBulkEnrolling}
              >
                Enroll Siswa Terpilih ({selectedMasterStudentIds.length})
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Bulk Add Subject ── */}
      <Modal
        isOpen={isAddSubjectModalOpen}
        onClose={() => setIsAddSubjectModalOpen(false)}
        title={`Tambah Mata Pelajaran ke Kelas: ${classEntity.name}`}
        maxWidth="md"
      >
        <div className="space-y-4">
          <div className="max-h-80 overflow-y-auto space-y-2 pr-1">
            {loadingAllSubjects ? (
              <p className="text-center text-xs text-slate-400 py-8">Memuat data mapel master…</p>
            ) : allSubjects.length === 0 ? (
              <p className="text-center text-xs text-slate-400 py-8">Tidak ada mata pelajaran di Master Data.</p>
            ) : (
              allSubjects.map((s) => {
                const isSelected = selectedMasterSubjectIds.includes(s.id);
                return (
                  <div
                    key={s.public_id}
                    onClick={() => toggleSelectMasterSubject(s.id)}
                    className={`flex items-center justify-between p-3 rounded-xl cursor-pointer border transition-all ${
                      isSelected ? "bg-indigo-950/40 border-indigo-500/50" : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-indigo-400 shrink-0" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-600 shrink-0" />
                      )}
                      <span className="font-mono text-xs font-bold text-indigo-300 bg-indigo-950/60 border border-indigo-500/30 px-2 py-0.5 rounded">
                        {s.code}
                      </span>
                      <div>
                        <p className="text-xs font-bold text-slate-100">{s.name}</p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <span className="text-xs text-slate-400">
              Terpilih: <strong>{selectedMasterSubjectIds.length}</strong> mapel
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setIsAddSubjectModalOpen(false)}>
                Batal
              </Button>
              <Button
                variant="primary"
                onClick={handleBulkAssignSubjectsSubmit}
                disabled={selectedMasterSubjectIds.length === 0 || isBulkAssigningSubjects}
                isLoading={isBulkAssigningSubjects}
              >
                Tambahkan Mapel Terpilih ({selectedMasterSubjectIds.length})
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Candidate Teacher Selection ── */}
      <Modal
        isOpen={!!assigningSubject}
        onClose={() => setAssigningSubject(null)}
        title={`Pilih Guru Pengampu: ${assigningSubject?.subject_name}`}
        maxWidth="md"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-400">
            Pilih guru dari daftar kandidat terverifikasi kompetensinya untuk mata pelajaran ini:
          </p>

          <div className="max-h-72 overflow-y-auto space-y-2 pr-1">
            {loadingCandidates ? (
              <p className="text-center text-xs text-slate-400 py-8">Memverifikasi kompetensi guru…</p>
            ) : teacherCandidates.length === 0 ? (
              <div className="p-6 text-center bg-amber-950/20 border border-amber-500/30 rounded-xl text-amber-300 text-xs">
                Belum ada guru yang terdaftar memiliki kompetensi mapel ini. Silakan assign kompetensi guru terlebih dahulu di menu Kelola Guru.
              </div>
            ) : (
              teacherCandidates.map((tc) => (
                <div
                  key={tc.public_id}
                  className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/40 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-300 flex items-center justify-center text-xs font-bold shrink-0">
                      {tc.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-100">{tc.name}</p>
                      <p className="text-[11px] text-slate-400 font-mono">NIP: {tc.nip || "—"} • {tc.username}</p>
                    </div>
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleAssignTeacherConfirm(tc.teacher_id, tc.name)}
                    className="text-xs"
                  >
                    Pilih Guru Ini
                  </Button>
                </div>
              ))
            )}
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="ghost" onClick={() => setAssigningSubject(null)}>
              Batal
            </Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
};
