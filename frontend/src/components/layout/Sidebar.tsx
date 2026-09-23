import React from "react";
import {
  LayoutDashboard, Building2, KeyRound, UserCheck, GraduationCap,
  CalendarDays, CreditCard, BookOpen, FileCheck, Award,
  ShieldCheck, HelpCircle, Cpu, X, Sparkles,
} from "lucide-react";
import { useAuth, UserRole } from "../../context/AuthContext";

export interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

export interface SidebarProps {
  activeHref?: string;
  onNavigate?: (href: string) => void;
  isOpen?: boolean;
  onClose?: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  SUPER_ADMIN: "Super Admin",
  SCHOOL_ADMIN: "Admin Sekolah",
  TEACHER: "Guru",
  STUDENT: "Siswa",
};

export const Sidebar: React.FC<SidebarProps> = ({
  activeHref = "/admin/dashboard",
  onNavigate,
  isOpen = false,
  onClose,
}) => {
  const { role } = useAuth();

  const getNavItems = (): NavItem[] => {
    switch (role) {
      case UserRole.SUPER_ADMIN:
        return [
          { label: "Dashboard", href: "/superadmin/dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: "Manajemen Sekolah", href: "/superadmin/schools", icon: <Building2 className="w-4 h-4" /> },
          { label: "Lisensi Key Generator", href: "/superadmin/licenses", icon: <KeyRound className="w-4 h-4" /> },
          { label: "AI & Sistem", href: "/superadmin/ai-system", icon: <Cpu className="w-4 h-4" /> },
        ];
      case UserRole.SCHOOL_ADMIN:
        return [
          { label: "Dashboard", href: "/admin/dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: "Jadwal Ujian", href: "/admin/exam-schedules", icon: <FileCheck className="w-4 h-4" /> },
          { label: "Mata Pelajaran", href: "/admin/subjects", icon: <BookOpen className="w-4 h-4" /> },
          { label: "Manajemen Kelas", href: "/admin/classes", icon: <GraduationCap className="w-4 h-4" /> },
          { label: "Direktori Guru", href: "/admin/teachers", icon: <UserCheck className="w-4 h-4" /> },
          { label: "Direktori Siswa", href: "/admin/students", icon: <UserCheck className="w-4 h-4" /> },
          { label: "Tahun Akademik", href: "/admin/academic-years", icon: <CalendarDays className="w-4 h-4" /> },
          { label: "Profil Sekolah", href: "/admin/profile", icon: <Building2 className="w-4 h-4" /> },
          { label: "Subscription", href: "/admin/subscription", icon: <CreditCard className="w-4 h-4" /> },
        ];
      case UserRole.TEACHER:
        return [
          { label: "Dashboard", href: "/teacher/dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
          { label: "Bank Soal", href: "/teacher/questions", icon: <HelpCircle className="w-4 h-4" /> },
          { label: "Paket Soal", href: "/teacher/packages", icon: <BookOpen className="w-4 h-4" /> },
          { label: "Penugasan Ujian", href: "/teacher/assignments", icon: <FileCheck className="w-4 h-4" /> },
          { label: "Pengawas & BAP", href: "/teacher/proctor", icon: <ShieldCheck className="w-4 h-4" /> },
          { label: "Penilaian Ujian", href: "/teacher/grading", icon: <Award className="w-4 h-4" /> },
        ];
      case UserRole.STUDENT:
        return [
          { label: "Jadwal Ujian CBT", href: "/student/dashboard", icon: <FileCheck className="w-4 h-4" /> },
          { label: "Riwayat Ujian", href: "/student/history", icon: <Award className="w-4 h-4" /> },
          { label: "Profil Siswa", href: "/student/profile", icon: <UserCheck className="w-4 h-4" /> },
        ];
      default:
        return [];
    }
  };

  const items = getNavItems();

  const handleNavigate = (href: string) => {
    if (onNavigate) onNavigate(href);
    if (onClose) onClose();
  };

  return (
    <>
      {/* Backdrop — hanya mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-950/60 z-50 backdrop-blur-sm transition-opacity duration-300 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel — drawer di mobile, persisten di desktop (lg) */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 h-screen flex flex-col
          glass-panel !rounded-none !border-y-0 !border-l-0
          transition-transform duration-300 ease-in-out shadow-2xl lg:shadow-none
          ${isOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0 lg:static lg:z-auto`}
      >
        {/* Brand */}
        <div className="px-5 pt-6 pb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-gradient flex items-center justify-center text-white font-black text-lg shadow-lg shadow-indigo-600/30">
              E
            </div>
            <div>
              <h1 className="font-extrabold text-base tracking-tight text-slate-100">Equigrade</h1>
              <p className="text-[10px] uppercase font-bold tracking-[0.18em] text-gradient">Lockxam v3.0</p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-colors lg:hidden"
              title="Tutup Menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Section label */}
        <div className="px-6 pb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
          Menu Utama
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 pb-4 space-y-1 overflow-y-auto">
          {items.map((item) => {
            const isActive = activeHref === item.href;
            return (
              <button
                key={item.href}
                onClick={() => handleNavigate(item.href)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium border transition-all duration-200 ${
                  isActive
                    ? "nav-active"
                    : "text-slate-400 border-transparent hover:text-slate-100 hover:bg-slate-800/50"
                }`}
              >
                <span className={isActive ? "text-indigo-300" : "text-slate-500 group-hover:text-slate-300"}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800/80">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-brand-gradient-soft border border-indigo-500/20">
            <Sparkles className="w-4 h-4 text-indigo-300 shrink-0" />
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-slate-200 truncate">
                {(role && ROLE_LABELS[role]) || "Pengguna"}
              </p>
              <p className="text-[10px] text-slate-500 truncate">EquiGrade x Lockxam</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
