import { useState, useEffect, Suspense, lazy } from "react";
import { AuthProvider, useAuth, UserRole } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { AppShell } from "./components/layout/AppShell";
import { LoginView } from "./views/LoginView";
import { Badge } from "./components/ui/Badge";
import { Breadcrumb } from "./components/layout/Breadcrumb";
import { Spinner } from "./components/ui/Spinner";
import { BookOpen } from "lucide-react";
import { ThemeProvider } from "./context/ThemeContext";
import { OfflineDetector } from "./components/ui/OfflineDetector";

// 🚀 Route-Level Code Splitting (React.lazy)
const SchoolDashboardView = lazy(() =>
  import("./views/admin/SchoolDashboardView").then((m) => ({ default: m.SchoolDashboardView }))
);
const SchoolProfileView = lazy(() =>
  import("./views/admin/SchoolProfileView").then((m) => ({ default: m.SchoolProfileView }))
);
const SchoolSubscriptionView = lazy(() =>
  import("./views/admin/SchoolSubscriptionView").then((m) => ({ default: m.SchoolSubscriptionView }))
);
const AcademicYearsView = lazy(() =>
  import("./views/admin/AcademicYearsView").then((m) => ({ default: m.AcademicYearsView }))
);
const TeachersView = lazy(() =>
  import("./views/admin/TeachersView").then((m) => ({ default: m.TeachersView }))
);
const StudentsView = lazy(() =>
  import("./views/admin/StudentsView").then((m) => ({ default: m.StudentsView }))
);
const SubjectsView = lazy(() =>
  import("./views/admin/SubjectsView").then((m) => ({ default: m.SubjectsView }))
);
const ClassesView = lazy(() =>
  import("./views/admin/ClassesView").then((m) => ({ default: m.ClassesView }))
);
const ExamSchedulesView = lazy(() =>
  import("./views/admin/ExamSchedulesView").then((m) => ({ default: m.ExamSchedulesView }))
);
const ForceChangePasswordView = lazy(() =>
  import("./views/ForceChangePasswordView").then((m) => ({ default: m.ForceChangePasswordView }))
);
const SuperAdminDashboardView = lazy(() =>
  import("./views/superadmin/SuperAdminDashboardView").then((m) => ({ default: m.SuperAdminDashboardView }))
);
const SuperAdminSchoolsView = lazy(() =>
  import("./views/superadmin/SuperAdminSchoolsView").then((m) => ({ default: m.SuperAdminSchoolsView }))
);
const SuperAdminLicensesView = lazy(() =>
  import("./views/superadmin/SuperAdminLicensesView").then((m) => ({ default: m.SuperAdminLicensesView }))
);
const SuperAdminAiSystemView = lazy(() =>
  import("./views/superadmin/SuperAdminAiSystemView").then((m) => ({ default: m.SuperAdminAiSystemView }))
);
const TeacherWorkspaceView = lazy(() =>
  import("./views/teacher/TeacherWorkspaceView").then((m) => ({ default: m.TeacherWorkspaceView }))
);
const StudentWorkspaceView = lazy(() =>
  import("./views/student/StudentWorkspaceView").then((m) => ({ default: m.StudentWorkspaceView }))
);

const RouteLoadingFallback = () => (
  <div className="min-h-[60vh] flex items-center justify-center">
    <Spinner size="lg" label="Memuat modul..." />
  </div>
);

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

  // Loading State
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Spinner size="lg" label="Memuat platform EquiGrade..." />
      </div>
    );
  }

  // Not Authenticated -> Login
  if (!isAuthenticated) {
    return (
      <LoginView
        onLoginSuccess={(accountRole: UserRole) => {
          const r = String(accountRole || role || "");
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
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        <ForceChangePasswordView />
      </Suspense>
    );
  }

  // SuperAdmin Routes (Phase 3A)
  if (role === UserRole.SUPER_ADMIN) {
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        {currentPath === "/superadmin/schools" ? (
          <SuperAdminSchoolsView onNavigate={handleNavigate} />
        ) : currentPath === "/superadmin/licenses" ? (
          <SuperAdminLicensesView onNavigate={handleNavigate} />
        ) : currentPath.startsWith("/superadmin/ai-system") ? (
          <SuperAdminAiSystemView onNavigate={handleNavigate} />
        ) : (
          <SuperAdminDashboardView onNavigate={handleNavigate} />
        )}
      </Suspense>
    );
  }

  // School Admin Routes (Phase 3B)
  if (role === UserRole.SCHOOL_ADMIN) {
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        {currentPath === "/admin/dashboard" ? (
          <SchoolDashboardView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/profile" ? (
          <SchoolProfileView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/subscription" ? (
          <SchoolSubscriptionView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/academic-years" ? (
          <AcademicYearsView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/teachers" ? (
          <TeachersView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/students" ? (
          <StudentsView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/subjects" ? (
          <SubjectsView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/classes" || currentPath === "/admin/classes-subjects" ? (
          <ClassesView onNavigate={handleNavigate} />
        ) : currentPath === "/admin/exam-schedules" ? (
          <ExamSchedulesView onNavigate={handleNavigate} />
        ) : (
          <AppShell activeHref={currentPath} onNavigate={(path) => setCurrentPath(path)}>
            <Breadcrumb
              items={[{ label: "School Admin", href: "/admin/profile" }, { label: "Halaman dalam Pengembangan" }]}
            />
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
        )}
      </Suspense>
    );
  }

  // Teacher Routes (Phase 4.1)
  if (role === UserRole.TEACHER) {
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        <TeacherWorkspaceView
          initialPath={currentPath || "/teacher/dashboard"}
          onNavigate={handleNavigate}
        />
      </Suspense>
    );
  }

  // Student Routes (Phase 4.2)
  if (role === UserRole.STUDENT) {
    return (
      <Suspense fallback={<RouteLoadingFallback />}>
        <StudentWorkspaceView
          initialPath={currentPath || "/student/dashboard"}
          onNavigate={handleNavigate}
        />
      </Suspense>
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
