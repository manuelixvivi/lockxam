import React, { useState, useEffect, useMemo, useRef } from "react";
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
import { classApi } from "../../api/class";
import type {
  ClassEntity,
  StudentEnrollment,
  ClassSubject,
  TeacherCandidate,
} from "../../api/class";
import { academicApi } from "../../api/academic";
import type { AcademicYear } from "../../api/academic";
import { studentApi } from "../../api/student";
import type { StudentAccount } from "../../api/student";
import { subjectApi } from "../../api/subject";
import type { Subject } from "../../api/subject";
import { ROMAN_GRADE_OPTIONS } from "../../utils/gradeLevels";
import { AddDataChoiceModal } from "../../components/ui/AddDataChoiceModal";
import { ImportExportBar } from "../../components/ui/ImportExportBar";
import {
  downloadMultiSheetXlsxTemplate,
  readMultiSheetXlsxFile,
} from "../../utils/xlsx";
import {
  GraduationCap,
  Plus,
  Search,
  RefreshCw,
  Edit2,
  Trash2,
  CheckCircle,
  Users,
  BookOpen,
  UserPlus,
  AlertCircle,
  Download,
  ArrowLeft,
  CheckSquare,
  Square,
  CalendarDays,
} from "lucide-react";

interface ClassesViewProps {
  onNavigate?: (path: string) => void;
}

export const ClassesView: React.FC<ClassesViewProps> = ({ onNavigate }) => {
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Academic Years
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [selectedYearId, setSelectedYearId] = useState<number | null>(null);

  // Classes Data
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modal: Create / Edit Class
  const [isClassModalOpen, setIsClassModalOpen] = useState<boolean>(false);
  const [editingClass, setEditingClass] = useState<ClassEntity | null>(null);
  const [formSuffix, setFormSuffix] = useState<string>("");
  const [formGradeLevel, setFormGradeLevel] = useState<string>("X");
  const [isSubmittingClass, setIsSubmittingClass] = useState<boolean>(false);

  // Delete Target Class
  const [deletingClass, setDeletingClass] = useState<ClassEntity | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // ── FULL PAGE CLASS STRUCTURE VIEW ──
  const [detailClass, setDetailClass] = useState<ClassEntity | null>(null);
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

  // ── FULL XLSX IMPORT STATE ──
  const [isImportingXlsx, setIsImportingXlsx] = useState<boolean>(false);
  const [xlsxPreviewData, setXlsxPreviewData] = useState<Array<{
    name: string;
    grade_level?: string | null;
    students: Array<Record<string, any>>;
    subjects: Array<Record<string, any>>;
  }> | null>(null);
  const [isSubmittingImport, setIsSubmittingImport] = useState<boolean>(false);
  const [isAddChoiceOpen, setIsAddChoiceOpen] = useState<boolean>(false);

  // Load Academic Years
  const loadAcademicYears = async () => {
    try {
      const years = await academicApi.getAcademicYears();
      setAcademicYears(years);
      if (years.length > 0) {
        const activeYear = years.find((y: AcademicYear) => y.status === "ACTIVE") || years[0];
        setSelectedYearId(activeYear.id);
      } else {
        setSelectedYearId(null);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Tahun Ajaran",
        message: err?.message || "Terjadi kesalahan.",
      });
    }
  };

  // Load Classes for Selected Academic Year (or All if null)
  const loadClasses = async (yearId: number | null) => {
    setIsLoading(true);
    try {
      const data = await classApi.listClasses(yearId || undefined);
      setClasses(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Data Kelas",
        message: err?.message || "Terjadi kesalahan saat mengambil daftar kelas.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAcademicYears();
  }, []);

  useEffect(() => {
    loadClasses(selectedYearId);
  }, [selectedYearId]);

  const currentYearObj = useMemo(() => {
    return academicYears.find((y) => y.id === selectedYearId) || null;
  }, [academicYears, selectedYearId]);

  // Filtered Classes
  const filteredClasses = useMemo(() => {
    return classes.filter((c) => {
      const query = searchQuery.toLowerCase();
      return (
        c.name.toLowerCase().includes(query) ||
        (c.grade_level || "").toLowerCase().includes(query)
      );
    });
  }, [classes, searchQuery]);

  // ── Handlers: Class Master ──

  const handleOpenCreateClass = () => {
    if (!selectedYearId) {
      showToast({
        type: "warning",
        title: "Tahun Ajaran Belum Dipilih",
        message: "Pilih tahun ajaran aktif terlebih dahulu.",
      });
      return;
    }
    setEditingClass(null);
    setFormSuffix("");
    setFormGradeLevel("X");
    setIsClassModalOpen(true);
  };

  const handleOpenEditClass = (cls: ClassEntity) => {
    setEditingClass(cls);
    const gl = cls.grade_level || "X";
    setFormGradeLevel(gl);
    const prefixRegex = new RegExp("^" + gl + "\\s*", "i");
    setFormSuffix(cls.name.replace(prefixRegex, ""));
    setIsClassModalOpen(true);
  };

  const handleSubmitClassForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formSuffix.trim() || !selectedYearId) {
      showToast({
        type: "warning",
        title: "Validasi Gagal",
        message: "Nama rombel wajib diisi.",
      });
      return;
    }

    const fullClassName = formSuffix.trim().toLowerCase().startsWith(formGradeLevel.toLowerCase())
      ? formSuffix.trim()
      : `${formGradeLevel} ${formSuffix.trim()}`;

    setIsSubmittingClass(true);
    try {
      if (editingClass) {
        await classApi.updateClass(editingClass.public_id, {
          name: fullClassName,
          grade_level: formGradeLevel.trim(),
          is_active: editingClass.is_active,
        });
        showToast({
          type: "success",
          title: "Kelas Diperbarui",
          message: `Kelas '${fullClassName}' berhasil diperbarui.`,
        });
      } else {
        await classApi.createClass({
          academic_year_id: selectedYearId,
          name: fullClassName,
          grade_level: formGradeLevel.trim(),
        });
        showToast({
          type: "success",
          title: "Kelas Berhasil Dibuat",
          message: `Kelas '${fullClassName}' berhasil didaftarkan pada tahun ajaran ${currentYearObj?.name}.`,
        });
      }
      setIsClassModalOpen(false);
      await loadClasses(selectedYearId);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menyimpan Kelas",
        message: err?.message || "Terjadi kesalahan saat menyimpan kelas.",
      });
    } finally {
      setIsSubmittingClass(false);
    }
  };

  const handleDeleteClassConfirm = async () => {
    if (!deletingClass || !selectedYearId) return;
    setIsDeleting(true);
    try {
      await classApi.deleteClass(deletingClass.public_id);
      showToast({
        type: "success",
        title: "Kelas Dihapus",
        message: `Kelas '${deletingClass.name}' telah dihapus.`,
      });
      setDeletingClass(null);
      await loadClasses(selectedYearId);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Menghapus Kelas",
        message: err?.message || "Kelas tidak dapat dihapus.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // ── FULL PAGE CLASS STRUCTURE LOGIC ──

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

  const handleOpenDetailFullPage = (cls: ClassEntity) => {
    setDetailClass(cls);
    setActiveTab("students");
    loadEnrolledStudents(cls.id);
    loadClassSubjects(cls.id);
  };

  const handleCloseDetailFullPage = () => {
    setDetailClass(null);
    if (selectedYearId) {
      loadClasses(selectedYearId);
    }
  };

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
    if (!detailClass || selectedStudentIds.length === 0) return;
    setIsBulkRemovingStudents(true);
    try {
      await classApi.bulkRemoveStudents(detailClass.id, selectedStudentIds);
      showToast({
        type: "success",
        title: "Siswa Dilepas",
        message: `${selectedStudentIds.length} siswa berhasil dilepas dari kelas '${detailClass.name}'.`,
      });
      await loadEnrolledStudents(detailClass.id);
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
    if (!detailClass || selectedMasterStudentIds.length === 0) return;
    setIsBulkEnrolling(true);
    try {
      await classApi.bulkEnrollStudents(detailClass.id, selectedMasterStudentIds);
      showToast({
        type: "success",
        title: "Siswa Berhasil Didaftarkan",
        message: `${selectedMasterStudentIds.length} siswa berhasil dimasukkan ke kelas ${detailClass.name}.`,
      });
      setIsEnrollModalOpen(false);
      await loadEnrolledStudents(detailClass.id);
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
    if (!detailClass || selectedSubjectIds.length === 0) return;
    setIsBulkRemovingSubjects(true);
    try {
      await classApi.bulkRemoveSubjects(detailClass.id, selectedSubjectIds);
      showToast({
        type: "success",
        title: "Mapel Dihapus",
        message: `${selectedSubjectIds.length} mata pelajaran dilepas dari kelas.`,
      });
      await loadClassSubjects(detailClass.id);
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
    if (!detailClass || selectedMasterSubjectIds.length === 0) return;
    setIsBulkAssigningSubjects(true);
    try {
      await classApi.bulkAssignSubjects(detailClass.id, selectedMasterSubjectIds);
      showToast({
        type: "success",
        title: "Mapel Berhasil Ditambahkan",
        message: `${selectedMasterSubjectIds.length} mata pelajaran ditambahkan ke kelas ${detailClass.name}.`,
      });
      setIsAddSubjectModalOpen(false);
      await loadClassSubjects(detailClass.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menambahkan Mapel", message: err?.message || "Gagal memproses." });
    } finally {
      setIsBulkAssigningSubjects(false);
    }
  };

  // Candidate Teacher Modal
  const handleOpenTeacherCandidateModal = async (cs: ClassSubject) => {
    if (!detailClass) return;
    setAssigningSubject(cs);
    setLoadingCandidates(true);
    try {
      const candidates = await classApi.getTeacherCandidates(detailClass.id, cs.subject_id);
      setTeacherCandidates(candidates);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memuat Guru Kandidat", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleAssignTeacherConfirm = async (teacherId: number, teacherName: string) => {
    if (!detailClass || !assigningSubject) return;
    try {
      await classApi.assignTeacher(detailClass.id, assigningSubject.subject_id, teacherId);
      showToast({
        type: "success",
        title: "Guru Pengampu Ditugaskan",
        message: `'${teacherName}' ditugaskan mengampu mapel ${assigningSubject.subject_name}.`,
      });
      setAssigningSubject(null);
      await loadClassSubjects(detailClass.id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menugaskan Guru", message: err?.message || "Gagal memproses." });
    }
  };

  // ── FULL XLSX WORKBOOK IMPORT FOR CLASSES & STRUCTURE ──

  const handleDownloadXlsxTemplate = () => {
    const sheets = [
      {
        name: "Daftar_Kelas",
        headers: ["Nama Kelas", "Tingkat Kelas"],
        samples: [
          { "Nama Kelas": "X IPA-1", "Tingkat Kelas": "X" },
          { "Nama Kelas": "XI IPS-2", "Tingkat Kelas": "XI" },
        ],
      },
      {
        name: "Siswa_Per_Kelas",
        headers: ["Nama Kelas", "NISN", "NIS", "Username Siswa"],
        samples: [
          { "Nama Kelas": "X IPA-1", NISN: "0051234567", NIS: "1001", "Username Siswa": "siswa01" },
          { "Nama Kelas": "X IPA-1", NISN: "0051234568", NIS: "1002", "Username Siswa": "siswa02" },
        ],
      },
      {
        name: "Mapel_Per_Kelas",
        headers: ["Nama Kelas", "Kode Mapel", "Kode Guru / NIP / Username"],
        samples: [
          { "Nama Kelas": "X IPA-1", "Kode Mapel": "MAT-10", "Kode Guru / NIP / Username": "GR-001" },
          { "Nama Kelas": "X IPA-1", "Kode Mapel": "BIO-10", "Kode Guru / NIP / Username": "GR-002" },
        ],
      },
    ];

    downloadMultiSheetXlsxTemplate(sheets, "Template_Import_Kelas_dan_Struktur_Rombel");
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsImportingXlsx(true);
    try {
      const sheetsData = await readMultiSheetXlsxFile(file);
      const parsedClassesMap: Record<string, {
        name: string;
        grade_level?: string | null;
        students: Array<Record<string, any>>;
        subjects: Array<Record<string, any>>;
      }> = {};

      const extractGradeLevel = (name: string): string => {
        const parts = name.trim().split(/\s+/);
        const firstWord = parts[0].toUpperCase();
        const valid = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "7", "8", "9", "10", "11", "12"];
        return valid.includes(firstWord) ? firstWord : "X";
      };

      // Parse Sheet 1: Daftar_Kelas / Kelas
      const classSheet = sheetsData["Daftar_Kelas"] || sheetsData["Kelas"] || [];
      classSheet.forEach((row) => {
        const clsName = strVal(row["Nama Kelas"] || row["Kelas"] || row["Rombel"]);
        if (clsName) {
          const gl = strVal(row["Tingkat Kelas"] || row["Tingkat"] || row["Grade Level"]) || extractGradeLevel(clsName);
          parsedClassesMap[clsName] = {
            name: clsName,
            grade_level: gl,
            students: [],
            subjects: [],
          };
        }
      });

      // Parse Sheet 2: Siswa_Per_Kelas / Siswa
      const studentSheet = sheetsData["Siswa_Per_Kelas"] || sheetsData["Siswa"] || [];
      studentSheet.forEach((row) => {
        const clsName = strVal(row["Nama Kelas"] || row["Kelas"] || row["Rombel"]);
        if (clsName) {
          if (!parsedClassesMap[clsName]) {
            parsedClassesMap[clsName] = {
              name: clsName,
              grade_level: extractGradeLevel(clsName),
              students: [],
              subjects: [],
            };
          }
          parsedClassesMap[clsName].students.push({
            nisn: strVal(row["NISN"]),
            nis: strVal(row["NIS"]),
            username: strVal(row["Username Siswa"] || row["Username"]),
          });
        }
      });

      // Parse Sheet 3: Mapel_Per_Kelas / Mapel
      const subjectSheet = sheetsData["Mapel_Per_Kelas"] || sheetsData["Mapel"] || [];
      subjectSheet.forEach((row) => {
        const clsName = strVal(row["Nama Kelas"] || row["Kelas"] || row["Rombel"]);
        if (clsName) {
          if (!parsedClassesMap[clsName]) {
            parsedClassesMap[clsName] = {
              name: clsName,
              grade_level: extractGradeLevel(clsName),
              students: [],
              subjects: [],
            };
          }
          parsedClassesMap[clsName].subjects.push({
            subject_code: strVal(row["Kode Mapel"] || row["Mapel"]),
            teacher_code: strVal(row["Kode Guru / NIP / Username"] || row["Kode Guru"] || row["NIP Guru"] || row["Username Guru"]),
          });
        }
      });

      // Also check per-sheet per-class format if user used 1 Sheet per Class!
      Object.keys(sheetsData).forEach((sName) => {
        if (!["Daftar_Kelas", "Kelas", "Siswa_Per_Kelas", "Siswa", "Mapel_Per_Kelas", "Mapel"].includes(sName)) {
          const sheetRows = sheetsData[sName];
          if (sheetRows.length > 0) {
            const clsName = sName.trim();
            if (!parsedClassesMap[clsName]) {
              parsedClassesMap[clsName] = {
                name: clsName,
                grade_level: extractGradeLevel(clsName),
                students: [],
                subjects: [],
              };
            }
            sheetRows.forEach((row) => {
              const nisn = strVal(row["NISN"]);
              const nis = strVal(row["NIS"]);
              const stUname = strVal(row["Username Siswa"] || row["Username"]);
              if (nisn || nis || stUname) {
                parsedClassesMap[clsName].students.push({ nisn, nis, username: stUname });
              }

              const sCode = strVal(row["Kode Mapel"] || row["Mapel"]);
              const tCode = strVal(row["Kode Guru"] || row["NIP Guru"] || row["Username Guru"]);
              if (sCode) {
                parsedClassesMap[clsName].subjects.push({ subject_code: sCode, teacher_code: tCode });
              }
            });
          }
        }
      });

      const finalClassesList = Object.values(parsedClassesMap);
      if (finalClassesList.length === 0) {
        showToast({
          type: "warning",
          title: "File XLSX Kosong",
          message: "Tidak ada data kelas yang valid terbaca dari file.",
        });
      } else {
        setXlsxPreviewData(finalClassesList);
      }
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Membaca XLSX", message: err?.message || "Format file tidak didukung." });
    } finally {
      setIsImportingXlsx(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const strVal = (val: any) => (val !== undefined && val !== null ? String(val).trim() : "");

  const handleConfirmFullImport = async () => {
    if (!xlsxPreviewData || !selectedYearId) return;
    setIsSubmittingImport(true);
    try {
      const result = await classApi.importFullClassesXlsx({
        academic_year_id: selectedYearId,
        classes: xlsxPreviewData,
      });

      showToast({
        type: "success",
        title: "Impor Rombel Sukses",
        message: `${result.imported_classes_count} kelas, ${result.total_students_enrolled} siswa, dan ${result.total_subjects_assigned} mapel berhasil disinkronkan.`,
      });
      setXlsxPreviewData(null);
      await loadClasses(selectedYearId);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Memproses Impor", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsSubmittingImport(false);
    }
  };

  // ── Table Columns ──
  const columns: Column<ClassEntity>[] = [
    {
      key: "name",
      header: "Nama Kelas & Rombel",
      render: (item) => (
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-sm shrink-0">
            {item.name.substring(0, 3)}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-100">{item.name}</div>
            <div className="text-xs text-slate-400">
              Tingkat: <span className="font-mono text-indigo-400 font-bold">{item.grade_level || "—"}</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      key: "student_count",
      header: "Jumlah Siswa",
      width: "140px",
      render: (item) => (
        <div className="flex items-center gap-1.5 text-xs text-slate-300">
          <Users className="w-4 h-4 text-indigo-400" />
          <span className="font-bold">{item.student_count}</span>
          <span className="text-slate-500">siswa</span>
        </div>
      ),
    },
    {
      key: "subject_count",
      header: "Mata Pelajaran",
      width: "140px",
      render: (item) => (
        <div className="flex items-center gap-1.5 text-xs text-slate-300">
          <BookOpen className="w-4 h-4 text-purple-400" />
          <span className="font-bold">{item.subject_count}</span>
          <span className="text-slate-500">mapel</span>
        </div>
      ),
    },
    {
      key: "is_active",
      header: "Status",
      width: "120px",
      render: (item) => (
        <Badge variant={item.is_active ? "emerald" : "crimson"} size="sm">
          {item.is_active ? "Aktif" : "Nonaktif"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "Aksi Management",
      width: "240px",
      render: (item) => (
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleOpenDetailFullPage(item)}
            className="text-xs px-3"
            leftIcon={<Users className="w-3.5 h-3.5" />}
          >
            Kelola Struktur
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleOpenEditClass(item)}
            title="Edit Nama Kelas"
            className="px-2"
          >
            <Edit2 className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-300" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setDeletingClass(item)}
            title="Hapus Kelas"
            className="px-2 hover:bg-rose-500/20"
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-400" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <AppShell activeHref="/admin/classes" onNavigate={onNavigate}>
      <Breadcrumb
        items={
          detailClass
            ? [
                { label: "School Admin", href: "/admin/dashboard" },
                { label: "Manajemen Kelas", href: "#" },
                { label: `Struktur: ${detailClass.name}` },
              ]
            : [
                { label: "School Admin", href: "/admin/dashboard" },
                { label: "Manajemen Kelas & Rombel" },
              ]
        }
      />

      {/* ── FULL PAGE VIEW 1: CLASS STRUCTURE DETAIL (detailClass !== null) ── */}
      {detailClass ? (
        <div className="space-y-6 animate-fade-in">
          {/* Header Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-panel p-5 rounded-2xl border border-indigo-500/30 bg-indigo-950/20">
            <div>
              <button
                onClick={handleCloseDetailFullPage}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Kembali ke Daftar Kelas
              </button>
              <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
                <GraduationCap className="w-7 h-7 text-indigo-400 shrink-0" />
                Struktur Rombel: {detailClass.name}
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Tingkat: <strong className="text-indigo-300">{detailClass.grade_level || "—"}</strong> | Tahun Ajaran:{" "}
                <strong className="text-slate-200">{currentYearObj?.name || "Aktif"}</strong>
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right hidden sm:block">
                <span className="text-xs text-slate-400 block">Total Anggota Siswa:</span>
                <span className="text-lg font-bold text-emerald-400">{enrolledStudents.length} Siswa</span>
              </div>
              <Button variant="outline" size="sm" onClick={handleCloseDetailFullPage}>
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

          {/* ── TAB 1: ANGGOTA SISWA (FULL PAGE & BULK OPERATIONS) ── */}
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
                          className={`px-4 py-3 flex items-center justify-between transition-colors ${
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

                          <div className="flex items-center gap-3">
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
      ) : (
        /* ── FULL PAGE VIEW 2: MASTER CLASS LIST (detailClass === null) ── */
        <div className="space-y-6 animate-fade-in">
          {/* Header & Title */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
                <GraduationCap className="w-6 h-6 text-indigo-400 shrink-0" />
                Manajemen Kelas & Rombel
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Kelola kelas terikat Tahun Ajaran, susun anggota siswa (*enrollment*), kurikulum mapel, dan guru pengampu.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <Button
                variant="ghost"
                leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
                onClick={() => {
                  const exportBar = document.getElementById("export-kelas-btn");
                  if (exportBar) exportBar.click();
                }}
              >
                Ekspor Excel
              </Button>
              <Button
                variant="primary"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => setIsAddChoiceOpen(true)}
              >
                Tambah Kelas
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>
          </div>

          {/* Academic Year Selector Bar */}
          <div className="glass-panel p-4 rounded-2xl border border-indigo-500/30 bg-indigo-950/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <CalendarDays className="w-5 h-5 text-indigo-400 shrink-0" />
              <div>
                <span className="text-xs text-slate-400 font-semibold block">Tahun Ajaran Aktif:</span>
                <span className="text-sm font-bold text-slate-100">
                  {currentYearObj ? currentYearObj.name : "Memuat tahun ajaran…"}
                </span>
              </div>
              {currentYearObj?.status === "ACTIVE" && (
                <Badge variant="emerald" size="sm">AKTIF BERJALAN</Badge>
              )}
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs text-slate-400 hidden sm:inline">Ganti Tahun:</span>
              <div className="w-full sm:w-48">
                <Select
                  options={[
                    { value: "ALL", label: "Semua Tahun Ajaran" },
                    ...academicYears.map((y) => ({ value: y.id.toString(), label: y.name })),
                  ]}
                  value={selectedYearId === null ? "ALL" : selectedYearId.toString()}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === "ALL" || !val) {
                      setSelectedYearId(null);
                    } else {
                      setSelectedYearId(parseInt(val, 10));
                    }
                  }}
                />
              </div>
            </div>
          </div>

          {/* Controls Bar */}
          <div className="flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2 flex-1 max-w-md">
              <div className="flex-1">
                <Input
                  placeholder="Cari nama kelas atau tingkat…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-slate-500" />}
                />
              </div>
              <Button
                variant="ghost"
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
                onClick={() => loadClasses(selectedYearId)}
                isLoading={isLoading}
                title="Muat Ulang"
                className="shrink-0"
              >
                Refresh
              </Button>
            </div>
          </div>

          {/* Hidden ImportExportBar helper for programmatic export */}
          <div className="hidden">
            <ImportExportBar<ClassEntity>
              exportData={filteredClasses}
              exportColumns={[
                { label: "Nama Kelas", key: "name" },
                { label: "Tingkat", key: "grade_level" },
                { label: "Jumlah Siswa", key: "student_count" },
                { label: "Jumlah Mapel", key: "subject_count" },
              ]}
              exportFilename="daftar-kelas-rombel"
              sheetName="Kelas Rombel"
              templateHeaders={["Nama Kelas", "Tingkat"]}
              templateSamples={[{ "Nama Kelas": "X IPA-1", Tingkat: "X" }]}
              templateFilename="template-import-kelas"
              onImportRow={async () => null}
            />
          </div>

          {/* Desktop View: Table */}
          <div className="hidden md:block">
            <Table
              columns={columns}
              data={filteredClasses}
              isLoading={isLoading}
              keyExtractor={(item) => item.public_id}
              emptyMessage={`Belum ada kelas pada tahun ajaran ${currentYearObj?.name || ""}. Klik Tambah Kelas Baru di atas.`}
            />
          </div>

          {/* Mobile View: Cards */}
          <div className="block md:hidden space-y-3">
            {isLoading ? (
              <div className="p-8 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-2">
                <RefreshCw className="w-5 h-5 text-indigo-400 animate-spin" />
                <span>Memuat daftar kelas...</span>
              </div>
            ) : filteredClasses.length === 0 ? (
              <div className="glass-panel p-8 text-center text-xs text-slate-400 rounded-2xl border border-slate-800">
                Belum ada kelas pada tahun ajaran {currentYearObj?.name || ""}. Klik "Tambah Kelas Baru" di atas.
              </div>
            ) : (
              filteredClasses.map((item) => (
                <div
                  key={item.public_id}
                  className="glass-panel p-4 rounded-2xl border border-slate-800 space-y-3 bg-slate-900/60 hover:border-slate-700 transition-all"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-sm shrink-0">
                        {item.name.substring(0, 3)}
                      </div>
                      <div>
                        <div className="text-sm font-bold text-slate-100">{item.name}</div>
                        <div className="text-xs text-slate-400">
                          Tingkat: <span className="font-mono text-indigo-400 font-bold">{item.grade_level || "—"}</span>
                        </div>
                      </div>
                    </div>
                    <Badge variant={item.is_active ? "emerald" : "crimson"} size="sm">
                      {item.is_active ? "Aktif" : "Nonaktif"}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-slate-400 pt-2 border-t border-slate-800/60">
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <Users className="w-4 h-4 text-indigo-400" />
                      <span className="font-bold">{item.student_count}</span>
                      <span className="text-slate-500">siswa</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-300">
                      <BookOpen className="w-4 h-4 text-purple-400" />
                      <span className="font-bold">{item.subject_count}</span>
                      <span className="text-slate-500">mapel</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenDetailFullPage(item)}
                      className="flex-1 text-xs"
                      leftIcon={<Users className="w-3.5 h-3.5" />}
                    >
                      Kelola Struktur
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenEditClass(item)}
                      title="Edit Nama Kelas"
                      className="px-2.5"
                    >
                      <Edit2 className="w-3.5 h-3.5 text-slate-400 hover:text-indigo-300" />
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingClass(item)}
                      title="Hapus Kelas"
                      className="px-2.5 hover:bg-rose-500/20"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Modal: Choice Add Data ── */}
      <AddDataChoiceModal
        isOpen={isAddChoiceOpen}
        onClose={() => setIsAddChoiceOpen(false)}
        entityName="Kelas"
        onSelectManual={handleOpenCreateClass}
        onDownloadTemplate={handleDownloadXlsxTemplate}
        onImportXlsx={async (file) => {
          const fakeEvent = { target: { files: [file], value: "" } } as any;
          await handleFileChange(fakeEvent);
        }}
        isLoadingImport={isImportingXlsx}
      />

      {/* ── Modal: Tambah / Edit Kelas ── */}
      <Modal
        isOpen={isClassModalOpen}
        onClose={() => setIsClassModalOpen(false)}
        title={editingClass ? `Edit Kelas: ${editingClass.name}` : `Tambah Kelas Baru (${currentYearObj?.name})`}
        maxWidth="md"
      >
        <form onSubmit={handleSubmitClassForm} className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                Tingkat Kelas (Wajib)
              </label>
              <Select
                value={formGradeLevel}
                onChange={(e) => setFormGradeLevel(e.target.value)}
                options={ROMAN_GRADE_OPTIONS}
                required
              />
            </div>
            <div className="col-span-2">
              <Input
                label="Nama Rombel / Extension (Wajib)"
                placeholder="Contoh: IPA-1, MIPA 1, IPS 2, RPL A"
                value={formSuffix}
                onChange={(e) => setFormSuffix(e.target.value)}
                required
                helperText={`Hasil nama kelas: ${formGradeLevel} ${formSuffix.trim() || "..."}`}
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button type="button" variant="ghost" onClick={() => setIsClassModalOpen(false)}>
              Batal
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmittingClass}>
              {editingClass ? "Simpan Perubahan" : "Buat Kelas"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Bulk Enroll Student from Master ── */}
      <Modal
        isOpen={isEnrollModalOpen}
        onClose={() => setIsEnrollModalOpen(false)}
        title={`Tarik & Enroll Siswa ke Kelas: ${detailClass?.name}`}
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
        title={`Tambah Mata Pelajaran ke Kelas: ${detailClass?.name}`}
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

      {/* ── Modal: Preview & Confirm Full XLSX Import ── */}
      <Modal
        isOpen={!!xlsxPreviewData}
        onClose={() => setXlsxPreviewData(null)}
        title="Pratinjau Impor Rombel XLSX"
        maxWidth="lg"
      >
        {xlsxPreviewData && (
          <div className="space-y-4">
            <div className="p-3.5 bg-indigo-950/30 border border-indigo-500/30 rounded-xl text-xs text-indigo-200">
              <span className="font-bold block mb-1">Struktur File Terbaca:</span>
              Ditemukan <strong>{xlsxPreviewData.length} kelas</strong> yang siap didaftarkan ke Tahun Ajaran{" "}
              <strong>{currentYearObj?.name}</strong>.
            </div>

            <div className="max-h-72 overflow-y-auto space-y-3 pr-1">
              {xlsxPreviewData.map((cls, idx) => (
                <div key={idx} className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-100">{cls.name}</span>
                    <Badge variant="indigo">Tingkat: {cls.grade_level || "X"}</Badge>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-slate-400">
                    <span className="flex items-center gap-1 text-emerald-400">
                      <Users className="w-3.5 h-3.5" />
                      {cls.students.length} Siswa
                    </span>
                    <span className="flex items-center gap-1 text-purple-400">
                      <BookOpen className="w-3.5 h-3.5" />
                      {cls.subjects.length} Mapel
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button variant="ghost" onClick={() => setXlsxPreviewData(null)}>
                Batal
              </Button>
              <Button
                variant="primary"
                onClick={handleConfirmFullImport}
                isLoading={isSubmittingImport}
              >
                Proses Impor ({xlsxPreviewData.length} Kelas)
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ── Modal: Hapus Kelas Confirm ── */}
      <Modal
        isOpen={!!deletingClass}
        onClose={() => setDeletingClass(null)}
        title="Hapus Kelas"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-300">
            Apakah Anda yakin ingin menghapus kelas <strong>{deletingClass?.name}</strong>?
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setDeletingClass(null)}>
              Batal
            </Button>
            <Button variant="danger" isLoading={isDeleting} onClick={handleDeleteClassConfirm}>
              Hapus Kelas
            </Button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
};
