import React, { useEffect } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Info,
  HelpCircle,
  X,
} from "lucide-react";
import { Button } from "./Button";
import type { ButtonVariant } from "./Button";

export type MessageBoxType = "error" | "warning" | "success" | "info" | "question";

export interface MessageBoxProps {
  isOpen: boolean;
  onClose: () => void;
  type?: MessageBoxType;
  title: string;
  message: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  onConfirm?: () => void | Promise<void>;
  isLoading?: boolean;
  confirmVariant?: ButtonVariant;
}

const typeStyles: Record<
  MessageBoxType,
  {
    iconBg: string;
    iconBorder: string;
    icon: React.ReactNode;
    badge: string;
    badgeStyle: string;
    glow: string;
  }
> = {
  error: {
    iconBg: "bg-rose-500/15",
    iconBorder: "border-rose-500/30",
    icon: <AlertOctagon className="w-8 h-8 text-rose-400" />,
    badge: "KESALAHAN SISTEM",
    badgeStyle: "bg-rose-500/20 text-rose-300 border-rose-500/30",
    glow: "shadow-[0_0_40px_rgba(244,63,94,0.25)]",
  },
  warning: {
    iconBg: "bg-amber-500/15",
    iconBorder: "border-amber-500/30",
    icon: <AlertTriangle className="w-8 h-8 text-amber-400" />,
    badge: "PERINGATAN",
    badgeStyle: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    glow: "shadow-[0_0_40px_rgba(245,158,11,0.25)]",
  },
  success: {
    iconBg: "bg-emerald-500/15",
    iconBorder: "border-emerald-500/30",
    icon: <CheckCircle2 className="w-8 h-8 text-emerald-400" />,
    badge: "BERHASIL",
    badgeStyle: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    glow: "shadow-[0_0_40px_rgba(16,185,129,0.25)]",
  },
  info: {
    iconBg: "bg-indigo-500/15",
    iconBorder: "border-indigo-500/30",
    icon: <Info className="w-8 h-8 text-indigo-400" />,
    badge: "PEMBERITAHUAN",
    badgeStyle: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    glow: "shadow-[0_0_40px_rgba(99,102,241,0.25)]",
  },
  question: {
    iconBg: "bg-cyan-500/15",
    iconBorder: "border-cyan-500/30",
    icon: <HelpCircle className="w-8 h-8 text-cyan-400" />,
    badge: "KONFIRMASI TINDAKAN",
    badgeStyle: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
    glow: "shadow-[0_0_40px_rgba(6,182,212,0.25)]",
  },
};

export const MessageBox: React.FC<MessageBoxProps> = ({
  isOpen,
  onClose,
  type = "info",
  title,
  message,
  confirmText = "Mengerti",
  cancelText,
  onConfirm,
  isLoading = false,
  confirmVariant,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isLoading) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  const style = typeStyles[type] || typeStyles.info;
  const defaultConfirmVariant: ButtonVariant =
    confirmVariant ||
    (type === "error" || type === "warning" ? "danger" : "primary");

  return (
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/80 backdrop-blur-md transition-opacity duration-300"
        onClick={() => {
          if (!isLoading) onClose();
        }}
      />

      {/* Message Box Dialog Card */}
      <div
        className={`relative w-full max-w-md bg-slate-900/95 border border-slate-700/70 rounded-2xl ${style.glow} p-6 shadow-2xl z-10 animate-msgbox-in overflow-hidden`}
        role="dialog"
        aria-modal="true"
      >
        {/* Top Close Button */}
        {!isLoading && (
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Header Ribbon Badge */}
        <div className="mb-4">
          <span
            className={`text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-full border inline-block ${style.badgeStyle}`}
          >
            {style.badge}
          </span>
        </div>

        {/* Content Layout */}
        <div className="flex items-start gap-4">
          {/* Animated Icon Emblem */}
          <div
            className={`w-14 h-14 rounded-2xl ${style.iconBg} border ${style.iconBorder} flex items-center justify-center shrink-0 shadow-inner`}
          >
            {style.icon}
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-base font-black text-slate-100 leading-snug">
              {title}
            </h3>
            <div className="mt-2 text-xs text-slate-300 leading-relaxed max-h-56 overflow-y-auto pr-1">
              {message}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-end gap-2.5">
          {cancelText && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={isLoading}
            >
              {cancelText}
            </Button>
          )}

          <Button
            variant={defaultConfirmVariant}
            size="sm"
            onClick={async () => {
              if (onConfirm) {
                await onConfirm();
              } else {
                onClose();
              }
            }}
            isLoading={isLoading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
};
