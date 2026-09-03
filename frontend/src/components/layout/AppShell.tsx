import { useEffect, useState } from "react";
import { AlertTriangle, Lock, Eye, EyeOff } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useAuth, UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { Modal } from "../ui/Modal";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { licenseApi } from "../../api/license";
import { schoolApi } from "../../api/school";
import type { ActiveLicenseResponse } from "../../api/license";

export interface AppShellProps {
  children: React.ReactNode;
  activeHref?: string;
  onNavigate?: (href: string) => void;
  hideSidebar?: boolean;
}

const schoolLogoCache: Record<number, string | null> = {};
const schoolLicenseCache: Record<number, ActiveLicenseResponse | null> = {};

export const AppShell: React.FC<AppShellProps> = ({
  children,
  activeHref,
  onNavigate,
  hideSidebar = false,
}) => {
  const { role, user } = useAuth();
  const schoolId = user?.school_id ? Number(user.school_id) : null;

  const [license, setLicense] = useState<ActiveLicenseResponse | null>(() => {
    return schoolId !== null && schoolLicenseCache[schoolId] !== undefined
      ? schoolLicenseCache[schoolId]
      : null;
  });

  useEffect(() => {
    if (role === UserRole.SCHOOL_ADMIN && schoolId !== null) {
      if (schoolLicenseCache[schoolId] !== undefined) {
        setLicense(schoolLicenseCache[schoolId]);
        return;
      }
      licenseApi
        .getMyLicense()
        .then((lic) => {
          schoolLicenseCache[schoolId] = lic;
          setLicense(lic);
        })
        .catch(() => {
          schoolLicenseCache[schoolId] = null;
          setLicense(null);
        });
    }
  }, [role, schoolId]);

  const [logoUrl, setLogoUrl] = useState<string | null>(() => {
    return schoolId !== null && schoolLogoCache[schoolId] !== undefined
      ? schoolLogoCache[schoolId]
      : null;
  });

  useEffect(() => {
    if (schoolId !== null) {
      if (schoolLogoCache[schoolId] !== undefined) {
        setLogoUrl(schoolLogoCache[schoolId]);
        return;
      }
      schoolApi
        .getSchoolProfile(schoolId)
        .then((profile) => {
          const logo = profile.logo_url || null;
          schoolLogoCache[schoolId] = logo;
          if (logo) {
            setLogoUrl(logo);
          }
        })
        .catch(() => {});
    }
  }, [schoolId]);

  const isSuspended = license?.status === "SUSPENDED" || license?.status === "PAUSED";

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Change Password States
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const { showToast } = useToast();

  const handleChangePassword = async (e: React.FormEvent) => {
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

    // Password strength check
    const hasUpper = /[A-Z]/.test(newPassword);
    const hasLower = /[a-z]/.test(newPassword);
    const hasNumber = /[0-9]/.test(newPassword);
    if (!hasUpper || !hasLower || !hasNumber) {
      setPasswordError("Kata sandi harus mengandung kombinasi huruf besar, huruf kecil, dan angka.");
      return;
    }

    setIsChangingPassword(true);
    try {
      const { schoolApi } = await import("../../api/school");
      await schoolApi.changeAdminPassword({
        old_password: oldPassword,
        new_password: newPassword,
      });
      showToast({
        type: "success",
        title: "Kata Sandi Diperbarui",
        message: "Kata sandi Anda berhasil diperbarui.",
      });
      setIsPasswordModalOpen(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setPasswordError(err.message || "Gagal memperbarui kata sandi. Periksa kata sandi lama Anda.");
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex relative overflow-hidden">
      {/* Subtle School Logo Watermark Background */}
      {logoUrl && (
        <div 
          className="fixed inset-0 pointer-events-none flex items-center justify-center z-0 select-none overflow-hidden"
          style={{ opacity: 0.025 }}
        >
          <img 
            src={logoUrl} 
            alt="School Logo Watermark" 
            className="w-[350px] h-[350px] md:w-[480px] md:h-[480px] object-contain filter grayscale contrast-125 brightness-110"
          />
        </div>
      )}

      {!hideSidebar && (
        <Sidebar
          activeHref={activeHref}
          onNavigate={onNavigate}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        {!hideSidebar && (
          <Topbar
            onMenuClick={() => setIsSidebarOpen(true)}
            onNavigate={onNavigate}
            onChangePasswordClick={() => setIsPasswordModalOpen(true)}
          />
        )}

        {role === UserRole.SCHOOL_ADMIN && isSuspended && (
          <div className="mx-6 md:mx-8 mt-6 p-4 rounded-2xl bg-amber-950/70 border border-amber-500/50 flex items-center justify-between gap-4 shadow-lg shadow-amber-950/50 backdrop-blur-md">
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                <AlertTriangle className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-amber-200 tracking-wide">
                  AKUN SEKOLAH SEDANG DIJEDA (SUBSCRIPTION SUSPENDED) ⏸️
                </h4>
                <p className="text-xs text-amber-300/80 mt-0.5">
                  Layanan subscription sekolah Anda sedang ditangguhkan/dijeda oleh SuperAdmin. Akses pengelolanan ujian dibatasi. Hubungi Tim SuperAdmin untuk aktivasi kembali.
                </p>
              </div>
            </div>
          </div>
        )}

        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>

      {/* ── Modal: Change Password ── */}
      <Modal
        isOpen={isPasswordModalOpen}
        onClose={() => {
          setIsPasswordModalOpen(false);
          setPasswordError("");
          setOldPassword("");
          setNewPassword("");
          setConfirmPassword("");
        }}
        title="Ubah Kata Sandi Akun"
        maxWidth="sm"
      >
        <form onSubmit={handleChangePassword} className="space-y-4">
          {passwordError && (
            <div className="p-3 rounded-lg bg-red-950/30 border border-red-500/30 text-red-300 text-xs font-semibold">
              {passwordError}
            </div>
          )}

          <Input
            label="Kata Sandi Lama"
            type={showOldPassword ? "text" : "password"}
            placeholder="Masukkan kata sandi lama Anda"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
            rightIcon={
              <button
                type="button"
                onClick={() => setShowOldPassword(!showOldPassword)}
                className="text-slate-400 hover:text-slate-200 focus:outline-none transition-colors p-1"
                title={showOldPassword ? "Sembunyikan" : "Tampilkan"}
              >
                {showOldPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            }
            autoComplete="new-password"
            required
          />

          <Input
            label="Kata Sandi Baru"
            type={showNewPassword ? "text" : "password"}
            placeholder="Minimal 8 karakter"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
            rightIcon={
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="text-slate-400 hover:text-slate-200 focus:outline-none transition-colors p-1"
                title={showNewPassword ? "Sembunyikan" : "Tampilkan"}
              >
                {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            }
            autoComplete="new-password"
            required
            helperText="Wajib kombinasi huruf besar, huruf kecil, dan angka."
          />

          <Input
            label="Konfirmasi Kata Sandi Baru"
            type={showConfirmPassword ? "text" : "password"}
            placeholder="Ulangi kata sandi baru"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
            rightIcon={
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="text-slate-400 hover:text-slate-200 focus:outline-none transition-colors p-1"
                title={showConfirmPassword ? "Sembunyikan" : "Tampilkan"}
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            }
            autoComplete="new-password"
            required
          />

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setIsPasswordModalOpen(false);
                setPasswordError("");
                setOldPassword("");
                setNewPassword("");
                setConfirmPassword("");
              }}
            >
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isChangingPassword}
            >
              Simpan Sandi
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

