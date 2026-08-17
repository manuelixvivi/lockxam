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
import { MessageBox } from "../../components/ui/MessageBox";
import { useToast } from "../../context/ToastContext";
import { examScheduleApi } from "../../api/examSchedule";
import type { ExamSchedule, ExamSchedulePackage } from "../../api/examSchedule";
import { academicApi } from "../../api/academic";
import type { AcademicYear, AcademicSemester } from "../../api/academic";
import { classApi } from "../../api/class";
import type { ClassEntity, ClassSubject } from "../../api/class";
import { teacherApi } from "../../api/teacher";
import type { TeacherAccount } from "../../api/teacher";
import { readXlsxFile, downloadXlsxTemplate } from "../../utils/xlsx";
import {
  FileCheck,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Edit2,
  Calendar,
  Clock,
  UserCheck,
  ShieldCheck,
  AlertCircle,
  GraduationCap,
  CheckCircle,
  Timer,
  Lock,
  ChevronLeft,
  Upload,
  FileSpreadsheet,
  Loader2,
} from "lucide-react";

interface ExamSchedulesViewProps {
  onNavigate?: (path: string) => void;
}

export const ExamSchedulesView: React.FC<ExamSchedulesViewProps> = ({ onNavigate }) => {
  const { showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reference Masters
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [semesters, setSemesters] = useState<AcademicSemester[]>([]);
  const [classes, setClasses] = useState<ClassEntity[]>([]);
  const [teachers, setTeachers] = useState<TeacherAccount[]>([]);

  // Selected Package Context
  const [selectedPackage, setSelectedPackage] = useState<ExamSchedulePackage | null>(null);

  // Packages List View State
  const [packages, setPackages] = useState<ExamSchedulePackage[]>([]);
  const [isPackagesLoading, setIsPackagesLoading] = useState<boolean>(true);
  const [packageFilterYearId, setPackageFilterYearId] = useState<number | null>(null);

  // Modal: Create Package
  const [isCreatePackageOpen, setIsCreatePackageOpen] = useState<boolean>(false);
  const [formPackageTitle, setFormPackageTitle] = useState<string>("");
  const [formPackageYearId, setFormPackageYearId] = useState<number | null>(null);
  const [isCreatingPackage, setIsCreatingPackage] = useState<boolean>(false);

  // Modal: Delete Package
  const [deletingPackage, setDeletingPackage] = useState<ExamSchedulePackage | null>(null);
  const [isDeletingPackage, setIsDeletingPackage] = useState<boolean>(false);

  // Selected Package Schedules View State
  const [schedules, setSchedules] = useState<ExamSchedule[]>([]);
  const [isSchedulesLoading, setIsSchedulesLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [classFilterId, setClassFilterId] = useState<number | null>(null);

  // Modal: Create / Edit Schedule Manual
  const [isCreateScheduleOpen, setIsCreateScheduleOpen] = useState<boolean>(false);
  const [editingSchedule, setEditingSchedule] = useState<ExamSchedule | null>(null);
  const [formSchSemesterId, setFormSchSemesterId] = useState<number | null>(null);
  const [formSchClassId, setFormSchClassId] = useState<number | null>(null);
  const [formSchClassSubjects, setFormSchClassSubjects] = useState<ClassSubject[]>([]);
  const [formSchSubjectId, setFormSchSubjectId] = useState<number | null>(null);
  const [formSchName, setFormSchName] = useState<string>("");
  const [formSchDate, setFormSchDate] = useState<string>("");
  const [formSchStartTime, setFormSchStartTime] = useState<string>("08:00");
  const [formSchEndTime, setFormSchEndTime] = useState<string>("09:30");
  const [formSchDuration, setFormSchDuration] = useState<number>(90);
  const [formSchProctorId, setFormSchProctorId] = useState<number | null>(null);
  const [formTargetType, setFormTargetType] = useState<"ALL_CLASS" | "SPECIFIC_STUDENTS">("ALL_CLASS");
  const [formAllowedStudentIds, setFormAllowedStudentIds] = useState<number[]>([]);
  const [formLockBrowser, setFormLockBrowser] = useState<boolean>(true);
  const [formEydLanguageEval, setFormEydLanguageEval] = useState<boolean>(false);
  const [formRandomizePerType, setFormRandomizePerType] = useState<boolean>(true);
  const [classStudents, setClassStudents] = useState<any[]>([]);
  const [loadingClassStudents, setLoadingClassStudents] = useState<boolean>(false);
  const [isSubmittingSchedule, setIsSubmittingSchedule] = useState<boolean>(false);

  // Modal: Assign Proctor
  const [proctorSchedule, setProctorSchedule] = useState<ExamSchedule | null>(null);
  const [selectedProctorId, setSelectedProctorId] = useState<number | null>(null);
  const [isAssigningProctor, setIsAssigningProctor] = useState<boolean>(false);

  // Modal: Delete Schedule
  const [deletingSchedule, setDeletingSchedule] = useState<ExamSchedule | null>(null);
  const [isDeletingSchedule, setIsDeletingSchedule] = useState<boolean>(false);

  // Excel Import Loading State
  const [isImportingXlsx, setIsImportingXlsx] = useState<boolean>(false);

  // Load Reference Masters
  const loadReferences = async () => {
    try {
      const [yearsData, teachersData] = await Promise.all([
        academicApi.getAcademicYears(),
        teacherApi.listTeachers(),
      ]);
      setAcademicYears(yearsData);
      setTeachers(teachersData);

      const allSemesters = yearsData.flatMap((y: AcademicYear) => y.semesters || []);
      setSemesters(allSemesters);

      if (yearsData.length > 0) {
        const activeYear = yearsData.find((y: AcademicYear) => y.status === "ACTIVE") || yearsData[0];
        setPackageFilterYearId(activeYear.id);
        setFormPackageYearId(activeYear.id);

        const classesData = await classApi.listClasses(activeYear.id);
        setClasses(classesData);
      }

      if (allSemesters.length > 0) {
        const activeSem = allSemesters.find((s: AcademicSemester) => s.status === "ACTIVE") || allSemesters[0];
        setFormSchSemesterId(activeSem.id);
      }
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Referensi",
        message: err?.message || "Terjadi kesalahan memuat data master.",
      });
    }
  };

  // Load Packages list
  const loadPackages = async () => {
    setIsPackagesLoading(true);
    try {
      const data = await examScheduleApi.listPackages(packageFilterYearId || undefined);
      setPackages(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Paket",
        message: err?.message || "Gagal mengambil data paket jadwal ujian.",
      });
    } finally {
      setIsPackagesLoading(false);
    }
  };

  // Load Schedules inside selected package
  const loadPackageSchedules = async (packagePublicId: string) => {
    setIsSchedulesLoading(true);
    try {
      const pkg = await examScheduleApi.getPackage(packagePublicId);
      setSelectedPackage(pkg);
      setSchedules(pkg.schedules || []);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Jadwal Paket",
        message: err?.message || "Terjadi kesalahan memuat rincian jadwal.",
      });
    } finally {
      setIsSchedulesLoading(false);
    }
  };

  useEffect(() => {
    loadReferences();
  }, []);

  useEffect(() => {
    loadPackages();
  }, [packageFilterYearId]);

  // Load class subjects & students when class dropdown is selected in Schedule Modal
  useEffect(() => {
    if (formSchClassId) {
      classApi.listClassSubjects(formSchClassId).then((subs) => {
        setFormSchClassSubjects(subs);
        if (subs.length > 0) {
          setFormSchSubjectId(subs[0].subject_id);
        } else {
          setFormSchSubjectId(null);
        }
      });

      if (formTargetType === "SPECIFIC_STUDENTS") {
        setLoadingClassStudents(true);
        classApi
          .listEnrolledStudents(formSchClassId)
          .then((stList) => setClassStudents(stList))
          .catch(() => setClassStudents([]))
          .finally(() => setLoadingClassStudents(false));
      }
    } else {
      setFormSchClassSubjects([]);
      setFormSchSubjectId(null);
      setClassStudents([]);
    }
  }, [formSchClassId, formTargetType]);

  // Retrieve current selected subject details in modal
  const selectedSchSubjectObj = useMemo(() => {
    return formSchClassSubjects.find((s) => s.subject_id === formSchSubjectId);
  }, [formSchClassSubjects, formSchSubjectId]);

  // Auto-calculate End Time based on Start Time + Duration
  const calculateEndTime = (startTimeStr: string, durationMinutes: number): string => {
    if (!startTimeStr || !startTimeStr.includes(":")) return "09:30";
    const [hStr, mStr] = startTimeStr.split(":");
    let hours = parseInt(hStr, 10);
    let minutes = parseInt(mStr, 10);

    if (isNaN(hours) || isNaN(minutes)) return "09:30";

    let totalMinutes = hours * 60 + minutes + (durationMinutes || 0);
    let endHours = Math.floor(totalMinutes / 60) % 24;
    let endMinutes = totalMinutes % 60;

    const hh = String(endHours).padStart(2, "0");
    const mm = String(endMinutes).padStart(2, "0");
    return `${hh}:${mm}`;
  };

  const handleStartTimeChange = (newStartTime: string) => {
    setFormSchStartTime(newStartTime);
    if (formSchDuration > 0) {
      const newEnd = calculateEndTime(newStartTime, formSchDuration);
      setFormSchEndTime(newEnd);
    }
  };

  const handleDurationChange = (newDuration: number) => {
    setFormSchDuration(newDuration);
    if (formSchStartTime && newDuration > 0) {
      const newEnd = calculateEndTime(formSchStartTime, newDuration);
      setFormSchEndTime(newEnd);
    }
  };

  // Filter schedules within selected package
  const filteredSchedules = useMemo(() => {
    return schedules.filter((s) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        s.name.toLowerCase().includes(q) ||
        (s.class_name || "").toLowerCase().includes(q) ||
        (s.subject_name || "").toLowerCase().includes(q) ||
        (s.teacher_name || "").toLowerCase().includes(q) ||
        (s.proctor_name || "").toLowerCase().includes(q);

      const matchesStatus = statusFilter ? s.status === statusFilter : true;
      const matchesClass = classFilterId ? s.class_id === classFilterId : true;

      return matchesSearch && matchesStatus && matchesClass;
    });
  }, [schedules, searchQuery, statusFilter, classFilterId]);

  // Action: Create Package
  const handleCreatePackageSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formPackageTitle.trim() || !formPackageYearId) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Judul paket dan tahun ajaran wajib diisi." });
      return;
    }
    setIsCreatingPackage(true);
    try {
      await examScheduleApi.createPackage({
        title: formPackageTitle.trim(),
        academic_year_id: formPackageYearId,
      });
      showToast({ type: "success", title: "Paket Dibuat", message: "Paket jadwal ujian berhasil ditambahkan." });
      setIsCreatePackageOpen(false);
      setFormPackageTitle("");
      await loadPackages();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Membuat Paket", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsCreatingPackage(false);
    }
  };

  // Action: Delete Package
  const handleDeletePackageConfirm = async () => {
    if (!deletingPackage) return;
    setIsDeletingPackage(true);
    try {
      await examScheduleApi.deletePackage(deletingPackage.public_id);
      showToast({ type: "success", title: "Paket Dihapus", message: `Paket '${deletingPackage.title}' telah dihapus.` });
      setDeletingPackage(null);
      await loadPackages();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menghapus Paket", message: err?.message || "Gagal menghapus." });
    } finally {
      setIsDeletingPackage(false);
    }
  };

  // Action: Revert Schedule to Draft Confirm
  const [revertingSchedule, setRevertingSchedule] = useState<{ public_id: string; title: string } | null>(null);
  const [isRevertingSchedule, setIsRevertingSchedule] = useState(false);

  const handleConfirmRevertSchedule = async () => {
    if (!revertingSchedule) return;
    setIsRevertingSchedule(true);
    try {
      await examScheduleApi.updateSchedule(revertingSchedule.public_id, { status: "DRAFT" });
      showToast({ type: "success", title: "Status Dibatalkan", message: "Jadwal dikembalikan ke status DRAFT." });
      setRevertingSchedule(null);
      if (selectedPackage) {
        await loadPackageSchedules(selectedPackage.public_id);
      }
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Ubah Status", message: err?.message || "Gagal mengubah status." });
    } finally {
      setIsRevertingSchedule(false);
    }
  };

  // Action: Open Edit Schedule Modal
  const handleOpenEditSchedule = (sch: ExamSchedule) => {
    setEditingSchedule(sch);
    setFormSchSemesterId(sch.academic_semester_id);
    setFormSchClassId(sch.class_id);
    setFormSchSubjectId(sch.subject_id);
    setFormSchName(sch.name || (sch as any).title || "");
    setFormSchDuration(sch.duration_minutes);
    setFormSchProctorId(sch.proctor_id || null);
    setFormTargetType(sch.target_type === "SPECIFIC_STUDENTS" ? "SPECIFIC_STUDENTS" : "ALL_CLASS");
    setFormAllowedStudentIds(sch.allowed_student_ids || []);
    setFormLockBrowser(sch.lock_browser !== undefined ? sch.lock_browser : true);
    setFormEydLanguageEval(sch.eyd_language_evaluation !== undefined ? sch.eyd_language_evaluation : false);
    setFormRandomizePerType(sch.randomize_per_type !== undefined ? sch.randomize_per_type : true);

    if (sch.start_time) {
      try {
        const dtStart = new Date(sch.start_time);
        const yyyy = dtStart.getFullYear();
        const mm = String(dtStart.getMonth() + 1).padStart(2, "0");
        const dd = String(dtStart.getDate()).padStart(2, "0");
        setFormSchDate(`${yyyy}-${mm}-${dd}`);
        setFormSchStartTime(dtStart.toTimeString().substring(0, 5));
      } catch {
        setFormSchDate("");
        setFormSchStartTime("08:00");
      }
    }

    if (sch.end_time) {
      try {
        const dtEnd = new Date(sch.end_time);
        setFormSchEndTime(dtEnd.toTimeString().substring(0, 5));
      } catch {
        setFormSchEndTime("09:30");
      }
    }

    setIsCreateScheduleOpen(true);
  };

  // Action: Create or Update Schedule Manual
  const handleCreateScheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPackage) return;
    if (!formSchSemesterId || !formSchClassId || !formSchSubjectId || !formSchName.trim() || !formSchDate) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Semua kolom wajib diisi." });
      return;
    }

    if (formTargetType === "SPECIFIC_STUDENTS" && formAllowedStudentIds.length === 0) {
      showToast({
        type: "warning",
        title: "Validasi Siswa Susulan",
        message: "Pilih setidaknya 1 siswa susulan yang berhak mengikuti ujian ini.",
      });
      return;
    }

      const startIso = `${formSchDate}T${formSchStartTime}:00`;
      const startDateObj = new Date(startIso);
      // Handle midnight crossover: if end HH:MM <= start HH:MM, end falls on the next calendar day
      let endDate = formSchDate;
      const [sH, sM] = formSchStartTime.split(":").map(Number);
      const [eH, eM] = formSchEndTime.split(":").map(Number);
      if (eH < sH || (eH === sH && eM <= sM)) {
        const nextDay = new Date(startDateObj);
        nextDay.setDate(nextDay.getDate() + 1);
        const ny = nextDay.getFullYear();
        const nm = String(nextDay.getMonth() + 1).padStart(2, "0");
        const nd = String(nextDay.getDate()).padStart(2, "0");
        endDate = `${ny}-${nm}-${nd}`;
      }
      const endIso = `${endDate}T${formSchEndTime}:00`;
      const startMs = startDateObj.getTime();
      const endMs = new Date(endIso).getTime();
      const minEndMs = startMs + formSchDuration * 60 * 1000;

      // 1. Validasi waktu selesai >= waktu mulai + durasi pengerjaan
      if (endMs < minEndMs) {
        const minEndStr = new Date(minEndMs).toTimeString().substring(0, 5);
        showToast({
          type: "warning",
          title: "Validasi Waktu Selesai Ujian",
          message: `Waktu selesai (${formSchEndTime}) tidak boleh kurang dari waktu mulai (${formSchStartTime}) + durasi (${formSchDuration}m). Minimal selesai jam ${minEndStr}.`,
        });
        return;
      }

      // 2. Validasi bentrok jadwal di kelas yang sama
      const overlap = schedules.find((s) => {
        if (s.class_id !== formSchClassId) return false;
        if (editingSchedule && s.public_id === editingSchedule.public_id) return false;

        const sStart = new Date(s.start_time).getTime();
        const sEnd = new Date(s.end_time).getTime();
        return startMs < sEnd && endMs > sStart;
      });

      if (overlap) {
        const oStart = new Date(overlap.start_time).toTimeString().substring(0, 5);
        const oEnd = new Date(overlap.end_time).toTimeString().substring(0, 5);
        showToast({
          type: "warning",
          title: "Validasi Bentrok Jadwal Kelas",
          message: `Waktu ujian menimpa jadwal lain di kelas yang sama: '${overlap.name}' (${oStart} - ${oEnd}).`,
        });
        return;
      }

      setIsSubmittingSchedule(true);
      try {
        const payload: any = {
        academic_year_id: selectedPackage.academic_year_id,
        academic_semester_id: formSchSemesterId,
        class_id: formSchClassId,
        subject_id: formSchSubjectId,
        title: formSchName.trim(),
        name: formSchName.trim(),
        start_time: startIso,
        end_time: endIso,
        duration_minutes: formSchDuration,
        proctor_id: formSchProctorId || undefined,
        package_id: selectedPackage.id,
        target_type: formTargetType,
        allowed_student_ids: formTargetType === "SPECIFIC_STUDENTS" ? formAllowedStudentIds : null,
        lock_browser: formLockBrowser,
        eyd_language_evaluation: formEydLanguageEval,
        randomize_per_type: formRandomizePerType,
      };

      if (editingSchedule) {
        await examScheduleApi.updateSchedule(editingSchedule.public_id, payload);
        showToast({
          type: "success",
          title: "Jadwal Ujian Diperbarui",
          message: `Jadwal ujian '${formSchName}' berhasil diperbarui.`,
        });
      } else {
        await examScheduleApi.createSchedule(payload);
        showToast({
          type: "success",
          title: "Jadwal Ujian Dibuat",
          message: `Jadwal ujian '${formSchName}' berhasil didaftarkan.`,
        });
      }

      setIsCreateScheduleOpen(false);
      setEditingSchedule(null);
      setFormSchName("");
      setFormSchProctorId(null);
      await loadPackageSchedules(selectedPackage.public_id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menyimpan Jadwal", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsSubmittingSchedule(false);
    }
  };

  // Action: Open Assign Proctor Modal
  const handleOpenProctorModal = (item: ExamSchedule) => {
    setProctorSchedule(item);
    setSelectedProctorId(item.proctor_id || (teachers.length > 0 ? teachers[0].id : null));
  };

  // Action: Save Proctor
  const handleSaveProctor = async () => {
    if (!proctorSchedule || !selectedProctorId || !selectedPackage) return;
    setIsAssigningProctor(true);
    try {
      await examScheduleApi.assignProctor(proctorSchedule.public_id, {
        proctor_id: selectedProctorId,
      });
      showToast({ type: "success", title: "Pengawas Ditetapkan", message: "Pengawas ujian berhasil ditugaskan." });
      setProctorSchedule(null);
      await loadPackageSchedules(selectedPackage.public_id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menugaskan Pengawas", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsAssigningProctor(false);
    }
  };

  // Action: Delete Schedule Confirm
  const handleDeleteScheduleConfirm = async () => {
    if (!deletingSchedule || !selectedPackage) return;
    setIsDeletingSchedule(true);
    try {
      await examScheduleApi.deleteSchedule(deletingSchedule.public_id);
      showToast({ type: "success", title: "Jadwal Dihapus", message: `Jadwal ujian '${deletingSchedule.name}' telah dihapus.` });
      setDeletingSchedule(null);
      await loadPackageSchedules(selectedPackage.public_id);
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menghapus Jadwal", message: err?.message || "Gagal menghapus." });
    } finally {
      setIsDeletingSchedule(false);
    }
  };

  // Download XLSX template for scheduling
  const handleDownloadTemplate = () => {
    const headers = ["Kelas", "Mata Pelajaran", "Tanggal Ujian", "Jam Mulai", "Jam Selesai", "Kode Pengawas"];
    const samples = [
      {
        Kelas: classes.length > 0 ? classes[0].name : "X-MIPA-1",
        "Mata Pelajaran": "Matematika",
        "Tanggal Ujian": new Date().toISOString().split("T")[0],
        "Jam Mulai": "07:30",
        "Jam Selesai": "09:00",
        "Kode Pengawas": teachers.length > 0 ? (teachers[0].teacher_code || "T-001") : "P-HEBAT",
      },
    ];
    downloadXlsxTemplate(headers, samples, "template-impor-jadwal-ujian", "Template Jadwal");
  };

  // Action: Upload XLSX spreadsheet
  const handleImportXlsx = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedPackage) return;
    e.target.value = "";

    setIsImportingXlsx(true);
    try {
      const rows = await readXlsxFile(file);
      if (rows.length === 0) {
        showToast({ type: "error", title: "File Kosong", message: "File excel yang diupload tidak berisi data." });
        return;
      }
      
      await examScheduleApi.importSchedulesXlsx(selectedPackage.public_id, rows);
      showToast({
        type: "success",
        title: "Impor Sukses",
        message: `${rows.length} jadwal ujian berhasil diimpor ke dalam paket ini.`,
      });
      await loadPackageSchedules(selectedPackage.public_id);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Impor Gagal",
        message: err?.message || "Gagal mengimpor file excel jadwal.",
      });
    } finally {
      setIsImportingXlsx(false);
    }
  };

  // Status Badge Rendering Helper
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "DRAFT":
        return <Badge variant="slate">DRAFT</Badge>;
      case "READY":
        return <Badge variant="emerald">READY (SIAP UJIAN)</Badge>;
      case "SCHEDULED":
        return <Badge variant="indigo">SCHEDULED</Badge>;
      case "LOCKED":
        return <Badge variant="amber">LOCKED</Badge>;
      case "ACTIVE":
        return <Badge variant="emerald">ACTIVE (SEDANG UJIAN)</Badge>;
      case "COMPLETED":
        return <Badge variant="slate">COMPLETED</Badge>;
      case "ARCHIVED":
        return <Badge variant="slate">ARCHIVED</Badge>;
      default:
        return <Badge variant="slate">{status}</Badge>;
    }
  };

  // Detailed Schedules columns
  const scheduleColumns: Column<ExamSchedule>[] = [
    {
      key: "name",
      header: "Nama Ujian & Tanggal",
      render: (item) => (
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-100">{item.name}</span>
            {item.target_type === "SPECIFIC_STUDENTS" && (
              <Badge variant="amber" size="sm">
                SUSULAN ({(item.allowed_student_ids || []).length} Siswa)
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1">
            <span className="flex items-center gap-1 text-indigo-400 font-medium">
              <Calendar className="w-3 h-3" />
              {item.date}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1 font-mono">
              <Clock className="w-3 h-3" />
              {item.start_time} - {item.end_time} ({item.duration_minutes}m)
            </span>
          </div>
        </div>
      ),
    },
    {
      key: "class_subject",
      header: "Kelas & Mapel",
      render: (item) => (
        <div className="min-w-0">
          <span className="text-xs font-bold text-slate-200 block">
            {item.class_name || `Kelas ID #${item.class_id}`}
          </span>
          <span className="text-xs text-indigo-300">
            {item.subject_name || `Mapel ID #${item.subject_id}`}
          </span>
        </div>
      ),
    },
    {
      key: "teachers",
      header: "Pengampu & Pengawas",
      render: (item) => (
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-1 text-slate-300">
            <GraduationCap className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="truncate">Pengampu: {item.teacher_name || "Otomatis"}</span>
          </div>
          <div className="flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className={item.proctor_name ? "text-emerald-300 font-semibold" : "text-amber-400 italic"}>
              Pengawas: {item.proctor_name || "Belum Ditugaskan"}
            </span>
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      width: "140px",
      render: (item) => getStatusBadge(item.status),
    },
    {
      key: "actions",
      header: "Aksi",
      width: "220px",
      render: (item) => {
        const canManage = item.status !== "ACTIVE" && item.status !== "ON_GOING" && item.status !== "COMPLETED";
        return (
          <div className="flex items-center gap-1.5 flex-wrap">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleOpenEditSchedule(item)}
              title="Edit Jadwal Ujian"
              className="text-xs text-indigo-400 hover:bg-indigo-500/15 px-2"
            >
              <Edit2 className="w-3.5 h-3.5 mr-1" />
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleOpenProctorModal(item)}
              title="Tugaskan Pengawas"
              className="text-xs text-emerald-400 hover:bg-emerald-500/15 px-2"
            >
              <UserCheck className="w-3.5 h-3.5 mr-1" />
              Proctor
            </Button>

            {item.status !== "DRAFT" && canManage && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRevertingSchedule({ public_id: item.public_id, title: item.name || (item as any).title || "Jadwal" })}
                title="Batalkan/Ubah ke Status DRAFT"
                className="text-xs text-amber-400 hover:bg-amber-500/15 px-2"
              >
                Draft
              </Button>
            )}

            {canManage ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDeletingSchedule(item)}
                title="Hapus Jadwal"
                className="px-2 hover:bg-rose-500/20"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-400" />
              </Button>
            ) : (
              <div className="px-2 py-1 text-[11px] text-slate-500 flex items-center gap-1 italic" title="Jadwal Berjalan / Selesai">
                <Lock className="w-3 h-3" /> Berjalan
              </div>
            )}
          </div>
        );
      },
    },
  ];

  // Stats boxes counts
  const draftCount = schedules.filter((s) => s.status === "DRAFT").length;
  const activeCount = schedules.filter((s) => s.status === "ACTIVE").length;
  const completedCount = schedules.filter((s) => s.status === "COMPLETED").length;

  return (
    <AppShell activeHref="/admin/exam-schedules" onNavigate={onNavigate}>
      {selectedPackage ? (
        <Breadcrumb
          items={[
            { label: "School Admin", href: "/admin/dashboard" },
            { label: "Paket Jadwal Ujian" },
            { label: selectedPackage.title },
          ]}
        />
      ) : (
        <Breadcrumb
          items={[
            { label: "School Admin", href: "/admin/dashboard" },
            { label: "Paket Jadwal Ujian" },
          ]}
        />
      )}

      {/* ── View 1: Paket List View (selectedPackage === null) ── */}
      {!selectedPackage && (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
                <FileCheck className="w-6 h-6 text-indigo-400 shrink-0" />
                Daftar Paket Jadwal Ujian
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Kelola jadwal ujian sekolah dalam kelompok paket ujian, dipisahkan per Tahun Ajaran.
              </p>
            </div>

            <Button
              variant="primary"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => {
                setFormPackageTitle("");
                setIsCreatePackageOpen(true);
              }}
            >
              Buat Paket Ujian
            </Button>
          </div>

          {/* Filter Bar */}
          <div className="glass-panel p-4 rounded-2xl border border-slate-800 bg-slate-900/50 flex flex-col sm:flex-row items-center gap-4">
            <div className="w-full sm:w-72">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1">Filter Tahun Ajaran</label>
              <Select
                options={[
                  { value: "", label: "Semua Tahun Ajaran" },
                  ...academicYears.map((y) => ({ value: y.id.toString(), label: y.name })),
                ]}
                value={packageFilterYearId?.toString() || ""}
                onChange={(e) => setPackageFilterYearId(e.target.value ? parseInt(e.target.value, 10) : null)}
              />
            </div>
            <div className="flex-1 flex justify-end pt-5 sm:pt-0">
              <Button
                variant="ghost"
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isPackagesLoading ? "animate-spin" : ""}`} />}
                onClick={loadPackages}
                isLoading={isPackagesLoading}
              >
                Muat Ulang
              </Button>
            </div>
          </div>

          {/* Packages Table */}
          <div className="glass-panel border border-slate-800 rounded-2xl overflow-hidden">
            <Table<ExamSchedulePackage>
              isLoading={isPackagesLoading}
              data={packages}
              keyExtractor={(item) => item.public_id}
              emptyMessage="Belum ada paket jadwal ujian terdaftar untuk filter ini. Silakan buat paket baru."
              columns={[
                {
                  key: "title",
                  header: "Judul Paket",
                  render: (item) => (
                    <div>
                      <span className="text-sm font-bold text-slate-100">{item.title}</span>
                      <span className="text-[10px] block text-slate-400 mt-0.5">Dibuat pada: {new Date(item.created_at).toLocaleDateString("id-ID")}</span>
                    </div>
                  ),
                },
                {
                  key: "academic_year",
                  header: "Tahun Ajaran",
                  width: "200px",
                  render: (item) => (
                    <Badge variant="indigo" size="sm">
                      {item.academic_year_name || `ID #${item.academic_year_id}`}
                    </Badge>
                  ),
                },
                {
                  key: "schedules_count",
                  header: "Jumlah Rencana Ujian",
                  width: "180px",
                  render: (item) => (
                    <span className="font-mono text-xs text-slate-300 bg-slate-900 px-2.5 py-1 rounded-md border border-slate-800">
                      {(item.schedules || []).length} Jadwal
                    </span>
                  ),
                },
                {
                  key: "actions",
                  header: "Aksi",
                  width: "200px",
                  align: "right",
                  render: (item) => (
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => loadPackageSchedules(item.public_id)}
                      >
                        Kelola Jadwal
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-rose-400 hover:bg-rose-500/10 px-2"
                        onClick={() => setDeletingPackage(item)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>
      )}

      {/* ── View 2: Detailed Schedules View (selectedPackage !== null) ── */}
      {selectedPackage && (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
            <div>
              <button
                onClick={() => setSelectedPackage(null)}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mb-2"
              >
                <ChevronLeft className="w-4 h-4" />
                Kembali ke Daftar Paket
              </button>
              <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2.5">
                <FileCheck className="w-6 h-6 text-indigo-400 shrink-0" />
                Paket: {selectedPackage.title}
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                Tahun Ajaran: <strong className="text-indigo-300">{selectedPackage.academic_year_name}</strong>
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <Button
                variant="ghost"
                leftIcon={<FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />}
                onClick={handleDownloadTemplate}
                title="Unduh template Excel untuk impor massal jadwal"
              >
                Unduh Template Excel
              </Button>

              <Button
                variant="ghost"
                leftIcon={
                  isImportingXlsx ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                  ) : (
                    <Upload className="w-3.5 h-3.5 text-amber-400" />
                  )
                }
                onClick={() => fileInputRef.current?.click()}
                isLoading={isImportingXlsx}
                title="Impor jadwal massal via file Excel"
              >
                Impor Jadwal XLSX
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={handleImportXlsx}
              />

              <Button
                variant="primary"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => {
                  setEditingSchedule(null);
                  setFormSchClassId(classes.length > 0 ? classes[0].id : null);
                  setFormSchName("");
                  setFormSchDate(new Date().toISOString().split("T")[0]);
                  setFormSchStartTime("08:00");
                  setFormSchEndTime("09:30");
                  setFormSchDuration(90);
                  setFormSchProctorId(null);
                  setIsCreateScheduleOpen(true);
                }}
              >
                Buat Jadwal Manual
              </Button>
            </div>
          </div>

          {/* Stats Box */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
            <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shrink-0">
                <FileCheck className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400">Total Jadwal</p>
                <p className="text-xl font-black text-slate-100">{schedules.length}</p>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0">
                <Timer className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400">Draft / Siap</p>
                <p className="text-xl font-black text-slate-200">{draftCount}</p>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0">
                <CheckCircle className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400">Ujian Aktif</p>
                <p className="text-xl font-black text-emerald-400">{activeCount}</p>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-xl border border-slate-800 bg-slate-900/60 flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/25 flex items-center justify-center text-purple-400 shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-400">Selesai (Arsip)</p>
                <p className="text-xl font-black text-purple-300">{completedCount}</p>
              </div>
            </div>
          </div>

          {/* Search & Class filter */}
          <div className="glass-panel p-4 rounded-2xl border border-slate-800 bg-slate-900/40 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2 flex-1 max-w-md">
              <div className="flex-1">
                <Input
                  placeholder="Cari ujian, kelas, mapel, atau pengawas…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  leftIcon={<Search className="w-4 h-4 text-slate-500" />}
                />
              </div>
              <Button
                variant="ghost"
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isSchedulesLoading ? "animate-spin" : ""}`} />}
                onClick={() => loadPackageSchedules(selectedPackage.public_id)}
                isLoading={isSchedulesLoading}
                className="shrink-0"
              >
                Refresh
              </Button>
            </div>

            <div className="flex items-center gap-2.5">
              <div className="w-40">
                <Select
                  options={[
                    { value: "", label: "Semua Kelas" },
                    ...classes.map((c) => ({ value: c.id.toString(), label: c.name })),
                  ]}
                  value={classFilterId?.toString() || ""}
                  onChange={(e) => setClassFilterId(e.target.value ? parseInt(e.target.value, 10) : null)}
                />
              </div>

              <div className="w-40">
                <Select
                  options={[
                    { value: "", label: "Semua Status" },
                    { value: "DRAFT", label: "Draft" },
                    { value: "READY", label: "Ready (Siap Ujian)" },
                    { value: "SCHEDULED", label: "Scheduled" },
                    { value: "ACTIVE", label: "Active" },
                    { value: "COMPLETED", label: "Completed" },
                  ]}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Mobile View: Cards */}
          <div className="block md:hidden space-y-3">
            {isSchedulesLoading ? (
              <div className="glass-panel p-8 text-center text-xs text-slate-400">Memuat jadwal ujian…</div>
            ) : filteredSchedules.length === 0 ? (
              <div className="glass-panel p-8 text-center text-xs text-slate-400">
                Belum ada jadwal ujian di paket ini. Silakan buat atau impor jadwal baru.
              </div>
            ) : (
              filteredSchedules.map((item) => (
                <div key={item.public_id} className="glass-panel p-4 rounded-xl border border-slate-800 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-bold text-slate-100">{item.name}</h3>
                      <p className="text-xs text-indigo-300 font-semibold mt-0.5">
                        {item.class_name} • {item.subject_name}
                      </p>
                    </div>
                    {getStatusBadge(item.status)}
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{item.date}</span>
                    <span>•</span>
                    <Clock className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{item.start_time} - {item.end_time} ({item.duration_minutes}m)</span>
                  </div>

                  <div className="text-xs text-slate-300 space-y-0.5 pt-1 border-t border-slate-800/60">
                    <p>Pengampu: <strong className="text-slate-100">{item.teacher_name || "Otomatis"}</strong></p>
                    <p>Pengawas: <strong className={item.proctor_name ? "text-emerald-400" : "text-amber-400"}>{item.proctor_name || "Belum Ditugaskan"}</strong></p>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-1 flex-wrap">
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenEditSchedule(item)}
                        className="text-xs text-indigo-400 px-2"
                        title="Edit Jadwal Ujian"
                      >
                        <Edit2 className="w-3.5 h-3.5 mr-1" />
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenProctorModal(item)}
                        className="text-xs text-emerald-400 px-2"
                        title="Tugaskan Pengawas"
                      >
                        <UserCheck className="w-3.5 h-3.5 mr-1" />
                        Proctor
                      </Button>
                    </div>

                    <div className="flex items-center gap-1">
                      {item.status !== "DRAFT" && item.status !== "ACTIVE" && item.status !== "ON_GOING" && item.status !== "COMPLETED" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setRevertingSchedule({ public_id: item.public_id, title: item.name || (item as any).title || "Jadwal" })}
                          className="text-xs text-amber-400 px-2"
                          title="Batalkan ke Draft"
                        >
                          Draft
                        </Button>
                      )}

                      {item.status !== "ACTIVE" && item.status !== "ON_GOING" && item.status !== "COMPLETED" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeletingSchedule(item)}
                          className="text-rose-400 text-xs px-2"
                        >
                          Hapus
                        </Button>
                      ) : (
                        <span className="text-[11px] text-slate-500 italic px-2">Terkunci</span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Desktop Table View */}
          <div className="hidden md:block">
            <Table
              columns={scheduleColumns}
              data={filteredSchedules}
              isLoading={isSchedulesLoading}
              keyExtractor={(item) => item.public_id}
              emptyMessage="Belum ada jadwal ujian di paket ini. Silakan buat atau impor jadwal baru."
            />
          </div>
        </div>
      )}

      {/* ── Modal: Buat Paket Ujian Baru ── */}
      <Modal
        isOpen={isCreatePackageOpen}
        onClose={() => setIsCreatePackageOpen(false)}
        title="Buat Paket Jadwal Ujian Baru"
        maxWidth="md"
      >
        <form onSubmit={handleCreatePackageSubmit} className="space-y-4">
          <Input
            label="Nama / Judul Paket (Wajib)"
            placeholder="Contoh: Penilaian Akhir Semester (PAS) Ganjil"
            value={formPackageTitle}
            onChange={(e) => setFormPackageTitle(e.target.value)}
            required
          />

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">Tahun Ajaran Terkait (Wajib)</label>
            <Select
              options={academicYears.map((y) => ({ value: y.id.toString(), label: y.name }))}
              value={formPackageYearId?.toString() || ""}
              onChange={(e) => setFormPackageYearId(parseInt(e.target.value, 10))}
              required
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button type="button" variant="ghost" onClick={() => setIsCreatePackageOpen(false)}>
              Batal
            </Button>
            <Button type="submit" variant="primary" isLoading={isCreatingPackage}>
              Buat Paket
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Hapus Paket Ujian ── */}
      <Modal
        isOpen={!!deletingPackage}
        onClose={() => setDeletingPackage(null)}
        title="Konfirmasi Hapus Paket Ujian"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3.5 bg-rose-950/30 border border-rose-500/30 rounded-xl text-xs text-rose-300">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-slate-100">Apakah Anda yakin ingin menghapus paket ini?</p>
              <p className="mt-1 text-slate-400">
                Paket <strong>{deletingPackage?.title}</strong> dan seluruh jadwal ujian rinci di dalamnya akan terhapus secara permanen. Tindakan ini tidak dapat dibatalkan.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setDeletingPackage(null)}>
              Batal
            </Button>
            <Button variant="danger" isLoading={isDeletingPackage} onClick={handleDeletePackageConfirm}>
              Hapus Paket Permanen
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Buat Jadwal Ujian Manual ── */}
      <Modal
        isOpen={isCreateScheduleOpen}
        onClose={() => setIsCreateScheduleOpen(false)}
        title={editingSchedule ? `Edit Jadwal Ujian: ${editingSchedule.name}` : "Buat Jadwal Ujian Baru (Manual)"}
        maxWidth="lg"
      >
        <form onSubmit={handleCreateScheduleSubmit} className="space-y-4">
          <Input
            label="Nama / Judul Ujian (Wajib)"
            placeholder="Contoh: PAS Ganjil - Matematika X"
            value={formSchName}
            onChange={(e) => setFormSchName(e.target.value)}
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Semester (Wajib)</label>
              <Select
                options={semesters.map((s) => ({ value: s.id.toString(), label: s.display_name }))}
                value={formSchSemesterId?.toString() || ""}
                onChange={(e) => setFormSchSemesterId(parseInt(e.target.value, 10))}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Kelas Rombel (Wajib)</label>
              <Select
                options={classes.map((c) => ({ value: c.id.toString(), label: c.name }))}
                value={formSchClassId?.toString() || ""}
                onChange={(e) => setFormSchClassId(parseInt(e.target.value, 10))}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Mata Pelajaran (Wajib)</label>
              <Select
                options={formSchClassSubjects.map((cs) => ({
                  value: cs.subject_id.toString(),
                  label: `${cs.subject_name} (${cs.subject_code})`,
                }))}
                value={formSchSubjectId?.toString() || ""}
                onChange={(e) => setFormSchSubjectId(parseInt(e.target.value, 10))}
                required
              />
            </div>
          </div>

          {/* Automatic Teacher Display Box */}
          <div className="p-3 bg-indigo-950/30 border border-indigo-500/30 rounded-xl text-xs flex items-center justify-between animate-fade-in">
            <span className="text-slate-400">Guru Pengampu Terverifikasi:</span>
            <span className="font-bold text-indigo-300">
              {selectedSchSubjectObj?.teacher_name || "Otomatis ditarik dari struktur kelas"}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <Input
              type="date"
              label="Tanggal Ujian"
              value={formSchDate}
              onChange={(e) => setFormSchDate(e.target.value)}
              required
            />

            <Input
              type="time"
              label="Waktu Mulai"
              value={formSchStartTime}
              onChange={(e) => handleStartTimeChange(e.target.value)}
              required
            />

            <div>
              <Input
                type="time"
                label="Waktu Selesai"
                value={formSchEndTime}
                onChange={(e) => setFormSchEndTime(e.target.value)}
                required
              />
              <p className="text-[10px] text-slate-500 mt-1">
                ⚡ Otomatis ter-set (Waktu Mulai + Durasi)
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <Input
              type="number"
              label="Durasi Pengerjaan (Menit)"
              value={formSchDuration.toString()}
              onChange={(e) => handleDurationChange(parseInt(e.target.value, 10) || 60)}
              required
            />

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Pengawas / Proctor (Opsional)</label>
              <Select
                options={[
                  { value: "", label: "Tugaskan Nanti" },
                  ...teachers.map((t) => ({
                    value: t.id.toString(),
                    label: `${t.name || t.username} (${t.username})`,
                  })),
                ]}
                value={formSchProctorId?.toString() || ""}
                onChange={(e) => setFormSchProctorId(e.target.value ? parseInt(e.target.value, 10) : null)}
              />
            </div>
          </div>

          {/* Target Peserta: Reguler vs Ujian Susulan */}
          <div className="space-y-2.5 p-3.5 bg-slate-950/40 rounded-xl border border-slate-800">
            <label className="block text-xs font-bold text-slate-200">
              Target Peserta Ujian
            </label>
            <div className="flex items-center gap-4 text-xs">
              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="radio"
                  name="target_type"
                  checked={formTargetType === "ALL_CLASS"}
                  onChange={() => setFormTargetType("ALL_CLASS")}
                  className="accent-indigo-500"
                />
                <span>Reguler (Seluruh Kelas)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-amber-300 font-semibold">
                <input
                  type="radio"
                  name="target_type"
                  checked={formTargetType === "SPECIFIC_STUDENTS"}
                  onChange={() => setFormTargetType("SPECIFIC_STUDENTS")}
                  className="accent-amber-500"
                />
                <span>Ujian Susulan / Remedial (Siswa Tertentu)</span>
              </label>
            </div>

            {formTargetType === "SPECIFIC_STUDENTS" && (
              <div className="mt-3 space-y-2 border-t border-slate-800 pt-3 animate-fade-in">
                <p className="text-[11px] text-slate-400">
                  Pilih siswa yang berhak mengakses & mengikuti ujian susulan ini:
                </p>

                {loadingClassStudents ? (
                  <p className="text-xs text-slate-400 py-2">Memuat daftar siswa kelas…</p>
                ) : classStudents.length === 0 ? (
                  <p className="text-xs text-amber-400 py-2 italic">Belum ada siswa terdaftar di kelas ini.</p>
                ) : (
                  <div className="max-h-40 overflow-y-auto space-y-1.5 pr-1 divide-y divide-slate-800/40">
                    {classStudents.map((st) => {
                      const isChecked = formAllowedStudentIds.includes(st.student_id);
                      return (
                        <label
                          key={st.student_id}
                          className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-800/40 cursor-pointer text-xs"
                        >
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {
                                setFormAllowedStudentIds((prev) =>
                                  prev.includes(st.student_id)
                                    ? prev.filter((id) => id !== st.student_id)
                                    : [...prev, st.student_id]
                                );
                              }}
                              className="accent-amber-500"
                            />
                            <span className="font-bold text-slate-200">{st.student_name || st.student_username}</span>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400">NISN: {st.nisn || "—"}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button type="button" variant="ghost" onClick={() => setIsCreateScheduleOpen(false)}>
              Batal
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmittingSchedule}>
              {editingSchedule ? "Simpan Perubahan" : "Jadwalkan Ujian"}
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Modal: Tugaskan Pengawas (Proctor) ── */}
      <Modal
        isOpen={!!proctorSchedule}
        onClose={() => setProctorSchedule(null)}
        title={`Tugaskan Pengawas: ${proctorSchedule?.name}`}
        maxWidth="md"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-400">
            Pilih guru yang bertugas sebagai <strong>Pengawas Ujian (Proctor)</strong> untuk memverifikasi kehadiran dan mengawasi ujian CBT kelas ini.
          </p>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">Pilih Guru Pengawas</label>
            <Select
              options={teachers.map((t) => ({
                value: t.id.toString(),
                label: `${t.name || t.username} (${t.username})${t.nip ? ` • NIP: ${t.nip}` : ""}${t.teacher_code ? ` • Kode: ${t.teacher_code}` : ""}`,
              }))}
              value={selectedProctorId?.toString() || ""}
              onChange={(e) => setSelectedProctorId(parseInt(e.target.value, 10))}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button variant="ghost" onClick={() => setProctorSchedule(null)}>
              Batal
            </Button>
            <Button variant="primary" isLoading={isAssigningProctor} onClick={handleSaveProctor}>
              Simpan Penugasan
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Modal: Hapus Rencana Jadwal Ujian ── */}
      <Modal
        isOpen={!!deletingSchedule}
        onClose={() => setDeletingSchedule(null)}
        title="Konfirmasi Hapus Jadwal Ujian"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3.5 bg-rose-950/30 border border-rose-500/30 rounded-xl text-xs text-rose-300">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-slate-100">Hapus jadwal ujian draft ini?</p>
              <p className="mt-1 text-slate-400">
                Jadwal <strong>{deletingSchedule?.name}</strong> akan dihapus. Tindakan ini tidak dapat dibatalkan.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setDeletingSchedule(null)}>
              Batal
            </Button>
            <Button variant="danger" isLoading={isDeletingSchedule} onClick={handleDeleteScheduleConfirm}>
              Hapus Jadwal
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Custom Confirmation MessageBox: Revert Schedule to Draft ── */}
      <MessageBox
        isOpen={revertingSchedule !== null}
        onClose={() => setRevertingSchedule(null)}
        type="question"
        title="Ubah Status Jadwal ke Draft"
        message={
          <div>
            Apakah Anda yakin ingin mengembalikan jadwal <strong>"{revertingSchedule?.title}"</strong> ke status <strong>DRAFT</strong>?
            <p className="text-[11px] text-slate-400 mt-1">
              Siswa tidak dapat mengakses ujian ini sementara waktu sampai status dikembalikan ke ACTIVE.
            </p>
          </div>
        }
        confirmText="Ubah ke Draft"
        cancelText="Batal"
        onConfirm={handleConfirmRevertSchedule}
        isLoading={isRevertingSchedule}
        confirmVariant="primary"
      />
    </AppShell>
  );
};
