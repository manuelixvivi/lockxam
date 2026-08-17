import React from "react";
import { useAuth, UserRole } from "../../context/AuthContext";
import { ShieldAlert } from "lucide-react";
import { Button } from "../ui/Button";

export interface RoleGuardProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
  fallbackRoute?: string;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({
  allowedRoles,
  children,
  fallbackRoute,
}) => {
  const { role, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const isRoleAllowed =
    role &&
    allowedRoles.some((allowed) => {
      if (allowed === UserRole.SUPER_ADMIN) {
        return role === "SUPERADMIN" || role === "SUPER_ADMIN";
      }
      return role === allowed;
    });

  if (!isAuthenticated || !role || !isRoleAllowed) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950">
        <div className="max-w-md w-full p-8 rounded-2xl bg-slate-900 border border-amber-500/30 text-center shadow-2xl">
          <div className="w-14 h-14 bg-amber-500/10 border border-amber-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
            <ShieldAlert className="w-8 h-8 text-amber-400" />
          </div>
          <h2 className="text-xl font-bold text-slate-100">Akses Ditolak (403 Forbidden)</h2>
          <p className="text-xs text-slate-400 mt-2 mb-6">
            Peran Anda ({role || "GUEST"}) tidak memiliki otorisasi untuk mengakses halaman ini.
          </p>
          <Button
            variant="primary"
            onClick={() => (window.location.href = fallbackRoute || "/")}
            className="w-full"
          >
            Kembali ke Halaman Utama
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
