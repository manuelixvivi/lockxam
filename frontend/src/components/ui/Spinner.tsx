import React from "react";
import { Loader2 } from "lucide-react";

export const Spinner: React.FC<{ size?: "sm" | "md" | "lg"; label?: string }> = ({
  size = "md",
  label,
}) => {
  const sizeStyles = {
    sm: "w-4 h-4",
    md: "w-7 h-7",
    lg: "w-10 h-10",
  };

  return (
    <div className="flex flex-col items-center justify-center gap-2.5 p-6">
      <Loader2 className={`${sizeStyles[size]} text-indigo-500 animate-spin`} />
      {label && <p className="text-xs text-slate-400 font-medium">{label}</p>}
    </div>
  );
};
