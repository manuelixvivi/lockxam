import React, { useEffect, useState } from "react";
import {
  Building2,
  Plus,
  Search,
  Pencil,
  Trash2,
  Building,
  MapPin,
  Phone,
  Mail,
  Globe,
  Lock,
  KeyRound,
  UserCheck,
  Copy,
  Check,
  Pause,
  Play,
  Calendar,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import type { SelectOption } from "../../components/ui/Select";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { Badge } from "../../components/ui/Badge";
import { Table } from "../../components/ui/Table";
import { UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { superadminApi } from "../../api/superadmin";
import type { CreateSchoolPayload, SchoolLevelOption } from "../../api/superadmin";
import type { SchoolProfile } from "../../api/school";
import type { AppApiError } from "../../api/client";
import { ImportExportBar } from "../../components/ui/ImportExportBar";
import { copyToClipboard } from "../../utils/clipboard";

export const SuperAdminSchoolsView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {
  const toast = useToast();

  const [schools, setSchools] = useState<SchoolProfile[]>([]);
  const [levels, setLevels] = useState<SchoolLevelOption[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalSchools, setTotalSchools] = useState<number>(0);
  const pageSize = 20;

  // Modal States
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [selectedSchool, setSelectedSchool] = useState<SchoolProfile | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Reset Password Modal State
  const [resetResult, setResetResult] = useState<{
    schoolName: string;
    username: string;
    newPassword: string;
    type?: "create" | "reset";
  } | null>(null);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // Form Field States
  const [npsn, setNpsn] = useState<string>("");
  const [code, setCode] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [schoolLevelId, setSchoolLevelId] = useState<string>("4"); // Default SMA
  const [address, setAddress] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [website, setWebsite] = useState<string>("");
  const [logoUrl, setLogoUrl] = useState<string>("");
  const [domain, setDomain] = useState<string>("");
  const [initialSubscriptionPreset, setInitialSubscriptionPreset] = useState<string>("ONE_MONTH");

  const fetchSchools = async (page: number = 1, search: string = searchQuery) => {
    setIsLoading(true);
    try {
      const paginatedRes = await superadminApi.getSchoolsPaginated(page, pageSize, search || undefined);
      setSchools(paginatedRes.items);
      setTotalSchools(paginatedRes.total);
      setCurrentPage(paginatedRes.page);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memuat Sekolah", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  const ensureLevelsLoaded = async () => {
    if (levels.length > 0) return levels;
    try {
      const levelsData = await superadminApi.getSchoolLevels();
      setLevels(levelsData);
      if (levelsData.length > 0 && !schoolLevelId) {
        setSchoolLevelId(levelsData[0].id.toString());
      }
      return levelsData;
    } catch {
      return [];
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSchools(1, searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const resetForm = () => {
    setNpsn("");
    setCode("");
    setName("");
    setAddress("");
    setPhone("");
    setEmail("");
    setWebsite("");
    setLogoUrl("");
    setDomain("");
    setInitialSubscriptionPreset("ONE_MONTH");
    setFormError(null);
    setSelectedSchool(null);
  };

  const handleOpenCreate = async () => {
    resetForm();
    setCode(`SCH_${Math.floor(1000 + Math.random() * 9000)}`);
    await ensureLevelsLoaded();
    setIsCreateModalOpen(true);
  };

  const handleOpenEdit = async (school: SchoolProfile) => {
    resetForm();
    setSelectedSchool(school);
    setNpsn(school.npsn || "");
    setCode(school.code || "");
    setName(school.name || "");
    setSchoolLevelId(school.school_level_id?.toString() || "4");
    setAddress(school.address || "");
    setPhone(school.phone || "");
    setEmail(school.email || "");
    setWebsite(school.website || "");
    setLogoUrl(school.logo_url || "");
    setDomain(school.domain || "");
    await ensureLevelsLoaded();
    setIsEditModalOpen(true);
  };

  const handleCreateSchool = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!name.trim() || !npsn.trim() || !code.trim() || !domain.trim()) {
      setFormError("Nama sekolah, NPSN, Kode Sekolah, dan Domain wajib diisi.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: CreateSchoolPayload = {
        npsn: npsn.trim(),
        code: code.trim(),
        name: name.trim(),
        school_level_id: parseInt(schoolLevelId, 10),
        domain: domain.trim(),
        initial_subscription_preset: initialSubscriptionPreset,
        address: address.trim() || undefined,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        website: website.trim() || undefined,
        logo_url: logoUrl.trim() || undefined,
      };

      const res = await superadminApi.createSchool(payload);
      toast.success("Sekolah Terdaftar", `Sekolah ${name} berhasil didaftarkan ke sistem.`);
      setIsCreateModalOpen(false);
      resetForm();
      fetchSchools(currentPage);
      setResetResult({
        schoolName: res.school.name,
        username: res.admin_credentials.username,
        newPassword: res.admin_credentials.temporary_password,
        type: "create",
      });
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setFormError(apiErr.message || "Gagal mendaftarkan sekolah baru.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdateSchool = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSchool) return;
    setFormError(null);

    setIsSubmitting(true);
    try {
      const payload: Partial<CreateSchoolPayload> = {
        npsn: npsn.trim(),
        code: code.trim(),
        name: name.trim(),
        school_level_id: parseInt(schoolLevelId, 10),
        domain: domain.trim(),
        address: address.trim() || undefined,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        website: website.trim() || undefined,
        logo_url: logoUrl.trim() || undefined,
      };


      await superadminApi.updateSchool(selectedSchool.public_id, payload);
      toast.success("Profil Sekolah Diperbarui", `Data ${name} berhasil disimpan.`);
      setIsEditModalOpen(false);
      resetForm();
      fetchSchools(currentPage);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setFormError(apiErr.message || "Gagal memperbarui profil sekolah.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetAdminPassword = async (school: SchoolProfile) => {
    if (
      !window.confirm(
        `Apakah Anda yakin ingin mereset kata sandi Admin Sekolah untuk ${school.name}?`
      )
    ) {
      return;
    }

    setIsResetting(true);
    try {
      const res = await superadminApi.resetSchoolAdminPassword(school.public_id);
      setResetResult({
        schoolName: school.name,
        username: res.username,
        newPassword: res.new_password,
        type: "reset",
      });
      toast.success(
        "Password Berhasil Direset",
        `Kata sandi baru untuk Admin Sekolah ${school.name} telah diterbitkan.`
      );
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Reset Password", apiErr.message);
    } finally {
      setIsResetting(false);
    }
  };

  const handleCopyCredentials = async () => {
    if (resetResult && resetResult.username && resetResult.newPassword) {
      const textToCopy = `Kredensial Admin Sekolah ${resetResult.schoolName}\nUsername: ${resetResult.username}\nPassword: ${resetResult.newPassword}`;
      const success = await copyToClipboard(textToCopy);
      if (success) {
        setIsCopied(true);
        toast.success("Disalin!", "Kredensial Admin Sekolah telah disalin.");
        setTimeout(() => setIsCopied(false), 2000);
      } else {
        toast.error("Gagal Menyalin", "Gagal menyalin kredensial secara otomatis.");
      }
    }
  };

  const handleDeleteSchool = async (school: SchoolProfile) => {
    if (!window.confirm(`Apakah Anda yakin ingin menghapus/nonaktifkan ${school.name}?`)) {
      return;
    }

    try {
      await superadminApi.deleteSchool(school.public_id);
      toast.success("Sekolah Dihapus", `Sekolah ${school.name} berhasil dinonaktifkan.`);
      fetchSchools(currentPage);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Menghapus", apiErr.message);
    }
  };

  const totalPages = Math.max(1, Math.ceil(totalSchools / pageSize));

  const levelOptions: SelectOption[] = levels.map((l) => ({
    value: l.id,
    label: `${l.name} (${l.code})`,
  }));

  const handleToggleSubscription = async (school: SchoolProfile) => {
    try {
      const updated = await superadminApi.toggleSchoolSubscription(school.public_id);
      const isSuspended = updated.subscription_status === "SUSPENDED";
      toast.success(
        isSuspended ? "Subscription Dijeda ⏸️" : "Subscription Aktif ▶️",
        `Subscription ${school.name} berhasil ${isSuspended ? "dijeda / ditangguhkan" : "diaktifkan kembali"}.`
      );
      fetchSchools(currentPage);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Mengubah Subscription", apiErr.message);
    }
  };

  return (
    <AppShell activeHref="/superadmin/schools" onNavigate={onNavigate}>
      <RoleGuard allowedRoles={[UserRole.SUPER_ADMIN]}>
        <Breadcrumb
          items={[{ label: "SuperAdmin Workspace", href: "/superadmin/dashboard" }, { label: "Manajemen Sekolah" }]}
        />

        {isLoading && schools.length === 0 ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat data sekolah central..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">CENTRAL MANAGEMENT</Badge>
                  <Badge variant="emerald">{totalSchools} SEKOLAH TERDAFTAR</Badge>
                </div>
                <h2 className="text-2xl font-black text-slate-100">Manajemen Sekolah Central</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Kelola pendaftaran tenant sekolah, reset kata sandi admin sekolah, dan jeda/aktifkan subscription.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={handleOpenCreate}
                >
                  Registrasi Sekolah Baru
                </Button>

              </div>
            </div>

            {/* Filter & Search + Export/Import Bar */}
            <div className="glass-panel p-4 space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex-1 max-w-md">
                  <Input
                    placeholder="Cari nama sekolah, NPSN, atau kode..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    leftIcon={<Search className="w-4 h-4" />}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="md"
                  leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
                  onClick={() => fetchSchools(currentPage, searchQuery)}
                  isLoading={isLoading}
                  title="Muat ulang data"
                  className="shrink-0"
                >
                  Refresh
                </Button>
              </div>
              <ImportExportBar<Record<string, unknown>>
                exportData={schools.map((s) => ({
                  NPSN: s.npsn,
                  Kode: s.code,
                  "Nama Sekolah": s.name,
                  Alamat: s.address || "",
                  Telepon: s.phone || "",
                  Email: s.email || "",
                  Website: s.website || "",
                  Domain: s.domain || "",
                  "Status Subscription": (s as any).subscription_status || "",
                }))}
                exportColumns={[
                  { label: "NPSN", key: "NPSN" },
                  { label: "Kode", key: "Kode" },
                  { label: "Nama Sekolah", key: "Nama Sekolah" },
                  { label: "Alamat", key: "Alamat" },
                  { label: "Telepon", key: "Telepon" },
                  { label: "Email", key: "Email" },
                  { label: "Website", key: "Website" },
                  { label: "Domain", key: "Domain" },
                  { label: "Status Subscription", key: "Status Subscription" },
                ]}
                exportFilename="daftar-sekolah"
                sheetName="Sekolah"
                templateHeaders={["NPSN", "Kode", "Nama Sekolah", "Jenjang (SD/SMP/SMA/SMK)", "Domain", "Alamat", "Telepon", "Email", "Website", "Durasi Awal (ONE_MONTH/ONE_YEAR/PERMANENT)"]}
                templateSamples={[
                  { NPSN: "10000001", Kode: "SCH_0001", "Nama Sekolah": "SMA Negeri 1 Contoh", "Jenjang (SD/SMP/SMA/SMK)": "SMA", Domain: "sma1contoh", Alamat: "Jl. Contoh No. 1", Telepon: "021-1234567", Email: "admin@sma1.sch.id", Website: "https://sma1.sch.id", "Durasi Awal (ONE_MONTH/ONE_YEAR/PERMANENT)": "ONE_MONTH" },
                ]}
                templateFilename="template-import-sekolah"
                onImportRow={async (row) => {
                  try {
                    const npsn = String(row["NPSN"] || "").trim();
                    const kode = String(row["Kode"] || "").trim();
                    const nama = String(row["Nama Sekolah"] || "").trim();
                    const domain = String(row["Domain"] || "").trim();
                    const durasiPreset = String(row["Durasi Awal (ONE_MONTH/ONE_YEAR/PERMANENT)"] || "ONE_MONTH").trim();
                    if (!npsn || !kode || !nama || !domain) return "NPSN, Kode, Nama Sekolah, dan Domain wajib diisi.";
                    const jenjangStr = String(row["Jenjang (SD/SMP/SMA/SMK)"] || "SMA").trim().toUpperCase();
                    const jenjangMap: Record<string, number> = { SD: 1, SMP: 2, MTs: 3, SMA: 4, SMK: 5, MA: 6 };
                    const levelId = jenjangMap[jenjangStr] || 4;
                    await superadminApi.createSchool({
                      npsn, code: kode, name: nama, domain,
                      school_level_id: levelId,
                      initial_subscription_preset: durasiPreset,
                      address: String(row["Alamat"] || "").trim() || undefined,
                      phone: String(row["Telepon"] || "").trim() || undefined,
                      email: String(row["Email"] || "").trim() || undefined,
                      website: String(row["Website"] || "").trim() || undefined,
                    });
                    return null;
                  } catch (err: any) {
                    return err?.message || "Gagal mendaftarkan sekolah.";
                  }
                }}
                onImportDone={() => fetchSchools(1, "")}
              />
            </div>

            {/* Main Schools List (Responsive: Desktop Table / Mobile Cards) */}
            <div>
              {/* Desktop Table (Visible on medium screens and up) */}
              <div className="hidden md:block glass-panel p-6">
                <Table
                  columns={[
                    {
                      key: "code",
                      header: "Kode & NPSN",
                      width: "140px",
                      render: (item: SchoolProfile) => (
                        <div>
                          <div className="flex items-center gap-1">
                            <span className="font-mono text-xs font-bold text-indigo-400">{item.code}</span>
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.stopPropagation();
                                const success = await copyToClipboard(item.code);
                                if (success) {
                                  toast.success("Disalin!", "Kode sekolah berhasil disalin.");
                                } else {
                                  toast.error("Gagal Menyalin", "Gagal menyalin kode sekolah.");
                                }
                              }}
                              className="text-slate-500 hover:text-indigo-400 transition-colors p-0.5"
                              title="Salin Kode Sekolah"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                          <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400 mt-0.5">
                            <span>NPSN: {item.npsn}</span>
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.stopPropagation();
                                const success = await copyToClipboard(item.npsn);
                                if (success) {
                                  toast.success("Disalin!", "NPSN berhasil disalin.");
                                } else {
                                  toast.error("Gagal Menyalin", "Gagal menyalin NPSN.");
                                }
                              }}
                              className="text-slate-550 hover:text-indigo-400 transition-colors p-0.5"
                              title="Salin NPSN"
                            >
                              <Copy className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "name",
                      header: "Nama Sekolah",
                      render: (item: SchoolProfile) => (
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 font-bold shrink-0">
                            {item.logo_url ? (
                              <img src={item.logo_url} alt="Logo" className="w-full h-full object-cover rounded-xl" />
                            ) : (
                              <Building className="w-5 h-5" />
                            )}
                          </div>
                          <div>
                            <div className="font-bold text-slate-100">{item.name}</div>
                            <div className="text-xs text-slate-400">{item.address || "Alamat belum diatur"}</div>
                            {item.domain && (
                              <div className="inline-flex items-center gap-1 mt-1 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                                Domain: @{item.domain}
                              </div>
                            )}
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "admin_username",
                      header: "Akun Admin Sekolah",
                      render: (item: SchoolProfile) => {
                        const uname = (item as any).admin_username || (item.domain ? `admin@admin.${item.domain}` : `admin_${item.npsn}`);
                        return (
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-purple-300">
                              <UserCheck className="w-3.5 h-3.5 text-purple-400" />
                              <span>{uname}</span>
                              <button
                                type="button"
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  const success = await copyToClipboard(uname);
                                  if (success) {
                                    toast.success("Disalin!", "Username Admin berhasil disalin.");
                                  } else {
                                    toast.error("Gagal Menyalin", "Gagal menyalin username admin.");
                                  }
                                }}
                                className="text-slate-500 hover:text-purple-400 transition-colors p-0.5"
                                title="Salin Username Admin"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                            <div className="text-[10px] text-slate-400">{item.email || "Email resmi"}</div>
                          </div>
                        );
                      },
                    },
                    {
                      key: "subscription_status",
                      header: "Status Subscription",
                      width: "150px",
                      render: (item: SchoolProfile) => {
                        const subStatus = (item as any).subscription_status || "NO_LICENSE";
                        if (subStatus === "ACTIVE") {
                          return <Badge variant="emerald">AKTIF</Badge>;
                        }
                        if (subStatus === "SUSPENDED" || subStatus === "PAUSED") {
                          return <Badge variant="crimson">DIJEDA</Badge>;
                        }
                        if (subStatus === "EXPIRED") {
                          return <Badge variant="amber">EXPIRED</Badge>;
                        }
                        return <Badge variant="slate">TANPA LISENSI</Badge>;
                      },
                    },
                    {
                      key: "subscription_end_date",
                      header: "Berakhir s/d",
                      width: "130px",
                      render: (item: SchoolProfile) => {
                        const endDateStr = (item as any).subscription_end_date;
                        if (!endDateStr) return <span className="text-xs text-slate-500 font-mono">-</span>;
                        const isPermanent = new Date(endDateStr).getFullYear() > 2070;
                        if (isPermanent) {
                          return (
                            <div className="flex items-center gap-1 text-xs font-bold text-emerald-400">
                              <span>Permanen ♾️</span>
                            </div>
                          );
                        }
                        return (
                          <div className="flex items-center gap-1 text-xs font-medium text-slate-300">
                            <Calendar className="w-3 h-3 text-indigo-400" />
                            <span>
                              {new Date(endDateStr).toLocaleDateString("id-ID", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })}
                            </span>
                          </div>
                        );
                      },
                    },
                    {
                      key: "actions",
                      header: "Aksi Management",
                      width: "280px",
                      render: (item: SchoolProfile) => {
                        const isSuspended = (item as any).subscription_status === "SUSPENDED";
                        return (
                          <div className="flex items-center gap-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              leftIcon={<KeyRound className="w-3.5 h-3.5 text-amber-400" />}
                              onClick={() => handleResetAdminPassword(item)}
                              isLoading={isResetting}
                            >
                              Reset Pass
                            </Button>
                            <Button
                              variant={isSuspended ? "primary" : "ghost"}
                              size="sm"
                              leftIcon={
                                isSuspended ? (
                                  <Play className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                  <Pause className="w-3.5 h-3.5 text-amber-400" />
                                )
                              }
                              onClick={() => handleToggleSubscription(item)}
                            >
                              {isSuspended ? "Aktifkan" : "Jeda"}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              leftIcon={<Pencil className="w-3.5 h-3.5" />}
                              onClick={() => handleOpenEdit(item)}
                            />
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                              onClick={() => handleDeleteSchool(item)}
                            />
                          </div>
                        );
                      },
                    },
                  ]}
                  data={schools}
                  keyExtractor={(item) => item.id.toString()}
                />
              </div>

              {/* Mobile Cards Grid (Visible on mobile/small screens) */}
              <div className="grid grid-cols-1 gap-4 md:hidden">
                {schools.length === 0 ? (
                  <div className="glass-panel p-8 text-center text-slate-500">
                    Tidak ada sekolah tersedia.
                  </div>
                ) : (
                  schools.map((item) => {
                    const isSuspended = (item as any).subscription_status === "SUSPENDED";
                    const subStatus = (item as any).subscription_status || "NO_LICENSE";
                    const endDateStr = (item as any).subscription_end_date;
                    const isPermanent = endDateStr && new Date(endDateStr).getFullYear() > 2070;

                    return (
                      <div key={item.id} className="glass-panel p-5 space-y-4">
                        {/* Header: School info */}
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 font-bold shrink-0">
                            {item.logo_url ? (
                              <img src={item.logo_url} alt="Logo" className="w-full h-full object-cover rounded-xl" />
                            ) : (
                              <Building className="w-6 h-6" />
                            )}
                          </div>
                          <div className="space-y-0.5">
                            <h4 className="font-bold text-slate-100 text-sm leading-snug">{item.name}</h4>
                            <p className="text-xs text-slate-400 line-clamp-1">{item.address || "Alamat belum diatur"}</p>
                          </div>
                        </div>

                        {/* Badges: Code, NPSN, and Domain Suffix */}
                        <div className="flex flex-wrap gap-2 text-xs">
                          <span className="bg-slate-800 text-indigo-400 px-2 py-0.5 rounded font-mono text-[10px] flex items-center gap-1">
                            {item.code}
                            <button
                              type="button"
                              onClick={async () => {
                                const success = await copyToClipboard(item.code);
                                if (success) {
                                  toast.success("Disalin!", "Kode sekolah disalin.");
                                } else {
                                  toast.error("Gagal Menyalin", "Gagal menyalin kode sekolah.");
                                }
                              }}
                              className="text-slate-500 hover:text-indigo-400 p-0.5"
                            >
                              <Copy className="w-2.5 h-2.5" />
                            </button>
                          </span>
                          <span className="bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono text-[10px] flex items-center gap-1">
                            NPSN: {item.npsn}
                            <button
                              type="button"
                              onClick={async () => {
                                const success = await copyToClipboard(item.npsn);
                                if (success) {
                                  toast.success("Disalin!", "NPSN disalin.");
                                } else {
                                  toast.error("Gagal Menyalin", "Gagal menyalin NPSN.");
                                }
                              }}
                              className="text-slate-550 hover:text-indigo-400 p-0.5"
                            >
                              <Copy className="w-2.5 h-2.5" />
                            </button>
                          </span>
                          {item.domain && (
                            <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-bold text-[10px]">
                              @{item.domain}
                            </span>
                          )}
                        </div>

                        {/* Details Block */}
                        <div className="p-3 bg-slate-950/60 rounded-xl space-y-2 text-xs border border-slate-800/40">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 font-semibold">Admin Account:</span>
                            <span className="font-mono text-purple-300 font-bold flex items-center gap-1">
                              {(item as any).admin_username || (item.domain ? `admin@admin.${item.domain}` : `admin_${item.npsn}`)}
                              <button
                                type="button"
                                onClick={async () => {
                                  const uname = (item as any).admin_username || (item.domain ? `admin@admin.${item.domain}` : `admin_${item.npsn}`);
                                  const success = await copyToClipboard(uname);
                                  if (success) {
                                    toast.success("Disalin!", "Username Admin disalin.");
                                  } else {
                                    toast.error("Gagal Menyalin", "Gagal menyalin username admin.");
                                  }
                                }}
                                className="text-slate-500 hover:text-purple-400 p-0.5"
                              >
                                <Copy className="w-2.5 h-2.5" />
                              </button>
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 font-semibold">Status:</span>
                            {subStatus === "ACTIVE" ? (
                              <Badge variant="emerald">AKTIF</Badge>
                            ) : subStatus === "SUSPENDED" || subStatus === "PAUSED" ? (
                              <Badge variant="crimson">DIJEDA</Badge>
                            ) : subStatus === "EXPIRED" ? (
                              <Badge variant="amber">EXPIRED</Badge>
                            ) : (
                              <Badge variant="slate">TANPA LISENSI</Badge>
                            )}
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 font-semibold">Berakhir s/d:</span>
                            {isPermanent ? (
                              <span className="font-bold text-emerald-400">Permanen ♾️</span>
                            ) : endDateStr ? (
                              <span className="text-slate-300 font-medium font-mono">
                                {new Date(endDateStr).toLocaleDateString("id-ID")}
                              </span>
                            ) : (
                              <span className="text-slate-500 font-mono">-</span>
                            )}
                          </div>
                        </div>

                        {/* Action buttons grid */}
                        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800/50">
                          <Button
                            variant="secondary"
                            size="sm"
                            leftIcon={<KeyRound className="w-3.5 h-3.5 text-amber-400" />}
                            onClick={() => handleResetAdminPassword(item)}
                            isLoading={isResetting}
                            className="flex-1 min-w-[100px]"
                          >
                            Reset Pass
                          </Button>
                          <Button
                            variant={isSuspended ? "primary" : "ghost"}
                            size="sm"
                            leftIcon={
                              isSuspended ? (
                                <Play className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Pause className="w-3.5 h-3.5 text-amber-400" />
                              )
                            }
                            onClick={() => handleToggleSubscription(item)}
                            className="flex-1 min-w-[80px]"
                          >
                            {isSuspended ? "Aktifkan" : "Jeda"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            leftIcon={<Pencil className="w-3.5 h-3.5" />}
                            onClick={() => handleOpenEdit(item)}
                            className="px-3"
                          />
                          <Button
                            variant="danger"
                            size="sm"
                            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                            onClick={() => handleDeleteSchool(item)}
                            className="px-3"
                          />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Server-Side Pagination Bar */}
              {totalSchools > 0 && (
                <div className="glass-panel p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="text-xs text-slate-400">
                    Menampilkan <span className="text-slate-100 font-bold">{schools.length}</span> dari{" "}
                    <span className="text-slate-100 font-bold">{totalSchools}</span> sekolah (Halaman{" "}
                    <span className="text-indigo-400 font-semibold">{currentPage}</span> dari{" "}
                    <span className="text-indigo-400 font-semibold">{totalPages}</span>)
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={<ChevronLeft className="w-4 h-4" />}
                      disabled={currentPage <= 1 || isLoading}
                      onClick={() => fetchSchools(currentPage - 1, searchQuery)}
                    >
                      Sebelumnya
                    </Button>
                    <div className="px-3 py-1 rounded bg-slate-900 border border-slate-800 text-xs font-mono text-indigo-400 font-bold">
                      {currentPage} / {totalPages}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      rightIcon={<ChevronRight className="w-4 h-4" />}
                      disabled={currentPage >= totalPages || isLoading}
                      onClick={() => fetchSchools(currentPage + 1, searchQuery)}
                    >
                      Selanjutnya
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Modal: Result Reset Password / Registrasi Admin Sekolah */}
        <Modal
          isOpen={!!resetResult}
          onClose={() => setResetResult(null)}
          title={
            resetResult?.type === "create"
              ? "Sekolah Berhasil Didaftarkan"
              : "Kata Sandi Admin Sekolah Berhasil Direset"
          }
          subtitle={
            resetResult?.type === "create"
              ? `Kredensial login admin default untuk ${resetResult?.schoolName}.`
              : `Informasi kredensial baru untuk ${resetResult?.schoolName}.`
          }
          maxWidth="md"
        >
          {resetResult && (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-amber-950/40 border border-amber-500/40 space-y-3">
                <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
                  <span className="text-xs text-amber-300 font-semibold">Nama Sekolah</span>
                  <span className="text-xs font-bold text-slate-100">{resetResult.schoolName}</span>
                </div>
                <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
                  <span className="text-xs text-amber-300 font-semibold">Username Admin</span>
                  <span className="font-mono text-xs font-bold text-purple-300">{resetResult.username}</span>
                </div>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-amber-300 font-semibold">
                    {resetResult.type === "create" ? "Kata Sandi Default" : "Kata Sandi Baru (Temporary)"}
                  </span>
                  <span className="font-mono text-sm font-black text-slate-100 bg-slate-900 px-3 py-1 rounded-lg border border-slate-700 select-all">
                    {resetResult.newPassword}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={isCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  onClick={handleCopyCredentials}
                >
                  {isCopied ? "Berhasil Disalin!" : "Salin Kredensial Admin"}
                </Button>
                <Button variant="outline" size="sm" onClick={() => setResetResult(null)}>
                  Tutup
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* Modal: Registrasi Sekolah Baru */}
        <Modal
          isOpen={isCreateModalOpen}
          onClose={() => {
            setIsCreateModalOpen(false);
            setFormError(null);
          }}
          title="Registrasi Sekolah Baru"
          subtitle="Masukkan data identitas sekolah resmi. Akun Admin Sekolah akan dibuat otomatis."
          maxWidth="lg"
        >
          <form onSubmit={handleCreateSchool} className="space-y-4">
            {formError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {formError}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Nama Resmi Sekolah"
                placeholder="SMA Negeri 1 Nusantara"
                value={name}
                onChange={(e) => setName(e.target.value)}
                leftIcon={<Building2 className="w-4 h-4" />}
                required
              />

              <Input
                label="NPSN (Nomor Pokok Sekolah Nasional)"
                placeholder="20101234"
                value={npsn}
                onChange={(e) => setNpsn(e.target.value)}
                leftIcon={<Lock className="w-4 h-4" />}
                required
              />

              <Input
                label="Kode Identifikasi Sekolah"
                placeholder="SCH_2026_01"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                leftIcon={<Lock className="w-4 h-4" />}
                required
              />

              <Select
                label="Jenjang Pendidikan"
                options={levelOptions}
                value={schoolLevelId}
                onChange={(e) => setSchoolLevelId(e.target.value)}
                required
              />

              <div className="md:col-span-2">
                <Input
                  label="Alamat Lengkap Sekolah"
                  placeholder="Jl. Pendidikan No. 123, Kel. Merdeka..."
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
                placeholder="info@sekolah.sch.id"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                leftIcon={<Mail className="w-4 h-4" />}
              />

              <Input
                label="Situs Web Sekolah"
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
                  onChange={(e) => setLogoUrl(e.target.value)}
                />
                {/* Always-visible logo preview */}
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-indigo-950 border border-indigo-500/40 flex items-center justify-center overflow-hidden shrink-0">
                    {logoUrl.trim() ? (
                      <img
                        src={logoUrl.trim()}
                        alt="Preview Logo"
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display='none'; (e.currentTarget.parentElement!.querySelector('.logo-fallback') as HTMLElement)!.style.display='flex'; }}
                      />
                    ) : null}
                    <Building2 className={`logo-fallback w-6 h-6 text-indigo-400/60 ${logoUrl.trim() ? 'hidden' : 'flex'}`} />
                  </div>
                  <span className="text-xs text-slate-500 font-medium">
                    {logoUrl.trim() ? 'Preview logo aktif — gambar ditampilkan langsung dari URL.' : 'Belum ada URL logo — masukkan URL untuk pratinjau langsung.'}
                  </span>
                </div>
              </div>

              <Input
                label="Domain Default Sekolah"
                placeholder="stpaulusMedan"
                value={domain}
                onChange={(e) => setDomain(e.target.value.replace(/[^a-zA-Z0-9.-]/g, ""))}
                helperText="Hanya huruf, angka, titik, dan strip. Digunakan untuk format username akun."
                required
              />

              <Select
                label="Durasi Subscription Awal"
                options={[
                  { value: "ONE_WEEK", label: "7 Hari (1 Minggu)" },
                  { value: "ONE_MONTH", label: "30 Hari (1 Bulan)" },
                  { value: "THREE_MONTHS", label: "90 Hari (3 Bulan)" },
                  { value: "SIX_MONTHS", label: "180 Hari (6 Bulan)" },
                  { value: "ONE_YEAR", label: "365 Hari (1 Tahun)" },
                  { value: "TWO_YEARS", label: "730 Hari (2 Tahun)" },
                  { value: "PERMANENT", label: "Lisensi Permanen ♾️" },
                ]}
                value={initialSubscriptionPreset}
                onChange={(e) => setInitialSubscriptionPreset(e.target.value)}
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsCreateModalOpen(false);
                  setFormError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>
                Registrasi Sekolah
              </Button>
            </div>
          </form>
        </Modal>

        {/* Modal: Edit Data Sekolah */}
        <Modal
          isOpen={isEditModalOpen}
          onClose={() => {
            setIsEditModalOpen(false);
            setFormError(null);
          }}
          title="Edit Data Profil Sekolah"
          subtitle={`Memperbarui informasi resmi untuk ${selectedSchool?.name || "Sekolah"}.`}
          maxWidth="lg"
        >
          <form onSubmit={handleUpdateSchool} className="space-y-4">
            {formError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {formError}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Nama Resmi Sekolah"
                value={name}
                onChange={(e) => setName(e.target.value)}
                leftIcon={<Building2 className="w-4 h-4" />}
                required
              />

              <Input
                label="NPSN (Nomor Pokok Sekolah Nasional)"
                value={npsn}
                onChange={(e) => setNpsn(e.target.value)}
                leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
                helperText="SuperAdmin berwenang mengedit NPSN jika terdapat perbaikan data."
                required
              />

              <Input
                label="Kode Identifikasi Sekolah"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                leftIcon={<Lock className="w-4 h-4 text-indigo-400" />}
                required
              />


              <Select
                label="Jenjang Pendidikan"
                options={levelOptions}
                value={schoolLevelId}
                onChange={(e) => setSchoolLevelId(e.target.value)}
                required
              />

              <div className="md:col-span-2">
                <Input
                  label="Alamat Lengkap Sekolah"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  leftIcon={<MapPin className="w-4 h-4" />}
                />
              </div>

              <Input
                label="Nomor Telepon Operasional"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                leftIcon={<Phone className="w-4 h-4" />}
              />

              <Input
                label="Email Resmi Sekolah"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                leftIcon={<Mail className="w-4 h-4" />}
              />

              <Input
                label="Situs Web Sekolah"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                leftIcon={<Globe className="w-4 h-4" />}
              />

              <div className="space-y-2">
                <Input
                  label="URL Logo Sekolah"
                  placeholder="https://cdn.sekolah.sch.id/logo.png"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                />
                {/* Always-visible logo preview */}
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-indigo-950 border border-indigo-500/40 flex items-center justify-center overflow-hidden shrink-0">
                    {logoUrl.trim() ? (
                      <img
                        src={logoUrl.trim()}
                        alt="Preview Logo"
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display='none'; (e.currentTarget.parentElement!.querySelector('.logo-fallback-edit') as HTMLElement)!.style.display='flex'; }}
                      />
                    ) : null}
                    <Building2 className={`logo-fallback-edit w-6 h-6 text-indigo-400/60 ${logoUrl.trim() ? 'hidden' : 'flex'}`} />
                  </div>
                  <span className="text-xs text-slate-500 font-medium">
                    {logoUrl.trim() ? 'Preview logo aktif — gambar ditampilkan langsung dari URL.' : 'Belum ada URL logo — masukkan URL untuk pratinjau langsung.'}
                  </span>
                </div>
              </div>

              <Input
                label="Domain Default Sekolah"
                value={domain}
                onChange={(e) => setDomain(e.target.value.replace(/[^a-zA-Z0-9.-]/g, ""))}
                helperText="Hanya huruf, angka, titik, dan strip. Digunakan untuk format username akun."
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsEditModalOpen(false);
                  setFormError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>
                Simpan Perubahan
              </Button>
            </div>
          </form>
        </Modal>
      </RoleGuard>
    </AppShell>
  );
};
