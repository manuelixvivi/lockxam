import React, { useState, useEffect } from "react";
import { Lock, User, Shield, AlertCircle, Sparkles, Sun, Moon, Eye, EyeOff } from "lucide-react";
import { Input } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { useAuth } from "../context/AuthContext";
import type { UserRole } from "../context/AuthContext";
import { apiClient } from "../api/client";
import { useTheme } from "../context/ThemeContext";

export const LoginView: React.FC<{ onLoginSuccess?: (role: UserRole) => void }> = ({
  onLoginSuccess,
}) => {
  const { login } = useAuth();
  const { theme, toggleTheme, setTheme } = useTheme();
  
  const [username, setUsername] = useState("admin_school");
  const [password, setPassword] = useState("Password123!");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    // Default to light mode on login page mounting
    setTheme("light");
  }, []);

  const handlePerformLogin = async (userToLogin: string, passToLogin: string) => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      const response = await apiClient.post<{
        access_token: string;
        refresh_token: string;
        role: UserRole;
        school_id?: number;
      }>("/api/v1/auth/login", {
        username: userToLogin,
        password: passToLogin,
      });

      apiClient.setAccessToken(response.access_token);

      const me = await apiClient.get("/api/v1/auth/me");

      login(response.access_token, response.refresh_token, me);

      if (onLoginSuccess) {
        onLoginSuccess(me.role);
      }
    } catch (err: any) {
      setErrorMessage(
        err.message || "Gagal masuk. Periksa kembali nama pengguna dan kata sandi Anda."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handlePerformLogin(username, password);
  };

  const handleQuickLogin = (uname: string) => {
    setUsername(uname);
    setPassword("Password123!");
    handlePerformLogin(uname, "Password123!");
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6 relative overflow-hidden">
      {/* Floating Theme Toggle (Sun/Moon) */}
      <div className="absolute top-6 right-6 z-20">
        <button
          type="button"
          onClick={toggleTheme}
          className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-slate-200 transition-colors shadow-lg backdrop-blur-md"
          title={theme === "light" ? "Ganti ke Mode Gelap" : "Ganti ke Mode Terang"}
        >
          {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>
      </div>

      {/* Background Decorative Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-10 w-72 h-72 bg-purple-600/15 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-3xl p-8 shadow-2xl backdrop-blur-xl">
        {/* Brand */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 bg-indigo-600/25 border border-indigo-500/40 rounded-2xl flex items-center justify-center text-indigo-400 mb-3 shadow-xl shadow-indigo-600/20">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-black text-slate-100 tracking-tight">Equigrade</h1>
          <p className="text-xs text-indigo-400 font-semibold tracking-wider uppercase mt-0.5">
            Lockxam v3.0 Integrated Platform
          </p>
        </div>

        {/* Quick Demo Credentials Assistant */}
        <div className="mb-6 p-4 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-300">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Satu-Klik Login Demo:</span>
          </div>
          <div className="grid grid-cols-2 gap-2 pt-1">
            <button
              type="button"
              onClick={() => handleQuickLogin("admin_school")}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-600/20 border border-indigo-500/40 text-indigo-200 hover:bg-indigo-600/40 transition-colors text-left"
            >
              🔑 School Admin
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin("superadmin")}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-purple-600/20 border border-purple-500/40 text-purple-200 hover:bg-purple-600/40 transition-colors text-left"
            >
              👑 SuperAdmin
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin("teacher1")}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-emerald-600/20 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-600/40 transition-colors text-left"
            >
              👨‍🏫 Teacher
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin("student1")}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-amber-600/20 border border-amber-500/40 text-amber-200 hover:bg-amber-600/40 transition-colors text-left"
            >
              🎓 Student
            </button>
          </div>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/50 border border-red-500/40 flex items-start gap-3 text-red-300 text-xs animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nama Pengguna atau Email"
            type="text"
            placeholder="admin_school atau admin_school@sekolah.sch.id"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            leftIcon={<User className="w-4 h-4" />}
            required
          />

          <Input
            label="Kata Sandi"
            type={showPassword ? "text" : "password"}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            leftIcon={<Lock className="w-4 h-4" />}
            rightIcon={
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-slate-400 hover:text-slate-200 focus:outline-none transition-colors p-1"
                title={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            }
            required
          />

          <Button type="submit" variant="primary" size="lg" isLoading={isLoading} className="w-full mt-2">
            Masuk ke Sistem
          </Button>
        </form>


        <p className="text-center text-[11px] text-slate-500 mt-6">
          Equigrade Platform &copy; 2026. All Security Operations Encrypted.
        </p>
      </div>
    </div>
  );
};
