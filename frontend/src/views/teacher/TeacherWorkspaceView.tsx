import { useState, useEffect } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { teacherContentApi } from "../../api/teacherContent";
import { QuestionPackagesView } from "./QuestionPackagesView";
import { QuestionPackageDetailView } from "./QuestionPackageDetailView";
import { QuestionBankView } from "./QuestionBankView";
import { TeacherAssignmentsView } from "./TeacherAssignmentsView";
import { TeacherProctorView } from "./TeacherProctorView";
import { TeacherGradingView } from "./TeacherGradingView";
import {
  BookOpen,
  FolderOpen,
  Sparkles,
  ClipboardList,
  CheckCircle2,
} from "lucide-react";
import { MultilingualTypingWelcome } from "../../components/ui/MultilingualTypingWelcome";

interface TeacherWorkspaceViewProps {
  initialPath?: string;
  onNavigate?: (href: string) => void;
}

export function TeacherWorkspaceView({ initialPath = "/teacher/dashboard", onNavigate }: TeacherWorkspaceViewProps) {
  const { user } = useAuth();

  // Local routing state
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [activePackageId, setActivePackageId] = useState<number | null>(null);

  // Statistics
  const [packageCount, setPackageCount] = useState(0);
  const [questionCount, setQuestionCount] = useState(0);
  const [readyPackageCount, setReadyPackageCount] = useState(0);

  const fetchStats = async () => {
    try {
      const [pkgs, qstns] = await Promise.all([
        teacherContentApi.listPackages(),
        teacherContentApi.listQuestions(),
      ]);
      setPackageCount(pkgs.length);
      setQuestionCount(qstns.length);
      setReadyPackageCount(pkgs.filter((p) => p.status === "READY").length);
    } catch {
      // Quiet fail or silent
    }
  };

  useEffect(() => {
    fetchStats();
  }, [currentPath]);

  // Sync state path if props change
  useEffect(() => {
    if (initialPath) {
      setCurrentPath(initialPath);
      // Extract package ID if path is /teacher/packages/:id
      const match = initialPath.match(/\/teacher\/packages\/(\d+)/);
      if (match) {
        setActivePackageId(parseInt(match[1], 10));
      } else {
        setActivePackageId(null);
      }
    }
  }, [initialPath]);

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    if (onNavigate) {
      onNavigate(path);
    }
    const match = path.match(/\/teacher\/packages\/(\d+)/);
    if (match) {
      setActivePackageId(parseInt(match[1], 10));
    } else {
      setActivePackageId(null);
    }
  };

  const renderContent = () => {
    if (currentPath === "/teacher/questions") {
      return <QuestionBankView onNavigate={handleNavigate} />;
    }

    if (currentPath === "/teacher/assignments") {
      return <TeacherAssignmentsView />;
    }

    if (currentPath === "/teacher/proctor") {
      return <TeacherProctorView />;
    }

    if (currentPath === "/teacher/grading") {
      return <TeacherGradingView />;
    }

    if (currentPath === "/teacher/packages" || currentPath.startsWith("/teacher/packages")) {
      if (activePackageId !== null) {
        return (
          <QuestionPackageDetailView
            packageId={activePackageId}
            onBack={() => handleNavigate("/teacher/packages")}
            onNavigate={handleNavigate}
          />
        );
      }
      return (
        <QuestionPackagesView
          onNavigate={handleNavigate}
          onSelectPackage={(id) => handleNavigate(`/teacher/packages/${id}`)}
        />
      );
    }

    // Default: Dashboard /teacher/dashboard
    return (
      <div className="space-y-6 animate-fade-in">
        {/* Welcome Banner */}
        <div className="glass-panel p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="indigo">Teacher / Guru</Badge>
              <Badge variant="emerald">PLATFORM ACTIVE</Badge>
            </div>
            <MultilingualTypingWelcome userName={user?.full_name || user?.name || user?.email || "Guru Equigrade"} />
            <p className="text-xs text-slate-400 mt-2">
              Workspace resmi pengampu mata pelajaran. Kelola pembuatan bank soal dan paket soal ujian mandiri di sini.
            </p>
          </div>
        </div>

        {/* Stats Bento Box on Mobile / 3-Column on Desktop */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
          <div className="glass-panel p-3.5 sm:p-4 flex items-center justify-between col-span-2 lg:col-span-1">
            <div className="flex items-center gap-3 sm:gap-3.5">
              <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                <FolderOpen className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <p className="text-[11px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Paket Soal</p>
                <p className="text-xl sm:text-2xl font-black text-slate-100 mt-0.5">{packageCount}</p>
              </div>
            </div>
            <span className="text-[10px] font-medium text-slate-500 bg-slate-900/60 px-2.5 py-1 rounded-full border border-slate-800">
              Koleksi
            </span>
          </div>

          <div className="glass-panel p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-2 col-span-1">
            <div className="flex items-center gap-2 sm:gap-3.5">
              <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Paket READY</p>
                <p className="text-lg sm:text-2xl font-black text-emerald-400 mt-0.5">{readyPackageCount}</p>
              </div>
            </div>
            <span className="text-[9px] sm:text-[10px] font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-emerald-500/20">
              Siap Ujian
            </span>
          </div>

          <div className="glass-panel p-3 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1.5 sm:gap-2 col-span-1">
            <div className="flex items-center gap-2 sm:gap-3.5">
              <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
                <BookOpen className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400" />
              </div>
              <div>
                <p className="text-[10px] sm:text-xs font-semibold text-slate-400 uppercase tracking-wider">Bank Soal</p>
                <p className="text-lg sm:text-2xl font-black text-amber-400 mt-0.5">{questionCount}</p>
              </div>
            </div>
            <span className="text-[9px] sm:text-[10px] font-semibold text-amber-400 bg-amber-950/40 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full border border-amber-500/20">
              Butir Soal
            </span>
          </div>
        </div>

        {/* Informative Dashboard Guide */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-panel p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>Langkah Cepat Pembuatan Paket Ujian</span>
            </h3>
            <div className="space-y-3 text-xs text-slate-400 leading-relaxed">
              <div className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-slate-800 text-[10px] font-bold text-slate-300 flex items-center justify-center shrink-0">1</span>
                <p>
                  Buka menu <strong className="text-slate-300">Bank Soal</strong> dan buat butir-butir pertanyaan pilihan ganda, isian singkat, maupun esai lengkap dengan rubrik.
                </p>
              </div>
              <div className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-slate-800 text-[10px] font-bold text-slate-300 flex items-center justify-center shrink-0">2</span>
                <p>
                  Buka menu <strong className="text-slate-300">Paket Soal</strong>, buat paket baru, dan tetapkan target jumlah soal untuk masing-masing jenis ujian.
                </p>
              </div>
              <div className="flex gap-2">
                <span className="w-5 h-5 rounded-full bg-slate-800 text-[10px] font-bold text-slate-300 flex items-center justify-center shrink-0">3</span>
                <p>
                  Buka detail paket tersebut, lalu masukkan soal dari bank soal pribadi. Urutkan soal sesuai kebutuhan hingga status paket menjadi <strong className="text-emerald-400">READY</strong>.
                </p>
              </div>
            </div>
          </div>

          <div className="glass-panel p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <ClipboardList className="w-4 h-4 text-indigo-400" />
              <span>Informasi Pengawasan & Ujian</span>
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Sesi ujian resmi diatur oleh School Admin lewat halaman penjadwalan. Sebagai guru pengampu, Anda akan mendapatkan akses ke menu penugasan pengawas (Proctoring) dan koreksi esai otomatis bertenaga AI setelah jadwal diaktifkan oleh admin.
            </p>
            <div className="pt-2">
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<FolderOpen className="w-4 h-4" />}
                onClick={() => handleNavigate("/teacher/packages")}
              >
                Susun Paket Ujian Sekarang
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const getBreadcrumbLabel = () => {
    if (currentPath === "/teacher/questions") return "Bank Soal";
    if (currentPath.startsWith("/teacher/packages")) {
      if (activePackageId !== null) return `Detail Paket Soal #${activePackageId}`;
      return "Paket Soal Ujian";
    }
    if (currentPath === "/teacher/assignments") return "Penugasan Ujian";
    if (currentPath === "/teacher/proctor") return "Pengawas & BAP";
    if (currentPath === "/teacher/grading") return "Penilaian Essay";
    return "Dashboard Guru";
  };

  return (
    <AppShell activeHref={currentPath} onNavigate={handleNavigate}>
      <Breadcrumb
        items={[
          { label: "Workspace Guru", href: "/teacher/dashboard" },
          { label: getBreadcrumbLabel() },
        ]}
      />
      {renderContent()}
    </AppShell>
  );
}
