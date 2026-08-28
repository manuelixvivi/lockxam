import React from "react";
import {
  LayoutDashboard,
  Building2,
  KeyRound,
  UserCheck,
  GraduationCap,
  CalendarDays,
  CreditCard,
  BookOpen,
  FileCheck,
  Award,
  ShieldCheck,
  HelpCircle,
  X,
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

  return (
    <>
      {/* Sidebar Backdrop Overlay for all screen sizes */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-50 backdrop-blur-sm transition-opacity duration-300"
          onClick={onClose}
        />
      )}

      {/* Collapsible Drawer Sidebar Panel */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-slate-900 border-r border-slate-800 flex flex-col h-screen transition-transform duration-300 ease-in-out shadow-2xl ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand Header with Close Button */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-400 font-black text-lg shadow-lg shadow-indigo-600/20">
              E
            </div>
            <div>
              <h1 className="font-extrabold text-base tracking-wide text-slate-100">Equigrade</h1>
              <p className="text-[10px] uppercase font-bold tracking-widest text-indigo-400">Lockxam v3.0</p>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
              title="Tutup Menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Nav List */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {items.map((item) => {
            const isActive = activeHref === item.href;
            return (
              <button
                key={item.href}
                onClick={() => {
                  if (onNavigate) onNavigate(item.href);
                  if (onClose) onClose();
                }}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-md shadow-indigo-600/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <span className={isActive ? "text-indigo-400" : "text-slate-500"}>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
};
