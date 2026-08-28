import React, { useState, useEffect } from "react";
import { LogOut, User, Building, Bell, Sun, Moon, Menu, KeyRound } from "lucide-react";
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

  // Dropdown states
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);

  // Mock Notifications
  const [notifications, setNotifications] = useState<any[]>([]);

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

    // Load read status from localStorage with robust user & role key
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
        const readIds = updated.map((n) => n.id);
        localStorage.setItem(storageKey, JSON.stringify(readIds));
      }
      return updated;
    });
  };

  // Close dropdowns on clicking outside (simplified)
  useEffect(() => {
    const handleOutsideClick = () => {
      // Close dropdowns when clicking anywhere else
    };
    window.addEventListener("click", handleOutsideClick);
    return () => window.removeEventListener("click", handleOutsideClick);
  }, []);

  return (
    <header className="h-16 bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md sticky top-0 z-40 shrink-0 flex items-center justify-between px-6">
      {/* Context Badge & Menu Toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="p-2 -ml-1 rounded-xl text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-colors"
          title="Buka Menu"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>

      {/* Profile & Controls */}
      <div className="flex items-center gap-4">
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
          title={theme === "light" ? "Ganti ke Mode Gelap" : "Ganti ke Mode Terang"}
        >
          {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
        </button>

        {/* Notification Bell with Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setIsNotificationsOpen(!isNotificationsOpen);
              setIsProfileOpen(false);
            }}
            className={`relative p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors ${
              isNotificationsOpen ? "bg-slate-800/60 text-slate-200" : ""
            }`}
            title="Notifikasi"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-indigo-500 text-[10px] font-black text-white flex items-center justify-center border border-slate-900">
                {unreadCount}
              </span>
            )}
          </button>

          {isNotificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-slate-900 border border-slate-800 p-3 shadow-2xl z-50 animate-fade-in text-xs">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
                <span className="font-bold text-slate-200 text-sm">Notifikasi Pusat</span>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllAsRead}
                    className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    Tandai Semua Dibaca
                  </button>
                )}
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {notifications.length === 0 ? (
                  <p className="text-slate-500 text-center py-4">Tidak ada notifikasi.</p>
                ) : (
                  notifications.map((n) => (
                    <button
                      key={n.id}
                      onClick={() => handleMarkAsRead(n.id)}
                      className={`w-full p-2.5 rounded-xl text-left border transition-all duration-200 ${
                        n.unread
                          ? "bg-indigo-600/5 border-indigo-500/20 text-slate-200"
                          : "bg-slate-950/20 border-slate-800/30 text-slate-400 hover:bg-slate-800/20"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium leading-relaxed">{n.text}</p>
                        {n.unread && (
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0 mt-1" />
                        )}
                      </div>
                      <span className="block text-[10px] text-slate-500 mt-1 font-mono">{n.time}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-slate-800"></div>

        {/* User Card with Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setIsProfileOpen(!isProfileOpen);
              setIsNotificationsOpen(false);
            }}
            className={`flex items-center gap-3 p-1.5 rounded-xl hover:bg-slate-800/50 transition-colors text-left ${
              isProfileOpen ? "bg-slate-800/50" : ""
            }`}
          >
            <div className="w-8 h-8 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-300 font-semibold text-xs shrink-0">
              {user?.full_name?.charAt(0).toUpperCase() || <User className="w-4 h-4" />}
            </div>
            <div className="hidden sm:block">
              <p className="text-xs font-semibold text-slate-200 leading-none">{user?.full_name || "Pengguna"}</p>
              <p className="text-[10px] text-slate-400 mt-1 leading-none">{user?.email}</p>
            </div>
          </button>

          {isProfileOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-slate-900 border border-slate-800 p-2 shadow-2xl z-50 animate-fade-in">
              <div className="px-3 py-2.5 border-b border-slate-800/60 mb-1">
                <p className="text-xs font-semibold text-slate-400">Masuk sebagai:</p>
                <p className="text-xs font-bold text-slate-200 mt-0.5 truncate">{user?.full_name}</p>
              </div>

              {role === "SCHOOL_ADMIN" && onNavigate && (
                <button
                  onClick={() => {
                    setIsProfileOpen(false);
                    onNavigate("/admin/profile");
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-slate-100 hover:bg-slate-800/60 transition-colors text-left"
                >
                  <Building className="w-4 h-4 text-slate-400" />
                  <span>Profil Sekolah</span>
                </button>
              )}

              {onChangePasswordClick && (
                <button
                  onClick={() => {
                    setIsProfileOpen(false);
                    onChangePasswordClick();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-slate-100 hover:bg-slate-800/60 transition-colors text-left mt-1"
                >
                  <KeyRound className="w-4 h-4 text-slate-400" />
                  <span>Ubah Kata Sandi</span>
                </button>
              )}

              <button
                onClick={() => {
                  setIsProfileOpen(false);
                  logout();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-red-400 hover:bg-red-500/10 transition-colors text-left mt-1"
              >
                <LogOut className="w-4 h-4 text-red-400" />
                <span>Keluar (Logout)</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
