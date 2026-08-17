import { useState } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { StudentSchedulesView } from "./StudentSchedulesView";
import { StudentCbtEngineView } from "./StudentCbtEngineView";
import type { StudentSchedule } from "../../api/studentExam";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { LockxamAppGuard } from "../../components/ui/LockxamAppGuard";
import { KeyRound, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { apiClient } from "../../api/client";

interface StudentWorkspaceProps {
  initialPath?: string;
  onNavigate?: (path: string) => void;
}

export function StudentWorkspaceView({ initialPath = "/student/dashboard", onNavigate }: StudentWorkspaceProps) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [activeExamSchedule, setActiveExamSchedule] = useState<StudentSchedule | null>(null);

  // Change Password Modal States
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    if (onNavigate) onNavigate(path);
  };

  const getBreadcrumbTitle = () => {
    if (currentPath === "/student/history") return "Riwayat Ujian";
    if (currentPath === "/student/profile") return "Profil Siswa";
    return "Jadwal Ujian CBT";
  };

  const handleChangePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError("");

    if (newPassword !== confirmPassword) {
      setPasswordError("Konfirmasi kata sandi baru tidak cocok.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("Kata sandi baru minimal harus 8 karakter.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await apiClient.post("/api/v1/auth/change-password", {
        old_password: oldPassword,
        new_password: newPassword,
      });
      showToast({
        type: "success",
        title: "Kata Sandi Berhasil Diubah",
        message: "Kata sandi akun siswa Anda telah diperbarui.",
      });
      setIsPasswordModalOpen(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setPasswordError(err?.message || "Gagal mengubah kata sandi. Periksa kata sandi lama Anda.");
    } finally {
      setIsChangingPassword(false);
    }
  };

  if (activeExamSchedule) {
    return (
      <LockxamAppGuard>
        <StudentCbtEngineView
          schedule={activeExamSchedule}
          onExit={() => setActiveExamSchedule(null)}
        />
      </LockxamAppGuard>
    );
  }

  return (
    <LockxamAppGuard>
      <AppShell activeHref={currentPath} onNavigate={handleNavigate}>
        <Breadcrumb
          items={[
            { label: "Student Portal", href: "/student/dashboard" },
            { label: getBreadcrumbTitle() },
          ]}
        />

        {currentPath === "/student/history" ? (
          <StudentSchedulesView mode="HISTORY" onStartExam={(sch) => setActiveExamSchedule(sch)} />
        ) : currentPath === "/student/profile" ? (
          <div className="space-y-6 animate-fade-in">
            {/* Main Profile Card */}
            <div className="glass-panel p-6 border border-slate-800 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-black text-2xl shadow-xl shadow-indigo-600/10">
                    {user?.full_name ? user.full_name.charAt(0) : user?.name ? user.name.charAt(0) : "S"}
                  </div>
                  <div>
                    <h3 className="text-xl font-black text-slate-100">
                      {user?.full_name || user?.name || user?.username || "Siswa Equigrade"}
                    </h3>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      NISN: <span className="text-indigo-300 font-bold">{user?.nisn || user?.nis || "-"}</span> | Username:{" "}
                      <span className="text-slate-200 font-bold">{user?.username || user?.email}</span>
                    </p>
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<KeyRound className="w-4 h-4 text-indigo-400" />}
                  onClick={() => setIsPasswordModalOpen(true)}
                >
                  Ganti Kata Sandi
                </Button>
              </div>

              {/* Profile Grid Detail */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Nama Lengkap Siswa:</span>
                  <p className="text-slate-100 font-bold text-sm">{user?.full_name || user?.name || "-"}</p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Nomor Induk Siswa Nasional (NISN):</span>
                  <p className="text-indigo-300 font-mono font-bold text-sm">{user?.nisn || "-"}</p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Nomor Induk Siswa (NIS):</span>
                  <p className="text-slate-200 font-mono font-bold text-sm">{user?.nis || "-"}</p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Kelas / Rombel:</span>
                  <p className="text-emerald-400 font-bold text-sm">{user?.class_name || "Kelas Terdaftar"}</p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Tahun Angkatan / Register:</span>
                  <p className="text-slate-200 font-bold text-sm">{user?.registered_year ? `${user.registered_year}` : "-"}</p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-850 space-y-1">
                  <span className="text-slate-500 font-medium">Sekolah Tenant:</span>
                  <p className="text-slate-200 font-bold text-sm">{user?.school_name || "Sekolah Terdaftar"}</p>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 bg-slate-950 rounded-xl border border-slate-850 text-xs">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span className="text-slate-300 font-medium">Status Akun Siswa:</span>
                </div>
                <Badge variant="emerald">AKTIF & TERVERIFIKASI</Badge>
              </div>
            </div>
          </div>
        ) : (
          <StudentSchedulesView onStartExam={(sch) => setActiveExamSchedule(sch)} />
        )}

        {/* ── Modal Ganti Password Siswa ── */}
        <Modal
          isOpen={isPasswordModalOpen}
          onClose={() => setIsPasswordModalOpen(false)}
          title="Ganti Kata Sandi Akun Siswa"
          maxWidth="sm"
        >
          <form onSubmit={handleChangePasswordSubmit} className="space-y-4 text-xs">
            {passwordError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300">
                {passwordError}
              </div>
            )}

            <div className="relative">
              <Input
                label="Kata Sandi Lama"
                type={showOldPassword ? "text" : "password"}
                required
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="Masukkan kata sandi lama saat ini"
              />
              <button
                type="button"
                onClick={() => setShowOldPassword(!showOldPassword)}
                className="absolute right-3 top-8 text-slate-400 hover:text-slate-200"
              >
                {showOldPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            <div className="relative">
              <Input
                label="Kata Sandi Baru"
                type={showNewPassword ? "text" : "password"}
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimal 8 karakter"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-8 text-slate-400 hover:text-slate-200"
              >
                {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            <div className="relative">
              <Input
                label="Konfirmasi Kata Sandi Baru"
                type={showConfirmPassword ? "text" : "password"}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Ulangi kata sandi baru"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-8 text-slate-400 hover:text-slate-200"
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" type="button" onClick={() => setIsPasswordModalOpen(false)}>
                Batal
              </Button>
              <Button variant="primary" type="submit" isLoading={isChangingPassword} disabled={isChangingPassword}>
                Simpan Perubahan
              </Button>
            </div>
          </form>
        </Modal>
      </AppShell>
    </LockxamAppGuard>
  );
}
