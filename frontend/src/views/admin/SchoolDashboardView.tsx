import React, { useEffect, useState } from "react";
import {
  Users,
  GraduationCap,
  CalendarDays,
  CreditCard,
  ArrowUpRight,
  BookOpen,
  FileCheck,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Table } from "../../components/ui/Table";
import { Spinner } from "../../components/ui/Spinner";
import { UserRole } from "../../context/AuthContext";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { schoolApi, type SchoolProfile, type SchoolDashboardSummary } from "../../api/school";
import { teacherApi, type TeacherAccount } from "../../api/teacher";
import { academicApi, type AcademicYear } from "../../api/academic";
import type { AppApiError } from "../../api/client";

export const SchoolDashboardView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {
  const { user } = useAuth();
  const toast = useToast();

  const [school, setSchool] = useState<SchoolProfile | null>(null);
  const [summary, setSummary] = useState<SchoolDashboardSummary | null>(null);
  const [teachers, setTeachers] = useState<TeacherAccount[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchDashboardData = async () => {
    if (!user?.school_id) return;
    setIsLoading(true);
    try {
      const [schoolData, summaryData, teachersData, academicData] = await Promise.all([
        schoolApi.getSchoolProfile(user.school_id),
        schoolApi.getDashboardSummary(user.school_id),
        teacherApi.listTeachers(5),
        academicApi.getAcademicYears(),
      ]);
      setSchool(schoolData);
      setSummary(summaryData);
      setTeachers(teachersData);
      setAcademicYears(academicData);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memuat Dashboard Sekolah", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [user?.school_id]);

  const activeAcademicYear = academicYears.find((y) => y.status === "ACTIVE");

  return (
    <AppShell activeHref="/admin/dashboard" onNavigate={onNavigate}>
      <RoleGuard allowedRoles={[UserRole.SCHOOL_ADMIN]}>
        <Breadcrumb items={[{ label: "School Admin Workspace", href: "#" }, { label: "Dashboard Sekolah" }]} />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat metrik dashboard sekolah..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">SCHOOL ADMIN</Badge>
                  <Badge variant={school?.is_active ? "emerald" : "amber"}>
                    {school?.is_active ? "PORTAL AKTIF" : "PORTAL DIBATASI"}
                  </Badge>
                </div>
                <h2 className="text-2xl font-black text-slate-100">
                  Selamat Datang di Portal, {school?.name || "Sekolah Anda"}
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Kelola tahun ajaran, pendaftaran guru/siswa, dan pemantauan aktivitas sekolah di pusat kendali Equigrade.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<FileCheck className="w-4 h-4" />}
                  onClick={() => onNavigate && onNavigate("/admin/exam-schedules")}
                >
                  Jadwal Ujian
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<BookOpen className="w-4 h-4 text-purple-400" />}
                  onClick={() => onNavigate && onNavigate("/admin/subjects")}
                >
                  Mata Pelajaran
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<GraduationCap className="w-4 h-4 text-emerald-400" />}
                  onClick={() => onNavigate && onNavigate("/admin/classes")}
                >
                  Kelas Rombel
                </Button>
              </div>
            </div>

            {/* Metrics Cards Grid - 2 columns on mobile, 4 columns on large screens */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {/* Total Teachers */}
              <div className="glass-panel p-5 space-y-2 border-indigo-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Guru</span>
                  <Users className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="text-3xl font-black text-slate-100">{summary?.total_teachers ?? 0}</div>
                <p className="text-[11px] text-slate-500 font-medium">Akun terdaftar resmi</p>
              </div>

              {/* Total Students */}
              <div className="glass-panel p-5 space-y-2 border-emerald-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Siswa</span>
                  <GraduationCap className="w-5 h-5 text-emerald-400" />
                </div>
                <div className="text-3xl font-black text-emerald-400">{summary?.total_students ?? 0}</div>
                <p className="text-[11px] text-slate-500 font-medium">Terdaftar di ujian central</p>
              </div>

              {/* Active Academic Year */}
              <div className="glass-panel p-5 space-y-2 border-amber-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Tahun Akademik</span>
                  <CalendarDays className="w-5 h-5 text-amber-400" />
                </div>
                <div className="text-lg font-bold text-slate-100 truncate" title={activeAcademicYear?.name || "Belum Aktif"}>
                  {activeAcademicYear?.name || "Belum Aktif"}
                </div>
                <p className="text-[11px] text-slate-500 font-medium">Periode aktif saat ini</p>
              </div>

              {/* Subscription Status */}
              <div className="glass-panel p-5 space-y-2 border-purple-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Status Lisensi</span>
                  <CreditCard className="w-5 h-5 text-purple-400" />
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge variant={school?.subscription_status === "ACTIVE" ? "emerald" : "crimson"}>
                    {school?.subscription_status || "PENDING"}
                  </Badge>
                </div>
                <p className="text-[10px] text-slate-500 font-medium truncate">
                  {school?.subscription_end_date
                    ? `Exp: ${new Date(school.subscription_end_date).toLocaleDateString("id-ID")}`
                    : "Belum berlangganan"}
                </p>
              </div>
            </div>

            {/* Dashboard Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Academic Years List */}
              <div className="glass-panel p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2 text-slate-100 font-bold text-sm">
                    <CalendarDays className="w-4 h-4 text-indigo-400" />
                    <span>Daftar Periode Akademik</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    rightIcon={<ArrowUpRight className="w-4 h-4" />}
                    onClick={() => onNavigate && onNavigate("/admin/academic-years")}
                  >
                    Atur
                  </Button>
                </div>

                <Table
                  columns={[
                    { key: "name", header: "Tahun Ajaran", render: (item: AcademicYear) => <span className="font-bold text-slate-200">{item.name}</span> },
                    { key: "status", header: "Status", width: "120px", render: (item: AcademicYear) => (
                      <Badge
                        variant={
                          item.status === "ACTIVE"
                            ? "emerald"
                            : item.status === "PLANNED"
                            ? "indigo"
                            : "slate"
                        }
                      >
                        {item.status}
                      </Badge>
                    )},
                  ]}
                  data={academicYears.slice(0, 5)}
                  keyExtractor={(item) => item.id.toString()}
                />
              </div>

              {/* Recent Teachers List */}
              <div className="glass-panel p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2 text-slate-100 font-bold text-sm">
                    <Users className="w-4 h-4 text-emerald-400" />
                    <span>Daftar Guru Terdaftar</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    rightIcon={<ArrowUpRight className="w-4 h-4" />}
                    onClick={() => onNavigate && onNavigate("/admin/teachers")}
                  >
                    Kelola
                  </Button>
                </div>

                <Table
                  columns={[
                    { key: "username", header: "Username / NIP", render: (item: TeacherAccount) => <span className="font-mono text-xs font-semibold text-indigo-300">{item.username}</span> },
                    { key: "status", header: "Status", width: "120px", render: (item: TeacherAccount) => (
                      <Badge variant={item.is_active ? "emerald" : "amber"}>
                        {item.is_active ? "AKTIF" : "NONAKTIF"}
                      </Badge>
                    )},
                  ]}
                  data={teachers.slice(0, 5)}
                  keyExtractor={(item) => item.id.toString()}
                />
              </div>
            </div>
          </div>
        )}
      </RoleGuard>
    </AppShell>
  );
};
