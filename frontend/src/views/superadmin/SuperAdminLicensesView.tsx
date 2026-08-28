import React, { useEffect, useState } from "react";
import {
  KeyRound,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  Sparkles,
  Calendar,
  Search,
  RefreshCw,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Select } from "../../components/ui/Select";
import type { SelectOption } from "../../components/ui/Select";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { Badge } from "../../components/ui/Badge";
import { Table } from "../../components/ui/Table";
import { UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { superadminApi } from "../../api/superadmin";
import { licenseApi } from "../../api/license";
import type {
  GenerateKeyPayload,
  GeneratedKeyResponse,
  SuperAdminRenewalItem,
  GeneratedKeyListItem,
} from "../../api/superadmin";
import type { SchoolProfile } from "../../api/school";
import type { LicenseTypeOption } from "../../api/license";
import type { AppApiError } from "../../api/client";
import { copyToClipboard } from "../../utils/clipboard";

export const SuperAdminLicensesView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {
  const toast = useToast();
  
  const isKeyExpiredForCancel = (createdAt: string) => {
    const createdTime = new Date(createdAt).getTime();
    const nowTime = new Date().getTime();
    const ageInMs = nowTime - createdTime;
    return ageInMs > 3 * 24 * 60 * 60 * 1000; // 3 days in ms
  };

  const [schools, setSchools] = useState<SchoolProfile[]>([]);
  const [plans, setPlans] = useState<LicenseTypeOption[]>([]);
  const [renewals, setRenewals] = useState<SuperAdminRenewalItem[]>([]);
  const [activationKeys, setActivationKeys] = useState<GeneratedKeyListItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Search states for each segment
  const [renewalSearchQuery, setRenewalSearchQuery] = useState("");
  const [keySearchQuery, setKeySearchQuery] = useState("");

  const filteredRenewals = renewals.filter((r) => {
    const school = schools.find((s) => s.id === r.school_id);
    const reqNum = r.request_number || r.id || r.public_id?.slice(0, 8);
    const q = renewalSearchQuery.toLowerCase();
    return (
      (school?.name || "").toLowerCase().includes(q) ||
      String(reqNum).toLowerCase().includes(q)
    );
  });

  const filteredKeys = activationKeys.filter((k) => {
    const school = schools.find((s) => s.id === k.school_id);
    const q = keySearchQuery.toLowerCase();
    return (
      (school?.name || "").toLowerCase().includes(q) ||
      k.key.toLowerCase().includes(q)
    );
  });

  // Generate Key Modal State
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState<boolean>(false);
  const [targetSchoolId, setTargetSchoolId] = useState<string>("");
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [selectedPresetDays, setSelectedPresetDays] = useState<number | "custom">(30);
  const [customDays, setCustomDays] = useState<string>("30");
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  // Result Modal State (Key Generated Success)
  const [generatedKey, setGeneratedKey] = useState<GeneratedKeyResponse | null>(null);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // Process Renewal Modal State
  const [selectedRenewal, setSelectedRenewal] = useState<SuperAdminRenewalItem | null>(null);
  const [processStatus, setProcessStatus] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [adminNotes, setAdminNotes] = useState<string>("");
  const [isProcessingRenewal, setIsProcessingRenewal] = useState<boolean>(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [schoolsData, plansData, renewalsData, keysData] = await Promise.all([
        superadminApi.getSchools(),
        licenseApi.getLicenseTypes(),
        superadminApi.getRenewalRequests(),
        superadminApi.getActivationKeys(),
      ]);
      setSchools(schoolsData);
      setPlans(plansData);
      setRenewals(renewalsData);
      setActivationKeys(keysData);

      if (schoolsData.length > 0) setTargetSchoolId(schoolsData[0].id.toString());
      
      // Default initial plan to ONE_MONTH (30 days)
      const defaultPlan = plansData.find((p) => p.code === "ONE_MONTH");
      if (defaultPlan) {
        setSelectedPlanId(defaultPlan.id.toString());
      } else if (plansData.length > 0) {
        setSelectedPlanId(plansData[0].id.toString());
      }
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memuat Data Lisensi", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handlePresetSelect = (days: number | "custom", code?: string) => {
    setSelectedPresetDays(days);
    if (days === "custom") {
      const defaultPlan = plans.find((p) => p.code === "ONE_MONTH");
      if (defaultPlan) {
        setSelectedPlanId(defaultPlan.id.toString());
      }
    } else {
      setCustomDays(days.toString());
      if (code) {
        const matchingPlan = plans.find((p) => p.code === code);
        if (matchingPlan) {
          setSelectedPlanId(matchingPlan.id.toString());
        }
      }
    }
  };

  const handleCancelKey = async (publicId: string) => {
    if (
      !window.confirm(
        "Apakah Anda yakin ingin membatalkan Activation Key ini? Setelah dibatalkan, key ini tidak dapat digunakan lagi."
      )
    ) {
      return;
    }

    try {
      await superadminApi.cancelActivationKey(publicId);
      toast.success("Key Dibatalkan", "Activation Key berhasil dinonaktifkan/dibatalkan.");
      fetchData();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Membatalkan Key", apiErr.message);
    }
  };

  const handleGenerateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerateError(null);

    const finalDays = parseInt(customDays, 10);

    if (!targetSchoolId || !selectedPlanId) {
      setGenerateError("Pilih sekolah dan jenis paket lisensi.");
      return;
    }

    if (isNaN(finalDays) || finalDays < 1) {
      setGenerateError("Masukkan durasi masa aktif custom minimal 1 hari.");
      return;
    }

    setIsGenerating(true);
    try {
      const payload: GenerateKeyPayload = {
        school_id: parseInt(targetSchoolId, 10),
        license_type_id: parseInt(selectedPlanId, 10),
        validity_days: finalDays,
      };

      const result = await superadminApi.generateActivationKey(payload);
      setGeneratedKey(result);
      setIsGenerateModalOpen(false);
      toast.success("Activation Key Diterbitkan", `Kode aktivasi (${finalDays} Hari) berhasil diterbitkan.`);
      fetchData();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setGenerateError(apiErr.message || "Gagal menerbitkan Activation Key.");
    } finally {
      setIsGenerating(false);
    }
  };


  const handleCopyKey = async () => {
    if (generatedKey?.key_plain) {
      const success = await copyToClipboard(generatedKey.key_plain);
      if (success) {
        setIsCopied(true);
        toast.success("Disalin!", "Activation Key telah disalin.");
        setTimeout(() => setIsCopied(false), 2000);
      } else {
        toast.error("Gagal Menyalin", "Gagal menyalin Activation Key secara otomatis.");
      }
    }
  };

  const handleProcessRenewal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRenewal) return;

    setIsProcessingRenewal(true);
    try {
      const response = await superadminApi.processRenewal(selectedRenewal.public_id, {
        status: processStatus,
        superadmin_notes: adminNotes.trim() || undefined,
      });

      toast.success(
        processStatus === "APPROVED" ? "Pengajuan Disetujui" : "Pengajuan Ditolak",
        `Permintaan perpanjangan lisensi #${selectedRenewal.request_number || selectedRenewal.id || selectedRenewal.public_id?.slice(0, 8)} telah diproses.`
      );


      if (response.key_plain) {
        setGeneratedKey({
          public_id: selectedRenewal.public_id,
          key_plain: response.key_plain,
          valid_until: new Date().toISOString(),
          status: "ACTIVE",
        });
      }

      setSelectedRenewal(null);
      setAdminNotes("");
      fetchData();
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memproses Perpanjangan", apiErr.message);
    } finally {
      setIsProcessingRenewal(false);
    }
  };

  const schoolOptions: SelectOption[] = schools.map((s) => ({
    value: s.id,
    label: `${s.name} (NPSN: ${s.npsn})`,
  }));



  const quickPresets = [
    { label: "7 Hari (1 Minggu)", days: 7, code: "ONE_WEEK" },
    { label: "30 Hari (1 Bulan)", days: 30, code: "ONE_MONTH" },
    { label: "90 Hari (3 Bulan)", days: 90, code: "THREE_MONTHS" },
    { label: "180 Hari (6 Bulan)", days: 180, code: "SIX_MONTHS" },
    { label: "365 Hari (1 Tahun)", days: 365, code: "ONE_YEAR" },
    { label: "730 Hari (2 Tahun)", days: 730, code: "TWO_YEARS" },
    { label: "Lisensi Permanen ♾️", days: 36500, code: "PERMANENT" },
  ];

  return (
    <AppShell activeHref="/superadmin/licenses" onNavigate={onNavigate}>
      <RoleGuard allowedRoles={[UserRole.SUPER_ADMIN]}>
        <Breadcrumb
          items={[{ label: "SuperAdmin Workspace", href: "/superadmin/dashboard" }, { label: "Lisensi Key Generator" }]}
        />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat wewenang lisensi & perpanjangan..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">SUPERADMIN AUTHORITY</Badge>
                  <Badge variant="emerald">CUSTOM DURATION & PRESETS</Badge>
                </div>
                <h2 className="text-2xl font-black text-slate-100">Penerbitan Activation Key & Renewal</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Pilih opsi durasi cepat (preset template) atau tentukan durasi custom jumlah hari sesuai kebutuhan tenant.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="ghost"
                  size="md"
                  leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
                  onClick={fetchData}
                  isLoading={isLoading}
                  title="Muat Ulang"
                >
                  Refresh
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<KeyRound className="w-4 h-4" />}
                  onClick={() => setIsGenerateModalOpen(true)}
                >
                  Generate Activation Key
                </Button>
              </div>
            </div>

            {/* Renewal Requests Table */}
            <div className="glass-panel p-6 space-y-4 border-indigo-500/20">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                  <Clock className="w-4 h-4" />
                  <span>Pengajuan Perpanjangan Lisensi (Renewal Requests)</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  {renewals.filter((r) => r.status === "PENDING" || r.status === "REQUESTED").length} Menunggu Persetujuan
                </span>
              </div>

              {/* Search Box */}
              <div className="flex items-center gap-2 w-full md:w-80">
                <div className="flex-1">
                  <Input
                    placeholder="Cari sekolah atau ID pengajuan..."
                    value={renewalSearchQuery}
                    onChange={(e) => setRenewalSearchQuery(e.target.value)}
                    leftIcon={<Search className="w-4 h-4" />}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="md"
                  leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />}
                  onClick={fetchData}
                  isLoading={isLoading}
                  title="Muat Ulang"
                  className="shrink-0"
                >
                  Refresh
                </Button>
              </div>
              
              <div className="max-h-[350px] overflow-y-auto space-y-4 pr-1">
                {/* Desktop Table (Visible on medium screens and up) */}
                <div className="hidden md:block">
                <Table
                  columns={[
                    {
                      key: "id",
                      header: "ID Request",
                      width: "140px",
                      render: (item: SuperAdminRenewalItem) => (
                        <span className="font-mono text-xs text-slate-300">
                          #{item.request_number || item.id || item.public_id?.slice(0, 8)}
                        </span>
                      ),
                    },
                    {
                      key: "school_id",
                      header: "Sekolah Pemohon",
                      render: (item: SuperAdminRenewalItem) => {
                        const school = schools.find((s) => s.id === item.school_id);
                        return <span className="font-bold text-slate-100">{school?.name || `Sekolah #${item.school_id}`}</span>;
                      },
                    },
                    {
                      key: "license_type_id",
                      header: "Paket Template",
                      render: (item: SuperAdminRenewalItem) => {
                        const plan = plans.find((p) => p.id === item.license_type_id);
                        return <span className="text-xs text-indigo-300 font-semibold">{plan?.name || `-`}</span>;
                      },
                    },
                    {
                      key: "proof",
                      header: "Bukti Bayar",
                      width: "120px",
                      render: (item: SuperAdminRenewalItem) =>
                        item.payment_proof_url ? (
                          <a
                            href={item.payment_proof_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:underline font-medium"
                          >
                            <span>Lihat URL</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : (
                          <span className="text-xs text-slate-500">-</span>
                        ),
                    },
                    {
                      key: "status",
                      header: "Status",
                      width: "130px",
                      render: (item: SuperAdminRenewalItem) => (
                        <Badge
                          variant={
                            item.status === "APPROVED"
                              ? "emerald"
                              : item.status === "REJECTED"
                              ? "crimson"
                              : "amber"
                          }
                        >
                          {item.status}
                        </Badge>
                      ),
                    },
                    {
                      key: "actions",
                      header: "Aksi Verifikasi",
                      width: "180px",
                      render: (item: SuperAdminRenewalItem) =>
                        item.status === "PENDING" || item.status === "REQUESTED" ? (
                          <div className="flex items-center gap-2">
                            <Button
                              variant="primary"
                              size="sm"
                              leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                              onClick={() => {
                                setSelectedRenewal(item);
                                setProcessStatus("APPROVED");
                              }}
                            >
                              Setujui
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<XCircle className="w-3.5 h-3.5" />}
                              onClick={() => {
                                setSelectedRenewal(item);
                                setProcessStatus("REJECTED");
                              }}
                            />
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500 font-mono">Diproses</span>
                        ),
                    },
                  ]}
                  data={filteredRenewals}
                  keyExtractor={(item) =>
                    item.public_id || item.request_number || (item.id ? item.id.toString() : Math.random().toString())
                  }
                />
              </div>

              {/* Mobile Cards Grid (Visible on mobile/small screens) */}
              <div className="grid grid-cols-1 gap-4 md:hidden">
                {filteredRenewals.length === 0 ? (
                  <div className="text-center py-6 text-slate-500 text-xs">
                    Tidak ada pengajuan perpanjangan lisensi.
                  </div>
                ) : (
                  filteredRenewals.map((item) => {
                    const school = schools.find((s) => s.id === item.school_id);
                    const plan = plans.find((p) => p.id === item.license_type_id);
                    const reqNum = item.request_number || item.id || item.public_id?.slice(0, 8);
                    const isPending = item.status === "PENDING" || item.status === "REQUESTED";

                    return (
                      <div key={item.public_id || item.id} className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
                        {/* Header: Request ID & Status */}
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-xs text-slate-400 font-bold">#{reqNum}</span>
                          <Badge
                            variant={
                              item.status === "APPROVED"
                                ? "emerald"
                                : item.status === "REJECTED"
                                ? "crimson"
                                : "amber"
                            }
                          >
                            {item.status}
                          </Badge>
                        </div>

                        {/* Details */}
                        <div className="space-y-1.5 text-xs">
                          <div>
                            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Sekolah Pemohon</span>
                            <span className="font-bold text-slate-100">{school?.name || `Sekolah #${item.school_id}`}</span>
                          </div>
                          <div className="flex justify-between items-center pt-1 border-t border-slate-800/40">
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Paket Template</span>
                              <span className="text-indigo-300 font-semibold">{plan?.name || `-`}</span>
                            </div>
                            <div>
                              <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider text-right">Bukti Bayar</span>
                              {item.payment_proof_url ? (
                                <a
                                  href={item.payment_proof_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 text-indigo-400 hover:underline font-bold"
                                >
                                  <span>Lihat URL</span>
                                  <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                              ) : (
                                <span className="text-slate-500 font-mono">-</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        {isPending && (
                          <div className="flex gap-2 pt-2 border-t border-slate-800/50">
                            <Button
                              variant="primary"
                              size="sm"
                              leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                              onClick={() => {
                                setSelectedRenewal(item);
                                setProcessStatus("APPROVED");
                              }}
                              className="flex-1"
                            >
                              Setujui
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<XCircle className="w-3.5 h-3.5" />}
                              onClick={() => {
                                setSelectedRenewal(item);
                                setProcessStatus("REJECTED");
                              }}
                              className="px-4"
                            />
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* Unused Keys Table */}
            <div className="glass-panel p-6 space-y-4 border-indigo-500/20">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                  <KeyRound className="w-4 h-4" />
                  <span>Activation Key Aktif yang Belum Digunakan (Dapat Dibatalkan)</span>
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  {activationKeys.filter((k) => k.status === "GENERATED").length} Tersedia
                </span>
              </div>

              {/* Search Box */}
              <div className="w-full md:w-80">
                <Input
                  placeholder="Cari sekolah atau hash key..."
                  value={keySearchQuery}
                  onChange={(e) => setKeySearchQuery(e.target.value)}
                  leftIcon={<Search className="w-4 h-4" />}
                />
              </div>

              {/* Desktop Table (Visible on medium screens and up) */}
              <div className="hidden md:block">
                <Table
                  columns={[
                    {
                      key: "school",
                      header: "Sekolah Tujuan",
                      render: (item: GeneratedKeyListItem) => {
                        const school = schools.find((s) => s.id === item.school_id);
                        return <span className="font-bold text-slate-100">{school?.name || `Sekolah #${item.school_id}`}</span>;
                      },
                    },
                    {
                      key: "plan",
                      header: "Paket Lisensi",
                      render: (item: GeneratedKeyListItem) => {
                        const plan = plans.find((p) => p.id === item.license_type_id);
                        return <span className="text-xs text-indigo-300 font-semibold">{plan?.name || `-`}</span>;
                      },
                    },
                    {
                      key: "valid_until",
                      header: "Batas Aktivasi",
                      render: (item: GeneratedKeyListItem) => (
                        <span className="text-xs text-slate-400">
                          {new Date(item.valid_until).toLocaleDateString("id-ID", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      ),
                    },
                    {
                      key: "key_preview",
                      header: "Hashed Key (Reference)",
                      render: (item: GeneratedKeyListItem) => (
                        <span className="font-mono text-[10px] text-slate-500 block truncate max-w-[150px]" title={item.key}>
                          {item.key.slice(0, 15)}...
                        </span>
                      ),
                    },
                    {
                      key: "actions",
                      header: "Aksi",
                      width: "150px",
                      render: (item: GeneratedKeyListItem) => {
                        const cannotCancel = isKeyExpiredForCancel(item.created_at);
                        return (
                          <Button
                            variant="danger"
                            size="sm"
                            leftIcon={<XCircle className="w-3.5 h-3.5" />}
                            onClick={() => handleCancelKey(item.public_id)}
                            disabled={cannotCancel}
                            title={cannotCancel ? "Tidak dapat dibatalkan setelah 3 hari dibuat" : undefined}
                          >
                            {cannotCancel ? "Waktu Habis" : "Batalkan Key"}
                          </Button>
                        );
                      },
                    },
                  ]}
                  data={filteredKeys.filter((k) => k.status === "GENERATED")}
                  keyExtractor={(item) => item.public_id}
                />
              </div>

              {/* Mobile Cards Grid (Visible on mobile/small screens) */}
              <div className="grid grid-cols-1 gap-4 md:hidden">
                {filteredKeys.filter((k) => k.status === "GENERATED").length === 0 ? (
                  <div className="text-center py-6 text-slate-500 text-xs">
                    Tidak ada activation key yang belum digunakan.
                  </div>
                ) : (
                  filteredKeys
                    .filter((k) => k.status === "GENERATED")
                    .map((item) => {
                      const school = schools.find((s) => s.id === item.school_id);
                      const plan = plans.find((p) => p.id === item.license_type_id);
                      const cannotCancel = isKeyExpiredForCancel(item.created_at);

                      return (
                        <div key={item.public_id} className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
                          {/* Header: School Name & Package */}
                          <div className="space-y-0.5">
                            <h4 className="font-bold text-slate-100 text-sm leading-snug">{school?.name || `Sekolah #${item.school_id}`}</h4>
                            <span className="inline-block text-xs text-indigo-300 font-semibold">{plan?.name || `-`}</span>
                          </div>

                          {/* Details */}
                          <div className="p-3 bg-slate-950/40 rounded-xl space-y-2 text-xs border border-slate-800/40">
                            <div className="flex justify-between items-center">
                              <span className="text-slate-400 font-semibold">Batas Aktivasi:</span>
                              <span className="text-slate-300 font-medium font-mono">
                                {new Date(item.valid_until).toLocaleDateString("id-ID")}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-slate-400 font-semibold">Reference Key:</span>
                              <span className="font-mono text-[10px] text-slate-500 block truncate max-w-[150px]" title={item.key}>
                                {item.key.slice(0, 15)}...
                              </span>
                            </div>
                          </div>

                          {/* Action */}
                          <div className="pt-1">
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<XCircle className="w-3.5 h-3.5" />}
                              onClick={() => handleCancelKey(item.public_id)}
                              className="w-full"
                              disabled={cannotCancel}
                              title={cannotCancel ? "Tidak dapat dibatalkan setelah 3 hari dibuat" : undefined}
                            >
                              {cannotCancel ? "Waktu Habis (Terkunci)" : "Batalkan Key"}
                            </Button>
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          </div>
        )}

        {/* Modal: Generate Activation Key with Preset + Custom Duration */}
        <Modal
          isOpen={isGenerateModalOpen}
          onClose={() => {
            setIsGenerateModalOpen(false);
            setGenerateError(null);
          }}
          title="Generate Activation Key Lisensi"
          subtitle="Pilih sekolah, template lisensi, dan tentukan durasi (Opsi Cepat atau Custom Hari)."
          maxWidth="lg"
        >
          <form onSubmit={handleGenerateKey} className="space-y-5">
            {generateError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {generateError}
              </div>
            )}

            <Select
              label="Sekolah Tujuan (Tenant)"
              options={schoolOptions}
              value={targetSchoolId}
              onChange={(e) => setTargetSchoolId(e.target.value)}
              placeholder="-- Pilih Sekolah --"
              required
            />

            {/* Template select dropdown removed because plan is bound to preset/duration selection */}

            {/* Quick Preset Options (Opsi Cepat Wallet-Style) */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                <span>Pilih Durasi Masa Aktif (Opsi Cepat & Custom)</span>
              </label>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {quickPresets.map((preset) => {
                  const isSelected = selectedPresetDays === preset.days;
                  return (
                    <button
                      type="button"
                      key={preset.days}
                      onClick={() => handlePresetSelect(preset.days, preset.code)}
                      className={`p-3 rounded-xl border text-xs font-medium text-left transition-all duration-200 flex flex-col justify-between ${
                        isSelected
                          ? "bg-indigo-600/25 border-indigo-500 text-indigo-200 shadow-md shadow-indigo-600/20"
                          : "bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/60"
                      }`}
                    >
                      <span className="font-bold text-slate-100">{preset.label}</span>
                      <span className="text-[11px] text-slate-400 mt-1">{preset.days} Hari Kalender</span>
                    </button>
                  );
                })}

                <button
                  type="button"
                  onClick={() => handlePresetSelect("custom")}
                  className={`p-3 rounded-xl border text-xs font-medium text-left transition-all duration-200 flex flex-col justify-between ${
                    selectedPresetDays === "custom"
                      ? "bg-purple-600/25 border-purple-500 text-purple-200 shadow-md shadow-purple-600/20"
                      : "bg-slate-900/80 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-800/60"
                  }`}
                >
                  <span className="font-bold text-purple-300">⏱️ Custom Durasi Hari</span>
                  <span className="text-[11px] text-slate-400 mt-1">Input Bebas Jumlah Hari</span>
                </button>
              </div>
            </div>

            {/* Custom Days Input Field */}
            <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3">
              <Input
                label="Jumlah Hari Masa Aktif (Custom Days)"
                type="number"
                min="1"
                max="3650"
                placeholder="Contoh: 14, 45, 120, 500"
                value={customDays}
                onChange={(e) => {
                  setCustomDays(e.target.value);
                  setSelectedPresetDays("custom");
                }}
                disabled={selectedPresetDays !== "custom"}
                leftIcon={<Calendar className="w-4 h-4 text-indigo-400" />}
                helperText={
                  selectedPresetDays === 36500
                    ? "Lisensi permanen aktif selamanya (dihitung 100 tahun)."
                    : selectedPresetDays !== "custom"
                    ? "Opsi preset cepat aktif. Klik 'Custom Durasi Hari' di atas untuk mengubah nilai."
                    : "Masukkan jumlah hari kalender secara spesifik jika tidak menggunakan opsi cepat."
                }
                required
              />

              {parseInt(customDays, 10) > 0 && (
                <div className="flex items-center gap-2 pt-1 text-xs text-indigo-300 font-medium">
                  <Badge variant="indigo">
                    DURASI TERPILIH: {customDays === "36500" ? "Permanen (100 Tahun)" : `${customDays} Hari`}
                  </Badge>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsGenerateModalOpen(false);
                  setGenerateError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isGenerating}>
                Generate Activation Key
              </Button>
            </div>
          </form>
        </Modal>

        {/* Modal: Result Activation Key Display */}
        <Modal
          isOpen={!!generatedKey}
          onClose={() => setGeneratedKey(null)}
          title="Activation Key Berhasil Diterbitkan"
          subtitle="Berikan kode aktivasi di bawah ini kepada School Admin untuk diinputkan di halaman Subscription."
          maxWidth="md"
        >
          {generatedKey && (
            <div className="space-y-4 text-center">
              <div className="p-6 rounded-2xl bg-indigo-950/70 border border-indigo-500/50 space-y-2">
                <span className="text-xs text-indigo-300 font-semibold tracking-wider uppercase">
                  Kode Lisensi Aktivasi Resmi
                </span>
                <div className="font-mono text-base md:text-xl font-black text-slate-100 tracking-wide md:tracking-widest bg-slate-900/90 py-3 px-4 rounded-xl border border-slate-700 select-all break-all whitespace-pre-wrap">
                  {generatedKey.key_plain}
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={isCopied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  onClick={handleCopyKey}
                  className="w-full sm:w-auto justify-center"
                >
                  {isCopied ? "Berhasil Disalin!" : "Salin Kode Key"}
                </Button>
                <Button 
                  variant="outline" 
                  size="md" 
                  onClick={() => setGeneratedKey(null)}
                  className="w-full sm:w-auto justify-center"
                >
                  Tutup
                </Button>
              </div>
            </div>
          )}
        </Modal>

        {/* Modal: Process Renewal Approval/Rejection */}
        <Modal
          isOpen={!!selectedRenewal}
          onClose={() => setSelectedRenewal(null)}
          title={processStatus === "APPROVED" ? "Setujui Perpanjangan Lisensi" : "Tolak Perpanjangan Lisensi"}
          subtitle={`Permintaan perpanjangan #${selectedRenewal?.request_number || selectedRenewal?.id || selectedRenewal?.public_id?.slice(0, 8)}.`}

          maxWidth="md"
        >
          <form onSubmit={handleProcessRenewal} className="space-y-4">
            <p className="text-xs text-slate-300">
              {processStatus === "APPROVED"
                ? "Dengan menyetujui pengajuan ini, sistem akan secara otomatis menerbitkan Activation Key baru untuk sekolah pemohon."
                : "Tolak pengajuan perpanjangan lisensi ini."}
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">Catatan SuperAdmin (Opsional)</label>
              <textarea
                className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 min-h-[80px]"
                placeholder="Contoh: Bukti pembayaran valid / Terverifikasi lunas."
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedRenewal(null)}>
                Batal
              </Button>
              <Button
                type="submit"
                variant={processStatus === "APPROVED" ? "primary" : "danger"}
                size="sm"
                isLoading={isProcessingRenewal}
              >
                {processStatus === "APPROVED" ? "Setujui & Terbitkan Key" : "Konfirmasi Tolak"}
              </Button>
            </div>
          </form>
        </Modal>
      </RoleGuard>
    </AppShell>
  );
};
