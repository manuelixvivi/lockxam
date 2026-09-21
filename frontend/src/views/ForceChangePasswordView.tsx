import React, { useState } from "react";
import { Lock, AlertCircle, CheckCircle2, ShieldAlert, Eye, EyeOff } from "lucide-react";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { schoolApi } from "../api/school";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export const ForceChangePasswordView: React.FC = () => {
  const { refreshProfile, logout, user } = useAuth();
  const { showToast } = useToast();

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    if (newPassword !== confirmPassword) {
      setErrorMessage("Konfirmasi kata sandi baru tidak cocok.");
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage("Kata sandi baru minimal harus 8 karakter.");
      return;
    }

    // Password strength check (must contain uppercase, lowercase, and number)
    const hasUpper = /[A-Z]/.test(newPassword);
    const hasLower = /[a-z]/.test(newPassword);
    const hasNumber = /[0-9]/.test(newPassword);
    if (!hasUpper || !hasLower || !hasNumber) {
      setErrorMessage("Kata sandi harus mengandung kombinasi huruf besar, huruf kecil, dan angka.");
      return;
    }

    setIsLoading(true);
    try {
      await schoolApi.changeAdminPassword({
        old_password: oldPassword,
        new_password: newPassword,
      });

      setIsSuccess(true);
      showToast({
        type: "success",
        title: "Kata Sandi Diperbarui",
        message: "Kata sandi Anda berhasil diperbarui. Halaman akan dimuat ulang...",
      });

      // Hard reload the browser so it clears the state and fetches the fresh profile
      setTimeout(() => {
        window.location.href = "/";
      }, 2000);
    } catch (err: any) {
      setErrorMessage(err.message || "Gagal memperbarui kata sandi. Periksa kata sandi lama Anda.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-3xl p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex items-center justify-center text-amber-400 mb-3 shadow-xl">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-black text-slate-100 tracking-tight">Wajib Ganti Kata Sandi</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-sm">
            Sebagai langkah keamanan pertama, Anda wajib memperbarui kata sandi default sebelum mengakses platform secara penuh.
          </p>
        </div>

        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-500/40 flex items-start gap-3 text-red-300 text-xs animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {isSuccess ? (
          <div className="p-6 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 text-center space-y-3 animate-fade-in">
            <div className="w-10 h-10 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <p className="text-sm font-semibold text-slate-100">Kata Sandi Berhasil Diperbarui!</p>
            <p className="text-xs text-slate-400">Sistem sedang memuat ulang halaman Anda...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="text-xs text-slate-400 bg-slate-950 px-3 py-2 rounded-lg font-mono">
              User: <span className="text-indigo-400">{user?.email || user?.full_name}</span>
            </div>

            <Input
              label="Kata Sandi Lama / Default"
              type={showOldPassword ? "text" : "password"}
              placeholder="Masukkan kata sandi lama/default"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              leftIcon={<Lock className="w-4 h-4" />}
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
              leftIcon={<Lock className="w-4 h-4" />}
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
              helperText="Min. 8 karakter, wajib kombinasi huruf besar, kecil, & angka."
            />

            <Input
              label="Konfirmasi Kata Sandi Baru"
              type={showConfirmPassword ? "text" : "password"}
              placeholder="Ulangi kata sandi baru"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              leftIcon={<Lock className="w-4 h-4" />}
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

            <div className="flex flex-col gap-2 pt-2">
              <Button type="submit" variant="primary" size="lg" isLoading={isLoading} className="w-full">
                Perbarui Kata Sandi
              </Button>
              <button
                type="button"
                onClick={() => logout()}
                className="text-xs text-slate-400 hover:text-slate-200 transition-colors py-2 text-center"
              >
                Keluar / Logout
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
