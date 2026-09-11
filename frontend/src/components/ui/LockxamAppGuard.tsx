import React, { useState, useEffect } from "react";
import { ShieldAlert, Smartphone, QrCode, Lock, CheckCircle2 } from "lucide-react";
import { Button } from "./Button";
import { Badge } from "./Badge";
import { ServerHealthIndicator } from "./ServerHealthIndicator";

interface LockxamAppGuardProps {
  children: React.ReactNode;
}

export const LockxamAppGuard: React.FC<LockxamAppGuardProps> = ({ children }) => {
  const [isCustomApp, setIsCustomApp] = useState<boolean>(false);
  const [isChecking, setIsChecking] = useState<boolean>(true);
  const [showQrModal, setShowQrModal] = useState<boolean>(false);

  useEffect(() => {
    // Check User-Agent or Custom Window Flag
    const ua = navigator.userAgent || "";
    const isAppUA =
      ua.includes("Lockxam") ||
      ua.includes("LockxamBrowser") ||
      ua.includes("EquigradeApp") ||
      (window as any).isLockxamApp === true;

    setIsCustomApp(Boolean(isAppUA));
    setIsChecking(false);
  }, []);

  if (isChecking) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium">Verifikasi Lingkungan Browser Lockxam...</span>
        </div>
      </div>
    );
  }

  if (!isCustomApp) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 relative overflow-hidden">
        {/* Background Decorative Glows */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-rose-600/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 right-10 w-80 h-80 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 w-full max-w-xl bg-slate-900/90 border border-rose-900/40 rounded-3xl p-8 shadow-2xl backdrop-blur-xl space-y-6">
          {/* Header Badge & Title */}
          <div className="flex flex-col items-center text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-rose-950/80 border border-rose-800/60 flex items-center justify-center shadow-inner">
              <ShieldAlert className="w-9 h-9 text-rose-400 animate-pulse" />
            </div>
            <div className="space-y-1">
              <Badge variant="crimson">AKSES DIBATASI — APLIKASI KHUSUS SISWA</Badge>
              <h1 className="text-2xl font-black tracking-tight text-white">
                Memerlukan Custom Browser Lockxam APK
              </h1>
            </div>
            <p className="text-slate-400 text-xs leading-relaxed max-w-md">
              Halaman ujian siswa <span className="text-rose-300 font-semibold">Equigrade x Lockxam</span> dilindungi oleh protokol keamanan anti-kecurangan ketat dan <span className="text-white font-bold">tidak dapat diakses melalui browser publik</span> (Chrome, Edge, Safari, Firefox).
            </p>
          </div>

          {/* Feature List Security Banner */}
          <div className="bg-slate-950/80 rounded-2xl p-4 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Lock className="w-4 h-4 text-indigo-400" />
              Fitur Keamanan Aplikasi Lockxam Browser:
            </h3>
            <ul className="space-y-2 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Memblokir pemindahan tab, split-screen, dan pop-up browser</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Mencegah perekaman layar (screenshot / screen-recorder)</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Auto Device Binding & IP Fingerprint Verification</span>
              </li>
            </ul>
          </div>

          {/* Live Server Connection Indicator */}
          <ServerHealthIndicator />

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
            <Button
              className="w-full sm:flex-1"
              variant="primary"
              leftIcon={<Smartphone className="w-4 h-4" />}
              onClick={() => alert("Mengunduh installer Lockxam App Client (APK / Windows Kiosk Executable)...")}
            >
              Unduh Lockxam APK Resmi
            </Button>
            <Button
              className="w-full sm:w-auto"
              variant="outline"
              leftIcon={<QrCode className="w-4 h-4 text-indigo-400" />}
              onClick={() => setShowQrModal(true)}
            >
              QR Code
            </Button>
          </div>
        </div>

        {/* QR Code Modal */}
        {showQrModal && (
          <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-xs w-full text-center space-y-4 shadow-2xl">
              <h3 className="text-sm font-bold text-white">Pindai QR Code untuk Unduh APK</h3>
              <div className="bg-white p-4 rounded-2xl inline-block mx-auto shadow-inner">
                <img
                  src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=https://equigrade.school/download/lockxam-client.apk"
                  alt="QR Code Lockxam APK"
                  className="w-40 h-40"
                />
              </div>
              <p className="text-xs text-slate-400">
                Pindai dengan kamera smartphone untuk langsung mengunduh Lockxam Student Client APK.
              </p>
              <Button variant="ghost" size="sm" onClick={() => setShowQrModal(false)}>
                Tutup
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return <>{children}</>;
};
