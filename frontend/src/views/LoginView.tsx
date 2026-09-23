import React, { useState } from "react";
import { Lock, User, Shield, AlertCircle, Sun, Moon, Eye, EyeOff, Cpu, BarChart3, ScanFace } from "lucide-react";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";
import type { UserRole } from "../context/AuthContext";
import { apiClient } from "../api/client";
import { useTheme } from "../context/ThemeContext";

const FEATURES = [
  { icon: ScanFace, title: "Lockdown Anti-Curang", desc: "Proteksi Lockxam selama sesi ujian berlangsung." },
  { icon: Cpu, title: "Penilaian AI RAG", desc: "Koreksi essay otomatis dengan verifikasi guru." },
  { icon: BarChart3, title: "Analitik Real-Time", desc: "Pantau progres dan hasil ujian secara instan." },
];

export const LoginView: React.FC<{ onLoginSuccess?: (role: UserRole) => void }> = ({
  onLoginSuccess,
}) => {
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handlePerformLogin = async (userToLogin: string, passToLogin: string) => {
    setIsLoading(true);
    setErrorMessage("");
    try {
      const response = await apiClient.post<{
        access_token: string;
        refresh_token: string;
        role: UserRole;
        school_id?: number;
        user_profile?: any;
      }>("/api/v1/auth/login", { username: userToLogin, password: passToLogin });

      apiClient.setAccessToken(response.access_token);
      const userProfile = response.user_profile || (await apiClient.get("/api/v1/auth/me"));
      login(response.access_token, response.refresh_token, userProfile);
      if (onLoginSuccess) onLoginSuccess(userProfile.role || response.role);
    } catch (err: any) {
      setErrorMessage(err.message || "Gagal masuk. Periksa kembali nama pengguna dan kata sandi Anda.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handlePerformLogin(username, password);
  };

  return (
    <div className="min-h-screen flex bg-slate-950">
      {/* ── Panel Brand (desktop) ── */}
      <div className="hidden lg:flex flex-col justify-between w-[46%] p-12 relative overflow-hidden bg-brand-gradient">
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-white/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 -left-16 w-80 h-80 bg-purple-900/40 rounded-full blur-3xl pointer-events-none" />

        <div className="relative flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-white/15 border border-white/25 backdrop-blur flex items-center justify-center text-white font-black text-xl">
            E
          </div>
          <div>
            <p className="text-white font-extrabold text-lg tracking-tight">Equigrade</p>
            <p className="text-white/60 text-[10px] font-bold uppercase tracking-[0.2em]">Lockxam v3.0</p>
          </div>
        </div>

        <div className="relative">
          <h2 className="text-4xl font-black text-white leading-tight tracking-tight">
            Penilaian Cerdas,<br />Terukur, &amp; Aman.
          </h2>
          <p className="mt-4 text-white/70 text-sm max-w-sm leading-relaxed">
            Platform Computer-Based Testing dengan koreksi essay berbasis AI
            Retrieval-Augmented Generation dan pengawasan ujian berlapis.
          </p>
          <div className="mt-10 space-y-5">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-white/12 border border-white/20 flex items-center justify-center shrink-0 backdrop-blur">
                  <f.icon className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-white font-semibold text-sm">{f.title}</p>
                  <p className="text-white/60 text-xs mt-0.5">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-white/40 text-xs">© 2026 EquiGrade x Lockxam. Seluruh hak cipta dilindungi.</p>
      </div>

      {/* ── Panel Form ── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 right-10 w-72 h-72 bg-purple-600/15 rounded-full blur-3xl pointer-events-none" />

        <button type="button" onClick={toggleTheme}
          className="absolute top-6 right-6 z-20 p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors shadow-lg backdrop-blur-md"
          title={theme === "light" ? "Ganti ke Mode Gelap" : "Ganti ke Mode Terang"}>
          {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>

        <div className="relative z-10 w-full max-w-md glass-panel p-8 md:p-10 animate-scale-in">
          <div className="flex flex-col items-center text-center mb-7">
            <div className="w-14 h-14 rounded-2xl bg-brand-gradient flex items-center justify-center text-white mb-4 shadow-xl shadow-indigo-600/30">
              <Shield className="w-8 h-8" />
            </div>
            <h1 className="text-2xl font-black text-slate-100 tracking-tight">Selamat Datang</h1>
            <p className="text-xs text-slate-400 font-medium mt-1.5">
              Masuk untuk melanjutkan ke platform ujian
            </p>
          </div>

          {errorMessage && (
            <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-500/40 flex items-start gap-3 text-red-300 text-xs animate-fade-in">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Nama Pengguna atau Email"
              placeholder="Masukkan nama pengguna / email"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              leftIcon={<User className="w-4 h-4 text-indigo-400" />}
              autoComplete="username"
              required
            />
            <Input
              label="Kata Sandi"
              type={showPassword ? "text" : "password"}
              placeholder="Masukkan kata sandi"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
              rightIcon={
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                  title={showPassword ? "Sembunyikan" : "Tampilkan"}>
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
              autoComplete="current-password"
              required
            />
            <Button type="submit" variant="primary" size="lg" isLoading={isLoading} className="w-full !mt-6">
              Masuk ke Platform
            </Button>
          </form>

          <p className="mt-8 text-center text-[11px] text-slate-500">
            EquiGrade x Lockxam v3.0 — AI-Powered Computer-Based Assessment
          </p>
        </div>
      </div>
    </div>
  );
};
