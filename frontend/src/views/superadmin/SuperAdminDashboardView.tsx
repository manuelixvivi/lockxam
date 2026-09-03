import React, { useEffect, useState } from "react";
import {
  Building2,
  KeyRound,
  ShieldCheck,
  CreditCard,
  Plus,
  ArrowUpRight,
  School,
  CheckCircle2,
  Cpu,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Table } from "../../components/ui/Table";
import { Spinner } from "../../components/ui/Spinner";
import { UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { superadminApi } from "../../api/superadmin";
import type { SchoolProfile } from "../../api/school";
import type { SuperAdminRenewalItem } from "../../api/superadmin";
import type { AppApiError } from "../../api/client";

export const SuperAdminDashboardView: React.FC<{ onNavigate?: (href: string) => void }> = ({
  onNavigate,
}) => {
  const toast = useToast();

  const [schools, setSchools] = useState<SchoolProfile[]>([]);
  const [renewals, setRenewals] = useState<SuperAdminRenewalItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    try {
      const [schoolsData, renewalsData] = await Promise.all([
        superadminApi.getSchools(),
        superadminApi.getRenewalRequests(),
      ]);
      setSchools(schoolsData);
      setRenewals(renewalsData);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memuat Dashboard", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const pendingRenewalsCount = renewals.filter((r) => r.status === "PENDING").length;

  return (
    <AppShell activeHref="/superadmin/dashboard" onNavigate={onNavigate}>
      <RoleGuard allowedRoles={[UserRole.SUPER_ADMIN]}>
        <Breadcrumb items={[{ label: "SuperAdmin Workspace", href: "#" }, { label: "Global Dashboard" }]} />

        {isLoading ? (
          <div className="glass-panel p-12 flex justify-center items-center">
            <Spinner size="lg" label="Memuat metrik global SuperAdmin..." />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header Panel */}
            <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="indigo">SUPERADMIN CONTROL</Badge>
                  <Badge variant="emerald">GLOBAL SYSTEM ACTIVE</Badge>
                </div>
                <h2 className="text-2xl font-black text-slate-100">Equigrade Global Management</h2>
                <p className="text-xs text-slate-400 mt-1">
                  Pusat kendali registrasi sekolah, penerbitan activation key, dan perpanjangan lisensi.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<Plus className="w-4 h-4" />}
                  onClick={() => onNavigate && onNavigate("/superadmin/schools")}
                >
                  Kelola Sekolah
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  leftIcon={<KeyRound className="w-4 h-4 text-purple-400" />}
                  onClick={() => onNavigate && onNavigate("/superadmin/licenses")}
                >
                  Lisensi Key
                </Button>
                <Button
                  variant="outline"
                  size="md"
                  leftIcon={<Cpu className="w-4 h-4 text-indigo-400" />}
                  onClick={() => onNavigate && onNavigate("/superadmin/ai-system")}
                >
                  AI & Sistem
                </Button>
              </div>
            </div>

            {/* Metrics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              {/* Total Schools */}
              <div className="glass-panel p-5 space-y-2 border-indigo-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Sekolah Terdaftar</span>
                  <Building2 className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="text-3xl font-black text-slate-100">{schools.length}</div>
                <p className="text-[11px] text-slate-500 font-medium">Terverifikasi di database central</p>
              </div>

              {/* Active Schools */}
              <div className="glass-panel p-5 space-y-2 border-emerald-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Sekolah Status Aktif</span>
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                </div>
                <div className="text-3xl font-black text-emerald-400">
                  {schools.filter((s) => s.is_active).length}
                </div>
                <p className="text-[11px] text-slate-500 font-medium">Siap melaksanakan ujian Lockxam</p>
              </div>

              {/* Pending Renewals */}
              <div className="glass-panel p-5 space-y-2 border-amber-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Pengajuan Perpanjangan</span>
                  <CreditCard className="w-5 h-5 text-amber-400" />
                </div>
                <div className="text-3xl font-black text-amber-400">{pendingRenewalsCount}</div>
                <p className="text-[11px] text-slate-500 font-medium">Membutuhkan verifikasi SuperAdmin</p>
              </div>

              {/* Total Activation Keys */}
              <div className="glass-panel p-5 space-y-2 border-purple-500/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Wewenang Lisensi</span>
                  <ShieldCheck className="w-5 h-5 text-purple-400" />
                </div>
                <div className="text-xl font-bold text-slate-100">SuperAdmin</div>
                <p className="text-[11px] text-purple-300 font-medium">100% Khusus SuperAdmin</p>
              </div>
            </div>

            {/* Registered Schools Overview Table */}
            <div className="glass-panel p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2 text-slate-100 font-bold text-sm">
                  <School className="w-4 h-4 text-indigo-400" />
                  <span>Daftar Sekolah Terdaftar Baru</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  rightIcon={<ArrowUpRight className="w-4 h-4" />}
                  onClick={() => onNavigate && onNavigate("/superadmin/schools")}
                >
                  Lihat Semua Sekolah
                </Button>
              </div>

              {/* Desktop Table (Visible on medium screens and up) */}
              <div className="hidden md:block">
                <Table
                  columns={[
                    { key: "code", header: "Kode", width: "120px", render: (item: SchoolProfile) => <span className="font-mono text-xs font-semibold text-indigo-400">{item.code}</span> },
                    { key: "name", header: "Nama Sekolah", render: (item: SchoolProfile) => <span className="font-bold text-slate-100">{item.name}</span> },
                    { key: "npsn", header: "NPSN", width: "120px", render: (item: SchoolProfile) => <span className="font-mono text-xs text-slate-300">{item.npsn}</span> },
                    { key: "phone", header: "Kontak", render: (item: SchoolProfile) => item.phone || "-" },
                    { key: "status", header: "Status", width: "120px", render: (item: SchoolProfile) => <Badge variant={item.is_active ? "emerald" : "amber"}>{item.is_active ? "AKTIF" : "PENDING"}</Badge> },
                  ]}
                  data={schools.slice(0, 5)}
                  keyExtractor={(item) => item.id.toString()}
                />
              </div>

              {/* Mobile Cards Grid (Visible on mobile/small screens) */}
              <div className="grid grid-cols-1 gap-4 md:hidden">
                {schools.slice(0, 5).length === 0 ? (
                  <div className="text-center py-6 text-slate-500 text-xs">
                    Belum ada data sekolah terdaftar.
                  </div>
                ) : (
                  schools.slice(0, 5).map((item) => (
                    <div key={item.id} className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <h4 className="font-bold text-slate-100 text-sm leading-snug">{item.name}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="font-mono text-[10px] text-indigo-400 font-bold">{item.code}</span>
                            <span className="text-[10px] text-slate-500 font-mono">NPSN: {item.npsn}</span>
                          </div>
                        </div>
                        <Badge variant={item.is_active ? "emerald" : "amber"}>
                          {item.is_active ? "AKTIF" : "PENDING"}
                        </Badge>
                      </div>
                      <div className="text-xs text-slate-400 border-t border-slate-800/80 pt-2 flex justify-between">
                        <span>Kontak:</span>
                        <span className="font-medium text-slate-200">{item.phone || "-"}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </RoleGuard>
    </AppShell>
  );
};
