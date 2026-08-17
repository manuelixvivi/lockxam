import React from "react";

export type BadgeVariant = "indigo" | "emerald" | "amber" | "crimson" | "slate";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: "sm" | "md";
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = "indigo", size = "md" }) => {
  const variantStyles: Record<BadgeVariant, string> = {
    indigo: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
    emerald: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    crimson: "bg-red-500/15 text-red-300 border-red-500/30",
    slate: "bg-slate-700/30 text-slate-300 border-slate-600/30",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[10px] tracking-wider uppercase font-semibold",
    md: "px-2.5 py-1 text-xs font-semibold",
  };

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border backdrop-blur-sm ${variantStyles[variant]} ${sizeStyles[size]}`}
    >
      {children}
    </span>
  );
};
