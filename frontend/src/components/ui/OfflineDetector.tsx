import React, { useState, useEffect } from "react";
import { WifiOff, RefreshCw, AlertCircle, ShieldCheck } from "lucide-react";
import { Button } from "./Button";

export const OfflineDetector: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [isRetrying, setIsRetrying] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const handleManualRetry = async () => {
    setIsRetrying(true);
    try {
      // Ping check
      const res = await fetch("/api/v1/health", { method: "HEAD", cache: "no-store" }).catch(() => null);
      if (res || navigator.onLine) {
        setIsOffline(false);
      }
    } finally {
      setTimeout(() => setIsRetrying(false), 800);
    }
  };

  if (isOffline) {
    return (
      <div className="fixed inset-0 z-[9999] bg-slate-950 flex flex-col items-center justify-center p-6 text-center select-none animate-fade-in">
        {/* Subtle Background Glow */}
        <div className="absolute w-[320px] h-[320px] bg-rose-600/10 rounded-full blur-3xl pointer-events-none animate-pulse" />

        <div className="relative glass-panel max-w-md w-full p-8 border-2 border-rose-500/30 rounded-3xl space-y-6 shadow-2xl shadow-rose-950/50">
          {/* Animated Offline Icon */}
          <div className="relative w-20 h-20 bg-rose-500/10 border border-rose-500/40 rounded-3xl flex items-center justify-center mx-auto text-rose-400 shadow-xl shadow-rose-500/20">
            <WifiOff className="w-10 h-10 animate-bounce" />
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 animate-ping" />
          </div>

          <div className="space-y-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-950 border border-rose-500/40 text-rose-300 text-[11px] font-bold uppercase tracking-wider">
              <AlertCircle className="w-3.5 h-3.5" />
              Koneksi Internet Terputus
            </div>
            <h2 className="text-xl font-black text-slate-100 tracking-tight">
              Tidak Dapat Terhubung Ke Server
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed max-w-xs mx-auto">
              Periksa jaringan Wi-Fi atau Data Seluler Anda. Sesi ujian Anda tetap tersimpan dengan aman di memori perangkat HP.
            </p>
          </div>

          <div className="p-3.5 bg-slate-900/90 rounded-2xl border border-slate-800 text-left text-xs space-y-2">
            <div className="flex items-center gap-2 text-slate-300 font-semibold">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Perlindungan Data Jawaban Ujian:</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-normal pl-6">
              Jangan tutup aplikasi. Jawaban yang telah diketik tersimpan otomatis di HP dan akan disinkronkan saat internet kembali terhubung.
            </p>
          </div>

          <div className="pt-2">
            <Button
              variant="primary"
              className="w-full font-bold shadow-lg shadow-indigo-600/30"
              leftIcon={<RefreshCw className={`w-4 h-4 ${isRetrying ? "animate-spin" : ""}`} />}
              onClick={handleManualRetry}
              disabled={isRetrying}
            >
              {isRetrying ? "Memeriksa Koneksi..." : "Coba Hubungkan Kembali"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
