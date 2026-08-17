import React, { useEffect, useState } from "react";
import {
  CalendarDays,
  Plus,
  Play,
  Archive,
  Lock,
  Trash2,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import type { SelectOption } from "../../components/ui/Select";

import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { Badge } from "../../components/ui/Badge";
import { Table } from "../../components/ui/Table";
import { UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { academicApi } from "../../api/academic";
import type { AcademicYear } from "../../api/academic";
import type { AppApiError } from "../../api/client";

export const AcademicYearsView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {

  const toast = useToast();

  const [years, setYears] = useState<AcademicYear[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Create Year Modal State
  const [isCreateYearOpen, setIsCreateYearOpen] = useState<boolean>(false);
  const [yearName, setYearName] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [isSubmittingYear, setIsSubmittingYear] = useState<boolean>(false);
  const [yearFormError, setYearFormError] = useState<string | null>(null);

  // Create Semester Modal State
  const [isCreateSemesterOpen, setIsCreateSemesterOpen] = useState<boolean>(false);
  const [selectedYearId, setSelectedYearId] = useState<number | null>(null);
  const [semesterCode, setSemesterCode] = useState<string>("ODD");
  const [semesterName, setSemesterName] = useState<string>("Semester Ganjil");
  const [isSubmittingSemester, setIsSubmittingSemester] = useState<boolean>(false);
  const [semesterFormError, setSemesterFormError] = useState<string | null>(null);

  const fetchYears = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await academicApi.getAcademicYears();
      setYears(data);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setError(apiErr.message || "Gagal memuat data tahun akademik.");
      toast.error("Gagal Memuat Data", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchYears();
  }, []);

  const handleCreateYear = async (e: React.FormEvent) => {
    e.preventDefault();
    setYearFormError(null);

    if (!yearName.trim() || !startDate || !endDate) {
      setYearFormError("Nama tahun akademik, tanggal mulai, dan tanggal selesai wajib diisi.");
      return;
    }

    setIsSubmittingYear(true);
    try {
      await academicApi.createAcademicYear({
        name: yearName.trim(),
        start_date: new Date(startDate).toISOString(),
        end_date: new Date(endDate).toISOString(),
      });

      toast.success("Tahun Akademik Dibuat", `Tahun Akademik ${yearName} berhasil didaftarkan (PLANNED).`);
      setIsCreateYearOpen(false);
      setYearName("");
      setStartDate("");
      setEndDate("");
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setYearFormError(apiErr.message || "Gagal membuat tahun akademik.");
    } finally {
      setIsSubmittingYear(false);
    }
  };

  const handleActivateYear = async (year: AcademicYear) => {
    if (
      !window.confirm(
        `Apakah Anda yakin ingin mengaktifkan (Rollover) Tahun Akademik ${year.name}? Tahun aktif sebelumnya akan ditutup.`
      )
    ) {
      return;
    }

    try {
      await academicApi.rolloverAcademicYear(year.public_id);
      toast.success("Tahun Akademik Aktif", `Tahun Akademik ${year.name} sekarang dalam status ACTIVE.`);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Mengaktifkan", apiErr.message);
    }
  };

  const handleCloseYear = async (year: AcademicYear) => {
    if (
      !window.confirm(
        `Apakah Anda yakin ingin menutup Tahun Akademik ${year.name}? Status akan menjadi PENDING_ARCHIVE.`
      )
    ) {
      return;
    }

    try {
      await academicApi.closeAcademicYear(year.public_id);
      toast.success("Tahun Akademik Ditutup", `Tahun Akademik ${year.name} berstatus PENDING_ARCHIVE.`);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Penutupan", apiErr.message);
    }
  };

  const handleFinalizeArchive = async (year: AcademicYear) => {
    if (
      !window.confirm(
        `PERINGATAN: Mengarsipkan Tahun Akademik ${year.name} akan membuat seluruh data menjadi READ-ONLY secara permanen. Lanjutkan?`
      )
    ) {
      return;
    }

    try {
      await academicApi.finalizeArchiveAcademicYear(year.public_id);
      toast.success("Tahun Akademik Diarsipkan", `Tahun Akademik ${year.name} sekarang ARCHIVED (Read-Only).`);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Mengarsipkan", apiErr.message);
    }
  };

  const handleDeleteYear = async (year: AcademicYear) => {
    if (!window.confirm(`Apakah Anda yakin ingin menghapus rencana Tahun Akademik ${year.name}?`)) {
      return;
    }

    try {
      await academicApi.deleteAcademicYear(year.public_id);
      toast.success("Dihapus", `Rencana Tahun Akademik ${year.name} telah dihapus.`);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Menghapus", apiErr.message);
    }
  };

  const handleCreateSemester = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedYearId) return;
    setSemesterFormError(null);

    setIsSubmittingSemester(true);
    try {
      await academicApi.createAcademicSemester({
        academic_year_id: selectedYearId,
        code: semesterCode,
        display_name: semesterName,
      });

      toast.success("Semester Ditambahkan", `Semester ${semesterName} berhasil dibuat.`);
      setIsCreateSemesterOpen(false);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setSemesterFormError(apiErr.message || "Gagal membuat semester.");
    } finally {
      setIsSubmittingSemester(false);
    }
  };

  const handleActivateSemester = async (semesterPublicId: string, semesterNameStr: string) => {
    try {
      await academicApi.activateAcademicSemester(semesterPublicId);
      toast.success("Semester Aktif", `Semester ${semesterNameStr} berhasil diaktifkan.`);
      fetchYears();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Mengaktifkan Semester", apiErr.message);
    }
  };

  const activeYear = years.find((y) => y.status === "ACTIVE");

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return "emerald";
      case "PLANNED":
        return "indigo";
      case "PENDING_ARCHIVE":
        return "amber";
      case "ARCHIVED":
        return "slate";
      default:
        return "indigo";
    }
  };

  const semesterCodeOptions: SelectOption[] = [
    { value: "ODD", label: "Semester Ganjil (ODD)" },
    { value: "EVEN", label: "Semester Genap (EVEN)" },
  ];

  return (
    <AppShell activeHref="/admin/academic-years" onNavigate={onNavigate}>

      <RoleGuard allowedRoles={[UserRole.SCHOOL_ADMIN]}>
        <Breadcrumb items={[{ label: "School Admin", href: "/admin/dashboard" }, { label: "Tahun Akademik" }]} />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat data tahun akademik..." />
          </div>
        ) : error ? (
          <div className="glass-panel p-8 text-center space-y-4 border-red-500/30">
            <p className="text-sm text-red-400 font-medium">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchYears}>
              Coba Lagi
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">MANAJEMEN PERIODE</Badge>
                  {activeYear ? (
                    <Badge variant="emerald">AKTIF: {activeYear.name}</Badge>
                  ) : (
                    <Badge variant="amber">BELUM ADA TAHUN AKTIF</Badge>
                  )}
                </div>
                <h2 className="text-2xl font-black text-slate-100">Manajemen Tahun Akademik & Semester</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Atur siklus tahun pelajaran (PLANNED ➔ ACTIVE ➔ PENDING_ARCHIVE ➔ ARCHIVED 🔒).
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={() => setIsCreateYearOpen(true)}
                >
                  Buat Tahun Akademik Baru
                </Button>
              </div>
            </div>

            {/* Active Year Summary Banner */}
            {activeYear && (
              <div className="glass-panel p-6 border-emerald-500/30 space-y-3 bg-emerald-950/10">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5" />
                    <span>Tahun Akademik Berjalan Saat Ini</span>
                  </div>
                  <Badge variant="emerald">STATUS: ACTIVE</Badge>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4 text-xs">
                  <div>
                    <span className="text-slate-400">Nama Periode:</span>
                    <div className="font-bold text-slate-100 text-sm sm:text-base">{activeYear.name}</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Masa Berlaku:</span>
                    <div className="font-semibold text-slate-200 text-xs sm:text-sm">
                      {new Date(activeYear.start_date).toLocaleDateString("id-ID")} -{" "}
                      {new Date(activeYear.end_date).toLocaleDateString("id-ID")}
                    </div>
                  </div>
                  <div className="col-span-2 md:col-span-1">
                    <span className="text-slate-400">Semester Terdaftar:</span>
                    <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                      {activeYear.semesters && activeYear.semesters.length > 0 ? (
                        activeYear.semesters.map((s) => (
                          <Badge key={s.id} variant={s.is_active ? "emerald" : "indigo"}>
                            {s.display_name} {s.is_active && "✓"}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-slate-500">Belum ada semester</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Academic Years List */}
            <div className="glass-panel p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-slate-100 font-bold text-sm">
                  <CalendarDays className="w-4 h-4 text-indigo-400" />
                  <span>Daftar Tahun Akademik Sekolah</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">Total {years.length} Periode</span>
              </div>

              {/* ── Mobile card list (hidden on md+) ── */}
              <div className="block md:hidden space-y-3">
                {isLoading ? (
                  <p className="text-center text-xs text-slate-500 py-8">Memuat data...</p>
                ) : years.length === 0 ? (
                  <p className="text-center text-xs text-slate-500 py-8">
                    Belum ada tahun akademik. Klik 'Buat Tahun Akademik Baru'.
                  </p>
                ) : (
                  years.map((item) => (
                    <div
                      key={item.id}
                      className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3"
                    >
                      {/* Row 1: name + status badge */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-slate-100 leading-tight">{item.name}</p>
                          <p className="text-[11px] text-slate-500 mt-0.5 font-mono">ID: #{item.id}</p>
                        </div>
                        <Badge variant={getStatusBadgeVariant(item.status)}>{item.status}</Badge>
                      </div>

                      {/* Row 2: date range */}
                      <div className="flex items-center gap-1.5 text-[11px] text-slate-400 border-t border-slate-800 pt-2">
                        <Clock className="w-3 h-3 shrink-0" />
                        <span>
                          {new Date(item.start_date).toLocaleDateString("id-ID")} —{" "}
                          {new Date(item.end_date).toLocaleDateString("id-ID")}
                        </span>
                      </div>

                      {/* Row 3: semesters */}
                      <div className="flex flex-wrap items-center gap-1.5">
                        {item.semesters && item.semesters.length > 0 ? (
                          item.semesters.map((s) => {
                            const active = s.status === "ACTIVE" || s.is_active;
                            return (
                              <button
                                key={s.id}
                                disabled={item.status === "ARCHIVED" || active}
                                onClick={() => handleActivateSemester(s.public_id, s.display_name)}
                                className={`px-2 py-1 text-[11px] rounded-lg font-medium transition-all ${
                                  active
                                    ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/50"
                                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                                }`}
                              >
                                {s.display_name} {active && "✓"}
                              </button>
                            );
                          })
                        ) : (
                          <span className="text-[11px] text-slate-500">Belum ada semester</span>
                        )}
                        {item.status !== "ARCHIVED" && (
                          <button
                            onClick={() => {
                              setSelectedYearId(item.id);
                              setIsCreateSemesterOpen(true);
                            }}
                            className="px-2 py-1 text-[11px] rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/40 border border-indigo-500/30"
                          >
                            + Tambah
                          </button>
                        )}
                      </div>

                      {/* Row 4: action buttons */}
                      <div className="flex items-center gap-2 pt-1 border-t border-slate-800">
                        {item.status === "PLANNED" && (
                          <>
                            <Button
                              variant="primary"
                              size="sm"
                              leftIcon={<Play className="w-3.5 h-3.5" />}
                              onClick={() => handleActivateYear(item)}
                              className="flex-1"
                            >
                              Aktifkan
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                              onClick={() => handleDeleteYear(item)}
                            />
                          </>
                        )}
                        {item.status === "ACTIVE" && (
                          <Button
                            variant="secondary"
                            size="sm"
                            leftIcon={<Clock className="w-3.5 h-3.5 text-amber-400" />}
                            onClick={() => handleCloseYear(item)}
                            className="flex-1"
                          >
                            Tutup Periode
                          </Button>
                        )}
                        {item.status === "PENDING_ARCHIVE" && (
                          <Button
                            variant="danger"
                            size="sm"
                            leftIcon={<Archive className="w-3.5 h-3.5" />}
                            onClick={() => handleFinalizeArchive(item)}
                            className="flex-1"
                          >
                            Finalisasi Arsip
                          </Button>
                        )}
                        {item.status === "ARCHIVED" && (
                          <span className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                            <Lock className="w-3.5 h-3.5" /> Read-Only
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* ── Desktop full table (hidden on mobile) ── */}
              <div className="hidden md:block">
                <Table
                  columns={[
                    {
                      key: "name",
                      header: "Tahun Akademik",
                      render: (item: AcademicYear) => (
                        <div>
                          <div className="font-bold text-slate-100">{item.name}</div>
                          <div className="text-[11px] text-slate-400 font-mono">ID: #{item.id}</div>
                        </div>
                      ),
                    },
                    {
                      key: "dates",
                      header: "Tanggal Pelaksanaan",
                      render: (item: AcademicYear) => (
                        <div className="text-xs text-slate-300 font-mono">
                          {new Date(item.start_date).toLocaleDateString("id-ID")} —{" "}
                          {new Date(item.end_date).toLocaleDateString("id-ID")}
                        </div>
                      ),
                    },
                    {
                      key: "status",
                      header: "Status Lifecycle",
                      width: "140px",
                      render: (item: AcademicYear) => (
                        <Badge variant={getStatusBadgeVariant(item.status)}>{item.status}</Badge>
                      ),
                    },
                    {
                      key: "semesters",
                      header: "Semester",
                      render: (item: AcademicYear) => (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {item.semesters && item.semesters.length > 0 ? (
                            item.semesters.map((s) => {
                              const active = s.status === "ACTIVE" || s.is_active;
                              return (
                                <button
                                  key={s.id}
                                  disabled={item.status === "ARCHIVED" || active}
                                  onClick={() => handleActivateSemester(s.public_id, s.display_name)}
                                  className={`px-2 py-1 text-[11px] rounded-lg font-medium transition-all ${
                                    active
                                      ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/50"
                                      : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                                  }`}
                                >
                                  {s.display_name} {active && "(Aktif)"}
                                </button>
                              );
                            })
                          ) : (
                            <span className="text-xs text-slate-500">Belum ada</span>
                          )}

                          {item.status !== "ARCHIVED" && (
                            <button
                              onClick={() => {
                                setSelectedYearId(item.id);
                                setIsCreateSemesterOpen(true);
                              }}
                              className="px-2 py-1 text-[11px] rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/40 border border-indigo-500/30"
                            >
                              + Tambah
                            </button>
                          )}
                        </div>
                      ),
                    },
                    {
                      key: "actions",
                      header: "Aksi Transisi",
                      width: "220px",
                      render: (item: AcademicYear) => (
                        <div className="flex items-center gap-2">
                          {item.status === "PLANNED" && (
                            <>
                              <Button
                                variant="primary"
                                size="sm"
                                leftIcon={<Play className="w-3.5 h-3.5" />}
                                onClick={() => handleActivateYear(item)}
                              >
                                Aktifkan
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                                onClick={() => handleDeleteYear(item)}
                              />
                            </>
                          )}

                          {item.status === "ACTIVE" && (
                            <Button
                              variant="secondary"
                              size="sm"
                              leftIcon={<Clock className="w-3.5 h-3.5 text-amber-400" />}
                              onClick={() => handleCloseYear(item)}
                            >
                              Tutup Periode
                            </Button>
                          )}

                          {item.status === "PENDING_ARCHIVE" && (
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<Archive className="w-3.5 h-3.5" />}
                              onClick={() => handleFinalizeArchive(item)}
                            >
                              Finalisasi Arsip
                            </Button>
                          )}

                          {item.status === "ARCHIVED" && (
                            <span className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                              <Lock className="w-3.5 h-3.5" /> Read-Only
                            </span>
                          )}
                        </div>
                      ),
                    },
                  ]}
                  data={years}
                  keyExtractor={(item) => item.id.toString()}
                />
              </div>
            </div>
          </div>
        )}

        {/* Modal: Buat Tahun Akademik Baru */}
        <Modal
          isOpen={isCreateYearOpen}
          onClose={() => {
            setIsCreateYearOpen(false);
            setYearFormError(null);
          }}
          title="Buat Tahun Akademik Baru"
          subtitle="Tahun akademik yang baru dibuat akan berstatus PLANNED sebelum diaktifkan."
          maxWidth="md"
        >
          <form onSubmit={handleCreateYear} className="space-y-4">
            {yearFormError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {yearFormError}
              </div>
            )}

            <Input
              label="Nama Tahun Akademik"
              placeholder="Contoh: 2026/2027"
              value={yearName}
              onChange={(e) => setYearName(e.target.value)}
              leftIcon={<CalendarDays className="w-4 h-4" />}
              required
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Tanggal Mulai"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />

              <Input
                label="Tanggal Selesai"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsCreateYearOpen(false);
                  setYearFormError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isSubmittingYear}>
                Simpan Rencana Periode
              </Button>
            </div>
          </form>
        </Modal>

        {/* Modal: Tambah Semester */}
        <Modal
          isOpen={isCreateSemesterOpen}
          onClose={() => {
            setIsCreateSemesterOpen(false);
            setSemesterFormError(null);
          }}
          title="Tambah Semester"
          subtitle="Daftarkan semester baru untuk tahun akademik terpilih."
          maxWidth="md"
        >
          <form onSubmit={handleCreateSemester} className="space-y-4">
            {semesterFormError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {semesterFormError}
              </div>
            )}

            <Select
              label="Kode Jenis Semester"
              options={semesterCodeOptions}
              value={semesterCode}
              onChange={(e) => {
                setSemesterCode(e.target.value);
                setSemesterName(e.target.value === "ODD" ? "Semester Ganjil" : "Semester Genap");
              }}
              required
            />

            <Input
              label="Nama Tampilan Semester"
              placeholder="Contoh: Semester Ganjil 2026"
              value={semesterName}
              onChange={(e) => setSemesterName(e.target.value)}
              required
            />

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsCreateSemesterOpen(false);
                  setSemesterFormError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isSubmittingSemester}>
                Simpan Semester
              </Button>
            </div>
          </form>
        </Modal>
      </RoleGuard>
    </AppShell>
  );
};
