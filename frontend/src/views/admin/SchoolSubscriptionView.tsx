import React, { useEffect, useState } from "react";
import {
  CreditCard,
  KeyRound,
  Calendar,
  Users,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Send,
  PlusCircle,
  FileCheck,
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
import { UserRole } from "../../context/AuthContext";

import { useToast } from "../../context/ToastContext";
import { licenseApi } from "../../api/license";
import type {
  ActiveLicenseResponse,
  LicenseTypeOption,
} from "../../api/license";
import type { AppApiError } from "../../api/client";

export const SchoolSubscriptionView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {

  const toast = useToast();


  const [license, setLicense] = useState<ActiveLicenseResponse | null>(null);
  const [plans, setPlans] = useState<LicenseTypeOption[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Activation Key Modal State
  const [isActivationModalOpen, setIsActivationModalOpen] = useState<boolean>(false);
  const [activationKey, setActivationKey] = useState<string>("");
  const [isActivating, setIsActivating] = useState<boolean>(false);
  const [activationError, setActivationError] = useState<string | null>(null);

  // Renewal / Order Form State
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [paymentProofUrl, setPaymentProofUrl] = useState<string>("");
  const [isSubmittingOrder, setIsSubmittingOrder] = useState<boolean>(false);

  const fetchSubscriptionData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [currentLicense, availablePlans] = await Promise.all([
        licenseApi.getMyLicense(),
        licenseApi.getLicenseTypes(),
      ]);

      setLicense(currentLicense);
      setPlans(availablePlans);
      if (availablePlans.length > 0) {
        setSelectedPlanId(availablePlans[0].id.toString());
      }
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setError(apiErr.message || "Gagal memuat data subscription dari server.");
      toast.error("Gagal Memuat Subscription", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSubscriptionData();
  }, []);

  const handleActivateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setActivationError(null);

    if (!activationKey.trim()) {
      setActivationError("Masukkan Kode Aktivasi (Activation Key).");
      return;
    }

    setIsActivating(true);
    try {
      const activeLicense = await licenseApi.activateLicenseKey(activationKey);
      setLicense(activeLicense);
      toast.success("Lisensi Berhasil Diaktifkan", "Subscription sekolah Anda telah diperbarui.");
      setIsActivationModalOpen(false);
      setActivationKey("");
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setActivationError(apiErr.message || "Gagal mengaktifkan kode lisensi. Periksa kembali kode Anda.");
    } finally {
      setIsActivating(false);
    }
  };

  const handleOrderSubscription = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlanId) {
      toast.warning("Pilih Durasi", "Silakan pilih durasi paket subscription terlebih dahulu.");
      return;
    }

    setIsSubmittingOrder(true);
    try {
      await licenseApi.requestRenewal({
        license_type_id: parseInt(selectedPlanId, 10),
        payment_proof_url: paymentProofUrl.trim() || undefined,
      });

      toast.success(
        "Pemesanan Terkirim",
        "Pengajuan perpanjangan lisensi telah dikirim ke Tim SuperAdmin untuk verifikasi."
      );
      setPaymentProofUrl("");
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Mengajukan Pemesanan", apiErr.message);
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  const getRemainingDays = (validUntilStr: string): number => {
    const until = new Date(validUntilStr).getTime();
    const now = new Date().getTime();
    const diff = Math.ceil((until - now) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
  };

  const planOptions: SelectOption[] = plans.map((p) => ({
    value: p.id,
    label: `${p.name} — ${p.duration_days >= 9999 ? "Permanen" : `${p.duration_days} Hari`}`,
  }));



  const isPermanent = !!(
    license &&
    (license.license_type_id === 7 ||
      (license.end_date && new Date(license.end_date).getFullYear() > 2070) ||
      (license.valid_until && new Date(license.valid_until).getFullYear() > 2070))
  );

  return (
    <AppShell activeHref="/admin/subscription" onNavigate={onNavigate}>

      <RoleGuard allowedRoles={[UserRole.SCHOOL_ADMIN]}>
        <Breadcrumb items={[{ label: "School Admin", href: "/admin/dashboard" }, { label: "Subscription & Lisensi" }]} />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat status subscription sekolah..." />
          </div>
        ) : error ? (
          <div className="glass-panel p-8 text-center space-y-4 border-red-500/30">
            <p className="text-sm text-red-400 font-medium">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchSubscriptionData}>
              Coba Lagi
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">MANAGEMENT SUBSCRIPTION</Badge>
                  {license ? (
                    <Badge variant={license.status === "ACTIVE" ? "emerald" : "crimson"}>
                      {license.status}
                    </Badge>
                  ) : (
                    <Badge variant="amber">BELUM ADA LISENSI</Badge>
                  )}
                </div>
                <h2 className="text-2xl font-black text-slate-100">Status Subscription Sekolah</h2>
                <p className="text-xs text-slate-400 mt-1">
                  {isPermanent
                    ? "Informasi paket subscription aktif permanen Anda."
                    : "Kelola paket subscription aktif dan masukkan Activation Key dari SuperAdmin."}
                </p>
              </div>

              <div className="flex items-center gap-3">
                {!isPermanent && (
                  <Button
                    variant="primary"
                    size="md"
                    leftIcon={<KeyRound className="w-4 h-4" />}
                    onClick={() => setIsActivationModalOpen(true)}
                  >
                    Insert Activation Key
                  </Button>
                )}
              </div>
            </div>

            {/* Active License Details Card */}
            <div className="glass-panel p-6 space-y-6 border-indigo-500/20">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                  <CreditCard className="w-4 h-4" />
                  <span>Informasi Lisensi Aktif</span>
                </div>
                {license && (
                  <span className="text-xs text-slate-400 font-mono">
                    ID Lisensi: #{license.public_id.toString().slice(0, 8).toUpperCase()}
                  </span>
                )}
              </div>

              {license ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 md:gap-6">
                  {/* Status Indicator */}
                  <div className="p-3.5 sm:p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[11px] sm:text-xs text-slate-400 font-medium">Status Berlangganan</span>
                    <div className="flex items-center gap-2 pt-1">
                      {license.status === "ACTIVE" ? (
                        <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-400 shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-red-400 shrink-0" />
                      )}
                      <span className="text-sm sm:text-base font-bold text-slate-100">{license.status}</span>
                    </div>
                  </div>

                  {/* Registered Students Count */}
                  <div className="p-3.5 sm:p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[11px] sm:text-xs text-slate-400 font-medium">Siswa Terdaftar</span>
                    <div className="flex items-center gap-2 pt-1">
                      <Users className="w-4 h-4 sm:w-5 sm:h-5 text-indigo-400 shrink-0" />
                      <span className="text-sm sm:text-base font-bold text-slate-100">
                        {(license as any).registered_students_count ?? 0} Siswa
                      </span>
                    </div>
                  </div>

                  {/* Validity Period */}
                  <div className="p-3.5 sm:p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[11px] sm:text-xs text-slate-400 font-medium">Masa Berlaku s/d</span>
                    <div className="flex items-center gap-2 pt-1">
                      <Calendar className="w-4 h-4 sm:w-5 sm:h-5 text-indigo-400 shrink-0" />
                      <span className="text-xs sm:text-sm font-semibold text-slate-200 truncate">
                        {license.valid_until || license.end_date
                          ? new Date(license.valid_until || license.end_date!).getFullYear() > 2070
                            ? "Permanen ♾️"
                            : new Date(license.valid_until || license.end_date!).toLocaleDateString("id-ID", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })
                          : "-"}
                      </span>
                    </div>
                  </div>

                  {/* Countdown Days */}
                  <div className="p-3.5 sm:p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                    <span className="text-[11px] sm:text-xs text-slate-400 font-medium">Sisa Masa Aktif</span>
                    <div className="flex items-center gap-2 pt-1">
                      <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400 shrink-0" />
                      <span className="text-sm sm:text-base font-bold text-slate-100">
                        {license.valid_until || license.end_date
                          ? new Date(license.valid_until || license.end_date!).getFullYear() > 2070
                            ? "Permanen ♾️"
                            : `${getRemainingDays(license.valid_until || license.end_date!)} Hari`
                          : "0 Hari"}
                      </span>
                    </div>
                  </div>

                </div>

              ) : (
                <div className="p-8 text-center border border-dashed border-amber-500/30 rounded-xl bg-amber-950/10 space-y-3">
                  <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
                  <h4 className="text-sm font-bold text-slate-200">Sekolah Belum Memiliki Lisensi Aktif</h4>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    Silakan masukkan Activation Key dari SuperAdmin atau ajukan pemesanan paket subscription di bawah ini.
                  </p>
                </div>
              )}
            </div>

            {/* Request Renewal / Subscription Order Panel (Disabled if Permanent) */}
            {license &&
            (license.license_type_id === 7 ||
              (license.end_date && new Date(license.end_date).getFullYear() > 2070) ||
              (license.valid_until && new Date(license.valid_until).getFullYear() > 2070)) ? (
              <div className="glass-panel p-6 border-emerald-500/30 bg-emerald-950/20 space-y-2">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span>Lisensi Sekolah Anda Bersifat Permanen ♾️</span>
                </div>
                <p className="text-xs text-slate-300">
                  Sekolah Anda memiliki akses lisensi permanen tanpa batas waktu. Fitur pengajuan perpanjangan dan pemesanan subscription dinonaktifkan karena tidak diperlukan.
                </p>
              </div>
            ) : (
              <div className="glass-panel p-6 space-y-6">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm border-b border-slate-800 pb-3">
                  <PlusCircle className="w-4 h-4" />
                  <span>Pemesanan / Perpanjangan Subscription</span>
                </div>

                <form onSubmit={handleOrderSubscription} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Select
                      label="Pilih Paket Subscription & Durasi"
                      options={planOptions}
                      value={selectedPlanId}
                      onChange={(e) => setSelectedPlanId(e.target.value)}
                      placeholder="-- Pilih Durasi Paket --"
                      required
                    />

                    <Input
                      label="URL Bukti Pembayaran (Opsional)"
                      placeholder="https://cdn.sekolah.sch.id/bukti-bayar.pdf"
                      value={paymentProofUrl}
                      onChange={(e) => setPaymentProofUrl(e.target.value)}
                      leftIcon={<FileCheck className="w-4 h-4" />}
                      helperText="Lampirkan URL bukti pembayaran untuk mempercepat verifikasi SuperAdmin."
                    />
                  </div>

                  <div className="flex items-center justify-end pt-4 border-t border-slate-800">
                    <Button
                      type="submit"
                      variant="primary"
                      size="md"
                      isLoading={isSubmittingOrder}
                      leftIcon={<Send className="w-4 h-4" />}
                    >
                      Ajukan Pemesanan Subscription
                    </Button>
                  </div>
                </form>
              </div>
            )}

          </div>
        )}

        {/* Insert Activation Key Modal (🔑 School Admin Activation) */}
        <Modal
          isOpen={isActivationModalOpen}
          onClose={() => {
            setIsActivationModalOpen(false);
            setActivationError(null);
          }}
          title="Insert Activation Key"
          subtitle="Masukkan kode lisensi aktivasi resmi dari SuperAdmin."
          maxWidth="md"
        >
          <form onSubmit={handleActivateKey} className="space-y-4">
            {activationError && (
              <div className="p-3.5 rounded-xl bg-red-950/60 border border-red-500/40 text-red-300 text-xs font-medium">
                {activationError}
              </div>
            )}

            <Input
              label="Activation Key"
              placeholder="EQG-PRO-2026-XXXX-XXXX"
              value={activationKey}
              onChange={(e) => setActivationKey(e.target.value)}
              leftIcon={<KeyRound className="w-4 h-4" />}
              className="font-mono uppercase tracking-wider text-base"
              helperText="Kode aktivasi tervalidasi langsung ke server backend Equigrade."
              required
            />

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsActivationModalOpen(false);
                  setActivationError(null);
                }}
              >
                Batal
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={isActivating}>
                Aktivasi Lisensi
              </Button>
            </div>
          </form>
        </Modal>
      </RoleGuard>
    </AppShell>
  );
};
