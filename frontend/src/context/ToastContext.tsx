import React, { createContext, useContext, useState } from "react";
import { ToastContainer } from "../components/ui/ToastContainer";

export type ToastType = "success" | "warning" | "error" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextType {
  toasts: ToastMessage[];
  showToast: (toast: Omit<ToastMessage, "id">) => void;
  removeToast: (id: string) => void;
  success: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const showToast = (toast: Omit<ToastMessage, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast: ToastMessage = { ...toast, id };

    setToasts((prev) => [...prev, newToast]);

    const defaultDuration = toast.type === "error" ? 6000 : 4500;
    const autoClose = toast.duration ?? defaultDuration;
    if (autoClose > 0) {
      setTimeout(() => {
        removeToast(id);
      }, autoClose);
    }
  };

  const success = (title: string, message?: string) => showToast({ type: "success", title, message });
  const warning = (title: string, message?: string) => showToast({ type: "warning", title, message });
  const error = (title: string, message?: string) => showToast({ type: "error", title, message });
  const info = (title: string, message?: string) => showToast({ type: "info", title, message });

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast, success, warning, error, info }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
};
