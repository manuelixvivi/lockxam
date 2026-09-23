import React, { useState, useEffect, useRef } from "react";
import { LogOut, Bell, Sun, Moon, Menu, KeyRound, CheckCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";

export interface TopbarProps {
  onMenuClick?: () => void;
  onNavigate?: (href: string) => void;
  onChangePasswordClick?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ onMenuClick, onNavigate, onChangePasswordClick }) => {
  const { user, logout, role } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);

  const notifRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) return;

    let list = [];
    if (role === "SUPER_ADMIN" || role === "SUPERADMIN") {
      list = [
        { id: "super_admin_1", text: "SMA Negeri 1 Nusantara mengajukan perpanjangan lisensi (3 bulan).", time: "Baru saja", unread: true },
        { id: "super_admin_2", text: "Sekolah baru SMK Telekomunikasi Garuda berhasil didaftarkan.", time: "2 jam yang lalu", unread: true },
        { id: "super_admin_3", text: "Lisensi sekolah SMAS Santo Paulus Medan akan habis dalam 7 hari.", time: "1 hari yang lalu", unread: false },
      ];
    } else if (role === "SCHOOL_ADMIN") {
      list = [
        { id: "school_admin_1", text: "Pengajuan perpanjangan lisensi sekolah Anda telah disetujui!", time: "5 menit yang lalu", unread: true },
        { id: "school_admin_2", text: "Pendaftaran Guru baru Budi Santoso, S.Pd. selesai.", time: "1 jam yang lalu", unread: true },
        { id: "school_admin_3", text: "Tahun Akademik 2025/2026 Semester Ganjil diaktifkan.", time: "1 hari yang lalu", unread: false },
      ];
    } else if (role === "TEACHER") {
      list = [
        { id: "teacher_1", text: "Ujian Harian Matematika selesai. Perlu penilaian essay siswa.", time: "10 menit yang lalu", unread: true },
        { id: "teacher_2", text: "Alert: Siswa Rian Wijaya terdeteksi keluar dari aplikasi Lockxam!", time: "30 menit yang lalu", unread: true },
        { id: "teacher_3", text: "Jadwal Ujian UAS Fisika besok pukul 08:00 WIB.", time: "4 jam yang lalu", unread: false },
      ];
    } else {
      list = [
        { id: "student_1", text: "Ujian Baru: Kuis Harian Sejarah telah dijadwalkan.", time: "1 jam yang lalu", unread: true },
        { id: "student_2", text: "Nilai Rilis: UAS Bahasa Inggris Anda telah dinilai. Hasil: 85/100.", time: "5 jam yang lalu", unread: true },
        { id: "student_3", text: "Proteksi Lockxam aktif untuk sesi ujian berikutnya.", time: "1 hari yang lalu", unread: false },
      ];
    }

    const storageKey = `notifications_read_v3_${user.id || user.email || 'user'}_${role}`;
    try {
      const readIdsRaw = localStorage.getItem(storageKey);
      if (readIdsRaw) {
        const readIds: string[] = JSON.parse(readIdsRaw);
        list = list.map((item) => ({
          ...item,
          unread: readIds.includes(item.id) ? false : item.unread,
        }));
      }
    } catch (e) {
      console.error("Failed to parse notification read state", e);
    }

    setNotifications(list);
  }, [role, user]);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const handleMarkAsRead = (id: string | number) => {
    setNotifications((prev) => {
      const updated = prev.map((n) => (n.id === id ? { ...n, unread: false } : n));
      if (user) {
        const storageKey = `notifications_read_v3_${user.id || user.email || 'user'}_${role}`;
        const readIds = updated.filter((n) => !n.unread).map((n) => n.id);
        localStorage.setItem(storageKey, JSON.stringify(readIds));
      }
      return updated;
    });
  };

  const handleMarkAllAsRead = () => {
    setNotifications((prev) => {
      const updated = prev.map((n) => ({ ...n, unread: false }));
      if (user) {
        const storageKey = `notifications_read_v3_${user.id || user.email || 'user'}_${role}`;
        localStorage.setItem(storageKey, JSON.stringify(updated.map((n) => n.id)));
      }
      return updated;
    });
  };

  // Close dropdowns on outside click (PERBAIKAN: sebelumnya listener kosong)
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setIsNotificationsOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setIsProfileOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const displayName =
    (user as any)?.full_name || (user as any)?.name || (user as any)?.email || "Pengguna";
  const initials = displayName
    .split(" ")
    .map((w: string) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const iconBtn =
    "p-2 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-colors";

  return (
    <header className="h-16 topbar-glass sticky top-0 z-40 shrink-0 flex items-center justify-between px-4 md:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onMenuClick} className={iconBtn} title="Buka Menu">
          <Menu className="w-5 h-5" />
        </button>
        <span className="hidden md:inline text-xs font-semibold text-slate-500 tracking-wide">
          EquiGrade Platform
        </span>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        {/* Theme toggle */}
        <button onClick={toggleTheme} className={iconBtn}
          title={theme === "light" ? "Ganti ke Mode Gelap" : "Ganti ke Mode Terang"}>
          {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button onClick={() => setIsNotificationsOpen((v) => !v)} className={`${iconBtn} relative`} title="Notifikasi">
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-brand-gradient text-white text-[10px] font-bold flex items-center justify-center shadow-lg shadow-indigo-600/40">
                {unreadCount}
              </span>
            )}
          </button>

          {isNotificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 glass-panel !rounded-2xl p-2 z-50 animate-scale-in text-xs">
              <div className="flex items-center justify-between px-3 py-2">
                <span className="font-bold text-slate-200">Notifikasi</span>
                {unreadCount > 0 && (
                  <button onClick={handleMarkAllAsRead}
                    className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold transition-colors">
                    <CheckCheck className="w-3.5 h-3.5" /> Tandai dibaca
                  </button>
                )}
              </div>
              <div className="max-h-72 overflow-y-auto space-y-1">
                {notifications.map((n) => (
                  <button key={n.id} onClick={() => handleMarkAsRead(n.id)}
                    className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-slate-800/50 transition-colors flex gap-2.5">
                    <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${n.unread ? "bg-indigo-400" : "bg-slate-700"}`} />
                    <span className="min-w-0">
                      <span className="block text-slate-200 leading-snug">{n.text}</span>
                      <span className="block text-slate-500 mt-0.5">{n.time}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Profile */}
        <div className="relative" ref={profileRef}>
          <button onClick={() => setIsProfileOpen((v) => !v)}
            className="flex items-center gap-2.5 pl-1.5 pr-2 py-1.5 rounded-2xl hover:bg-slate-800/50 transition-colors">
            <span className="w-8 h-8 rounded-xl bg-brand-gradient flex items-center justify-center text-white text-xs font-bold shadow-lg shadow-indigo-600/30">
              {initials}
            </span>
            <span className="hidden md:block text-left">
              <span className="block text-xs font-semibold text-slate-200 leading-tight">{displayName}</span>
              <span className="block text-[10px] text-slate-500 capitalize">{(role as string || "").toLowerCase().replace("_", " ")}</span>
            </span>
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-56 glass-panel !rounded-2xl p-2 z-50 animate-scale-in text-xs">
              <div className="px-3 py-2.5 border-b border-slate-800 mb-1">
                <p className="font-bold text-slate-200 truncate">{displayName}</p>
                <p className="text-slate-500 truncate mt-0.5">{(user as any)?.email || "-"}</p>
              </div>
              {onChangePasswordClick && (
                <button
                  onClick={() => { setIsProfileOpen(false); onChangePasswordClick(); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-slate-300 hover:bg-slate-800/50 hover:text-slate-100 transition-colors">
                  <KeyRound className="w-4 h-4 text-slate-500" /> Ubah Kata Sandi
                </button>
              )}
              <button
                onClick={() => { logout(); onNavigate && onNavigate("/login"); }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-red-400 hover:bg-red-500/10 transition-colors">
                <LogOut className="w-4 h-4" /> Keluar
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
