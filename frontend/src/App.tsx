import { useState, useEffect } from "react";
import { AuthProvider, useAuth, UserRole } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { AppShell } from "./components/layout/AppShell";
import { LoginView } from "./views/LoginView";
import { SchoolDashboardView } from "./views/admin/SchoolDashboardView";
import { SchoolProfileView } from "./views/admin/SchoolProfileView";
import { SchoolSubscriptionView } from "./views/admin/SchoolSubscriptionView";
import { AcademicYearsView } from "./views/admin/AcademicYearsView";
import { TeachersView } from "./views/admin/TeachersView";
import { StudentsView } from "./views/admin/StudentsView";
import { SubjectsView } from "./views/admin/SubjectsView";
import { ClassesView } from "./views/admin/ClassesView";
import { ExamSchedulesView } from "./views/admin/ExamSchedulesView";
import { ForceChangePasswordView } from "./views/ForceChangePasswordView";
import { SuperAdminDashboardView } from "./views/superadmin/SuperAdminDashboardView";
import { TeacherWorkspaceView } from "./views/teacher/TeacherWorkspaceView";
import { StudentWorkspaceView } from "./views/student/StudentWorkspaceView";

import { SuperAdminSchoolsView } from "./views/superadmin/SuperAdminSchoolsView";
import { SuperAdminLicensesView } from "./views/superadmin/SuperAdminLicensesView";
import { SuperAdminAiSystemView } from "./views/superadmin/SuperAdminAiSystemView";
import { Badge } from "./components/ui/Badge";
import { Breadcrumb } from "./components/layout/Breadcrumb";
import { BookOpen } from "lucide-react";

function NavigationRouter() {
  const { isAuthenticated, role, user, isLoading } = useAuth();
  const [currentPath, setCurrentPath] = useState<string>(() => window.location.pathname || "");

  const handleNavigate = (path: string) => {
    if (path && window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setCurrentPath(path);
  };

  // Sync state with browser Back / Forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Determine path based on role on login or session restore if path doesn't match role
  useEffect(() => {
    if (!role) return;

    const path = window.location.pathname;
    const r = String(role);

    if (r === "SCHOOL_ADMIN" || r === "ADMIN") {
      if (!path || !path.startsWith("/admin")) {
        handleNavigate("/admin/dashboard");
      } else if (currentPath !== path) {
        setCurrentPath(path);
      }
    } else if (r === "SUPERADMIN" || r === "SUPER_ADMIN") {
      if (!path || !path.startsWith("/superadmin")) {
        handleNavigate("/superadmin/dashboard");
      } else if (currentPath !== path) {
        setCurrentPath(path);
      }
    } else if (r === "TEACHER") {
      if (!path || !path.startsWith("/teacher")) {
        handleNavigate("/teacher/dashboard");
      } else if (currentPath !== path) {
        setCurrentPath(path);
      }
    } else if (r === "STUDENT") {
      if (!path || !path.startsWith("/student")) {
        handleNavigate("/student/dashboard");
      } else if (currentPath !== path) {
        setCurrentPath(path);
      }
    }
  }, [role]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6 text-slate-400 text-xs">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3" />
        <span>Memuat sesi pengguna...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    if (window.location.pathname !== "/login" && window.location.pathname !== "/") {
      window.history.replaceState({}, "", "/login");
    }

    return (
      <LoginView
        onLoginSuccess={(loggedInRole) => {
          const r = String(loggedInRole);
          if (r === "SCHOOL_ADMIN" || r === "ADMIN") {
            handleNavigate("/admin/dashboard");
          } else if (r === "SUPERADMIN" || r === "SUPER_ADMIN") {
            handleNavigate("/superadmin/dashboard");
          } else if (r === "TEACHER") {
            handleNavigate("/teacher/dashboard");
          } else {
            handleNavigate("/student/dashboard");
          }
        }}
      />
    );
  }

  if (user?.must_change_password) {
    return <ForceChangePasswordView />;
  }

  // SuperAdmin Routes (Phase 3A)
  if (role === UserRole.SUPER_ADMIN) {
    if (currentPath === "/superadmin/schools") {
      return <SuperAdminSchoolsView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/superadmin/licenses") {
      return <SuperAdminLicensesView onNavigate={handleNavigate} />;
    }
    if (currentPath.startsWith("/superadmin/ai-system")) {
      return <SuperAdminAiSystemView onNavigate={handleNavigate} />;
    }
    return <SuperAdminDashboardView onNavigate={handleNavigate} />;
  }

  // School Admin Routes (Phase 3B)
  if (role === UserRole.SCHOOL_ADMIN) {
    if (currentPath === "/admin/dashboard") {
      return <SchoolDashboardView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/profile") {
      return <SchoolProfileView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/subscription") {
      return <SchoolSubscriptionView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/academic-years") {
      return <AcademicYearsView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/teachers") {
      return <TeachersView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/students") {
      return <StudentsView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/subjects") {
      return <SubjectsView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/classes" || currentPath === "/admin/classes-subjects") {
      return <ClassesView onNavigate={handleNavigate} />;
    }
    if (currentPath === "/admin/exam-schedules") {
      return <ExamSchedulesView onNavigate={handleNavigate} />;
    }
  }

  // Teacher Routes (Phase 4.1)
  if (role === UserRole.TEACHER) {
    return (
      <TeacherWorkspaceView
        initialPath={currentPath || "/teacher/dashboard"}
        onNavigate={handleNavigate}
      />
    );
  }

  // Student Routes (Phase 4.2)
  if (role === UserRole.STUDENT) {
    return (
      <StudentWorkspaceView
        initialPath={currentPath || "/student/dashboard"}
        onNavigate={handleNavigate}
      />
    );
  }



  // School Admin — unimplemented page placeholder
  if (role === UserRole.SCHOOL_ADMIN) {
    return (
      <AppShell activeHref={currentPath} onNavigate={(path) => setCurrentPath(path)}>
        <Breadcrumb items={[{ label: "School Admin", href: "/admin/profile" }, { label: "Halaman dalam Pengembangan" }]} />
        <div className="glass-panel p-10 text-center space-y-4">
          <div className="w-16 h-16 bg-indigo-500/10 border border-indigo-500/30 rounded-full flex items-center justify-center mx-auto">
            <BookOpen className="w-8 h-8 text-indigo-400" />
          </div>
          <h2 className="text-xl font-bold text-slate-100">Halaman Sedang Dalam Pengembangan</h2>
          <p className="text-sm text-slate-400 max-w-md mx-auto">
            Fitur ini sedang dipersiapkan dan akan segera tersedia. Silakan gunakan menu navigasi di sidebar untuk berpindah ke halaman lain.
          </p>
          <Badge variant="indigo">COMING SOON</Badge>
        </div>
      </AppShell>
    );
  }

  // Fallback View for Unknown / Unassigned Role
  return (
    <AppShell activeHref={currentPath} onNavigate={(path) => setCurrentPath(path)}>
      <Breadcrumb items={[{ label: "Domain Workspace", href: "#" }, { label: role || "Dashboard" }]} />
      <div className="glass-panel p-8 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-100">Selamat Datang di Equigrade Platform</h2>
        <p className="text-xs text-slate-400">
          Silakan gunakan menu di navigasi sidebar untuk mengakses fitur sesuai dengan hak akses akun Anda.
        </p>
      </div>
    </AppShell>
  );
}

import { ThemeProvider } from "./context/ThemeContext";
import { OfflineDetector } from "./components/ui/OfflineDetector";

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <OfflineDetector>
              <NavigationRouter />
            </OfflineDetector>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
