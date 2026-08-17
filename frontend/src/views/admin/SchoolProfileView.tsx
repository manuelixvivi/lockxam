import React, { useEffect, useState } from "react";
import {
  Building2,
  Lock,
  Save,
  KeyRound,
  ShieldCheck,
  MapPin,
  Phone,
  Mail,
  Globe,
  Image as ImageIcon,
  CheckCircle2,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { Badge } from "../../components/ui/Badge";
import { useAuth, UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { schoolApi } from "../../api/school";
import type { SchoolProfile, SchoolProfileUpdateRequest } from "../../api/school";
import type { AppApiError } from "../../api/client";

export const SchoolProfileView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {

  const { user } = useAuth();
  const toast = useToast();

  const [profile, setProfile] = useState<SchoolProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [logoLoadFailed, setLogoLoadFailed] = useState<boolean>(false);

  // Editable Form Fields
  const [address, setAddress] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [website, setWebsite] = useState<string>("");
  const [logoUrl, setLogoUrl] = useState<string>("");

  // Change Password Modal States
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState<boolean>(false);
  const [oldPassword, setOldPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [isChangingPassword, setIsChangingPassword] = useState<boolean>(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const fetchProfile = async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (!user?.school_id) {
        throw new Error("Akun Admin tidak terikat dengan ID sekolah.");
      }
      const data = await schoolApi.getSchoolProfile(user.school_id);
      setProfile(data);
      setAddress(data.address || "");
      setPhone(data.phone || "");
      setEmail(data.email || "");
      setWebsite(data.website || "");
      setLogoUrl(data.logo_url || "");
      setLogoLoadFailed(false);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setError(apiErr.message || "Gagal memuat profil sekolah.");
      toast.error("Gagal Memuat Profil", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [user?.school_id]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;

    setIsSaving(true);
    try {
      const payload: SchoolProfileUpdateRequest = {
        address: address.trim() || null,
        phone: phone.trim() || null,
        email: email.trim() || null,
        website: website.trim() || null,
        logo_url: logoUrl.trim() || null,
      };

      const updated = await schoolApi.updateSchoolProfile(profile.public_id, payload);
      setProfile(updated);
      setLogoLoadFailed(false);
      toast.success("Profil Diperbarui", "Data informasi sekolah dan logo berhasil disimpan.");
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Menyimpan", apiErr.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError("Kata sandi baru minimal 8 karakter.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("Konfirmasi kata sandi baru tidak sesuai.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await schoolApi.changeAdminPassword({
        old_password: oldPassword,
        new_password: newPassword,
      });

      toast.success("Kata Sandi Diperbarui", "Kata sandi Admin berhasil diubah.");
      setIsPasswordModalOpen(false);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setPasswordError(apiErr.message || "Gagal mengubah kata sandi.");
    } finally {
      setIsChangingPassword(false);
    }
  };

  const activeDisplayLogo = logoUrl.trim() || profile?.logo_url || null;

  return (
    <AppShell activeHref="/admin/profile" onNavigate={onNavigate}>

      <RoleGuard allowedRoles={[UserRole.SCHOOL_ADMIN]}>
        <Breadcrumb items={[{ label: "School Admin", href: "/admin/dashboard" }, { label: "Profil Sekolah" }]} />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat informasi profil sekolah..." />
          </div>
        ) : error ? (
          <div className="glass-panel p-8 text-center space-y-4 border-red-500/30">
            <p className="text-sm text-red-400 font-medium">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchProfile}>
              Coba Lagi
            </Button>
          </div>
        ) : profile ? (
          <div className="space-y-6">
            {/* Top Banner & Header Info */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 relative overflow-hidden">
              <div className="flex items-center gap-5 z-10">
                <div className="w-16 h-16 rounded-2xl bg-indigo-600/25 border border-indigo-500/40 flex items-center justify-center text-indigo-300 font-black text-2xl shadow-xl shadow-indigo-600/20 overflow-hidden shrink-0">
                  {activeDisplayLogo && !logoLoadFailed ? (
                    <img
                      src={activeDisplayLogo}
                      alt="Logo Sekolah"
                      className="w-full h-full object-cover rounded-2xl"
                      onError={() => setLogoLoadFailed(true)}
                    />
                  ) : (
                    <Building2 className="w-8 h-8" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="indigo">SEKOLAH TERDAFTAR</Badge>
                    <Badge variant={profile.is_active ? "emerald" : "amber"}>
                      {profile.is_active ? "AKTIF" : "PENDING"}
                    </Badge>
                  </div>
                  <h2 className="text-2xl font-black text-slate-100">{profile.name}</h2>
                  <p className="text-xs text-slate-400 mt-1 font-mono">
                    NPSN: <span className="text-slate-200">{profile.npsn}</span> | Kode:{" "}
                    <span className="text-slate-200">{profile.code}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 z-10">
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<KeyRound className="w-4 h-4 text-indigo-400" />}
                  onClick={() => setIsPasswordModalOpen(true)}
                >
                  Ubah Kata Sandi Admin
                </Button>
              </div>
            </div>

            {/* Profile Form Grid */}
            <form onSubmit={handleSaveProfile} className="space-y-6">
              {/* Section 1: Non-Editable / Locked Metadata */}
              <div className="glass-panel p-6 space-y-4 border-indigo-500/20">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm border-b border-slate-800 pb-3">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Identitas Sekolah (Terkunci / Read-Only 🔒)</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Input
                    label="Nama Resmi Sekolah"
                    value={profile.name}
                    disabled
                    readOnly
                    leftIcon={<Lock className="w-4 h-4 text-slate-500" />}
                    helperText="Terkunci: Perubahan nama sekolah wajib melalui SuperAdmin."
                  />
                  <Input
                    label="NPSN (Nomor Pokok Sekolah Nasional)"
                    value={profile.npsn}
                    disabled
                    readOnly
                    leftIcon={<Lock className="w-4 h-4 text-slate-500" />}
                    helperText="Terkunci: Kode NPSN terverifikasi secara nasional."
                  />
                  <Input
                    label="Kode Identifikasi Sistem"
                    value={profile.code}
                    disabled
                    readOnly
                    leftIcon={<Lock className="w-4 h-4 text-slate-500" />}
                  />
                </div>
              </div>

              {/* Section 2: Editable School Profile Information */}
              <div className="glass-panel p-6 space-y-5">
                <div className="flex items-center gap-2 text-slate-100 font-semibold text-sm border-b border-slate-800 pb-3">
                  <Building2 className="w-4 h-4 text-indigo-400" />
                  <span>Informasi Kontak & Logo Operasional (Dapat Diedit ✏️)</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <Input
                      label="Alamat Lengkap Sekolah"
                      placeholder="Jl. Merdeka No. 123, Kel. Merdeka..."
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      leftIcon={<MapPin className="w-4 h-4" />}
                    />
                  </div>

                  <Input
                    label="Nomor Telepon Operasional"
                    placeholder="(021) 555-1234"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    leftIcon={<Phone className="w-4 h-4" />}
                  />

                  <Input
                    label="Email Resmi Sekolah"
                    type="email"
                    placeholder="admin@sekolah.sch.id"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    leftIcon={<Mail className="w-4 h-4" />}
                  />

                  <Input
                    label="Situs Web Resmi"
                    placeholder="https://www.sekolah.sch.id"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                    leftIcon={<Globe className="w-4 h-4" />}
                  />

                  <div className="space-y-2">
                    <Input
                      label="URL Logo Sekolah (Opsional)"
                      placeholder="https://cdn.sekolah.sch.id/logo.png"
                      value={logoUrl}
                      onChange={(e) => {
                        setLogoUrl(e.target.value);
                        setLogoLoadFailed(false);
                      }}
                      leftIcon={<ImageIcon className="w-4 h-4" />}
                      helperText="Masukkan tautan URL gambar (PNG, JPG, SVG) logo sekolah."
                    />

                    {/* Live Logo Preview Box — always visible */}
                    <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-indigo-950 border border-indigo-500/40 flex items-center justify-center overflow-hidden shrink-0">
                        {logoUrl.trim() && !logoLoadFailed ? (
                          <img
                            src={logoUrl.trim()}
                            alt="Preview Logo"
                            className="w-full h-full object-cover"
                            onError={() => setLogoLoadFailed(true)}
                          />
                        ) : (
                          <Building2 className="w-6 h-6 text-indigo-400/60" />
                        )}
                      </div>
                      <div className="text-xs">
                        {!logoUrl.trim() ? (
                          <span className="text-slate-500 font-medium">Belum ada URL logo — masukkan URL untuk pratinjau langsung.</span>
                        ) : logoLoadFailed ? (
                          <span className="text-red-400 font-medium">⚠️ Gagal memuat logo. Pastikan tautan gambar publik dan langsung.</span>
                        ) : (
                          <span className="text-emerald-400 font-medium flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Pratinjau Logo Valid &amp; Siap Disimpan
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Form Footer Action */}
                <div className="flex items-center justify-end pt-4 border-t border-slate-800">
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isSaving}
                    leftIcon={<Save className="w-4 h-4" />}
                  >
                    Simpan Perubahan Profil
                  </Button>
                </div>
              </div>
            </form>
          </div>
        ) : null}

        {/* Change Password Modal */}
        <Modal
          isOpen={isPasswordModalOpen}
          onClose={() => {
            setIsPasswordModalOpen(false);
            setPasswordError(null);
          }}
          title="Ubah Kata Sandi Admin Sekolah"
          subtitle="Masukkan kata sandi lama dan tentukan kata sandi baru untuk akun Admin Sekolah ini."
          maxWidth="md"
        >
          <form onSubmit={handleChangePassword} className="space-y-4">
            {passwordError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {passwordError}
              </div>
            )}

            <Input
              label="Kata Sandi Saat Ini"
              type="password"
              placeholder="••••••••"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />

            <Input
              label="Kata Sandi Baru"
              type="password"
              placeholder="••••••••"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              helperText="Minimal 8 karakter."
              required
            />

            <Input
              label="Konfirmasi Kata Sandi Baru"
              type="password"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsPasswordModalOpen(false);
                  setPasswordError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isChangingPassword}>
                Perbarui Kata Sandi
              </Button>
            </div>
          </form>
        </Modal>
      </RoleGuard>
    </AppShell>
  );
};
