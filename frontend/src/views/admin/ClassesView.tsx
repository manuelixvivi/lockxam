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
import type { ClassEntity } from "../../api/class";
import { academicApi } from "../../api/academic";
import type { AcademicYear } from "../../api/academic";
import { useAuth } from "../../context/AuthContext";
import { getGradeOptionsForSchool } from "../../utils/gradeLevels";
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
  Users,
  BookOpen,
  Download,
  CalendarDays,
} from "lucide-react";
import { ClassStructureView } from "./ClassStructureView";

interface ClassesViewProps {
  onNavigate?: (path: string) => void;
}

export const ClassesView: React.FC<ClassesViewProps> = ({ onNavigate }) => {
  const { showToast } = useToast();
  const { user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const gradeOptions = useMemo(() => {
    return getGradeOptionsForSchool(user?.school_level_code);
  }, [user?.school_level_code]);

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
  const [formGradeLevel, setFormGradeLevel] = useState<string>(gradeOptions[0]?.value || "VII");
  const [isSubmittingClass, setIsSubmittingClass] = useState<boolean>(false);

  // Delete Target Class
  const [deletingClass, setDeletingClass] = useState<ClassEntity | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // ── FULL PAGE CLASS STRUCTURE VIEW ──
  const [detailClass, setDetailClass] = useState<ClassEntity | null>(null);

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
        loadClasses(activeYear.id);
      } else {
        setSelectedYearId(null);
        loadClasses(null);
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
    if (selectedYearId !== null) {
      loadClasses(selectedYearId);
    }
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
    setFormGradeLevel(gradeOptions[0]?.value || "VII");
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

  const handleOpenDetailFullPage = (cls: ClassEntity) => {
    setDetailClass(cls);
  };

  const handleCloseDetailFullPage = () => {
    setDetailClass(null);
    if (selectedYearId) {
      loadClasses(selectedYearId);
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
      studentSheet.forEach((row, idx) => {
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
            row_num: idx + 2,
          });
        }
      });

      // Parse Sheet 3: Mapel_Per_Kelas / Mapel
      const subjectSheet = sheetsData["Mapel_Per_Kelas"] || sheetsData["Mapel"] || [];
      subjectSheet.forEach((row, idx) => {
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
            row_num: idx + 2,
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
            sheetRows.forEach((row, idx) => {
              const nisn = strVal(row["NISN"]);
              const nis = strVal(row["NIS"]);
              const stUname = strVal(row["Username Siswa"] || row["Username"]);
              if (nisn || nis || stUname) {
                parsedClassesMap[clsName].students.push({ nisn, nis, username: stUname, row_num: idx + 2 });
              }

              const sCode = strVal(row["Kode Mapel"] || row["Mapel"]);
              const tCode = strVal(row["Kode Guru"] || row["NIP Guru"] || row["Username Guru"]);
              if (sCode) {
                parsedClassesMap[clsName].subjects.push({ subject_code: sCode, teacher_code: tCode, row_num: idx + 2 });
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

  if (detailClass) {
    return (
      <ClassStructureView
        classEntity={detailClass}
        academicYearName={currentYearObj?.name}
        onClose={handleCloseDetailFullPage}
        onNavigate={onNavigate}
      />
    );
  }

  return (
    <AppShell activeHref="/admin/classes" onNavigate={onNavigate}>
      <Breadcrumb
        items={[
          { label: "School Admin", href: "/admin/dashboard" },
          { label: "Manajemen Kelas & Rombel" },
        ]}
      />

      {/* ── FULL PAGE VIEW 2: MASTER CLASS LIST ── */}
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
                options={gradeOptions}
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
