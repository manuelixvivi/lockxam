import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Info,
  X,
  Copy,
  Check,
} from "lucide-react";
import { useToast } from "../../context/ToastContext";
import type { ToastType, ToastMessage } from "../../context/ToastContext";
import { copyToClipboard } from "../../utils/clipboard";

interface ToastItemProps {
  toast: ToastMessage;
  onRemove: (id: string) => void;
}

const typeConfig: Record<
  ToastType,
  {
    badgeText: string;
    badgeStyle: string;
    cardStyle: string;
    progressStyle: string;
    icon: React.ReactNode;
    beaconColor: string;
  }
> = {
  error: {
    badgeText: "KESALAHAN SISTEM / GAGAL",
    badgeStyle: "bg-rose-500/20 text-rose-300 border-rose-500/30",
    cardStyle:
      "border-rose-500/40 bg-slate-900/95 shadow-[0_12px_36px_-6px_rgba(244,63,94,0.25)]",
    progressStyle: "bg-gradient-to-r from-rose-500 to-red-400",
    icon: <AlertOctagon className="w-5 h-5 text-rose-400 shrink-0" />,
    beaconColor: "bg-rose-500",
  },
  warning: {
    badgeText: "PERINGATAN / PERHATIAN",
    badgeStyle: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    cardStyle:
      "border-amber-500/40 bg-slate-900/95 shadow-[0_12px_36px_-6px_rgba(245,158,11,0.25)]",
    progressStyle: "bg-gradient-to-r from-amber-500 to-yellow-400",
    icon: <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />,
    beaconColor: "bg-amber-500",
  },
  success: {
    badgeText: "BERHASIL DILAKUKAN",
    badgeStyle: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
    cardStyle:
      "border-emerald-500/40 bg-slate-900/95 shadow-[0_12px_36px_-6px_rgba(16,185,129,0.25)]",
    progressStyle: "bg-gradient-to-r from-emerald-500 to-teal-400",
    icon: <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />,
    beaconColor: "bg-emerald-500",
  },
  info: {
    badgeText: "PEMBERITAHUAN",
    badgeStyle: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    cardStyle:
      "border-indigo-500/40 bg-slate-900/95 shadow-[0_12px_36px_-6px_rgba(99,102,241,0.25)]",
    progressStyle: "bg-gradient-to-r from-indigo-500 to-cyan-400",
    icon: <Info className="w-5 h-5 text-indigo-400 shrink-0" />,
    beaconColor: "bg-indigo-500",
  },
};

const ToastItem: React.FC<ToastItemProps> = ({ toast, onRemove }) => {
  const [copied, setCopied] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const duration = toast.duration ?? (toast.type === "error" ? 6000 : 4500);
  const [timeLeft, setTimeLeft] = useState(duration);

  const config = typeConfig[toast.type] || typeConfig.info;

  // Auto dismiss countdown with hover-pause
  useEffect(() => {
    if (duration <= 0) return;

    const interval = 50;
    const timer = setInterval(() => {
      if (!isHovered) {
        setTimeLeft((prev) => {
          if (prev <= interval) {
            clearInterval(timer);
            onRemove(toast.id);
            return 0;
          }
          return prev - interval;
        });
      }
    }, interval);

    return () => clearInterval(timer);
  }, [duration, isHovered, onRemove, toast.id]);

  const handleCopy = async () => {
    const textToCopy = toast.message
      ? `${toast.title}\n${toast.message}`
      : toast.title;
    const success = await copyToClipboard(textToCopy);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const progressPercent = Math.max(0, Math.min(100, (timeLeft / duration) * 100));

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={`pointer-events-auto relative overflow-hidden rounded-2xl border backdrop-blur-xl transition-all duration-300 animate-msgbox-in ${config.cardStyle}`}
      role="alert"
    >
      {/* Top Header Ribbon */}
      <div className="flex items-center justify-between px-4 pt-3.5 pb-2 border-b border-slate-800/80 bg-slate-950/40">
        <div className="flex items-center gap-2">
          {/* Pulsing Beacon Dot */}
          <div className="relative flex items-center justify-center w-2.5 h-2.5">
            <span
              className={`absolute w-full h-full rounded-full animate-beacon-pulse opacity-75 ${config.beaconColor}`}
            />
            <span className={`relative w-2 h-2 rounded-full ${config.beaconColor}`} />
          </div>

          <span
            className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border ${config.badgeStyle}`}
          >
            {config.badgeText}
          </span>
        </div>

        <div className="flex items-center gap-1">
          {toast.message && (
            <button
              type="button"
              onClick={handleCopy}
              className="p-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
              title="Salin isi pesan"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          )}
          <button
            type="button"
            onClick={() => onRemove(toast.id)}
            className="p-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            title="Tutup pemberitahuan"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div className="p-4 flex items-start gap-3.5">
        <div className="w-10 h-10 rounded-xl bg-slate-800/80 border border-slate-700/60 flex items-center justify-center shrink-0 shadow-inner mt-0.5">
          {config.icon}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-black text-slate-100 leading-snug">
            {toast.title}
          </h4>
          {toast.message && (
            <div className="mt-1.5 text-xs text-slate-300 leading-relaxed max-h-48 overflow-y-auto pr-1">
              {String(toast.message)}
            </div>
          )}
        </div>
      </div>

      {/* Animated Countdown Progress Bar */}
      {duration > 0 && (
        <div className="w-full h-1 bg-slate-800/80 overflow-hidden">
          <div
            className={`h-full transition-all duration-75 ease-linear ${config.progressStyle}`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      )}
    </div>
  );
};

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-5 right-5 z-[99999] flex flex-col gap-3 max-w-md w-full sm:w-[420px] pointer-events-none px-4 sm:px-0"
      aria-live="polite"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
      ))}
    </div>
  );
};
