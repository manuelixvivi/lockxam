import React, { useState, useEffect } from "react";
import { RefreshCw } from "lucide-react";

export const ServerHealthIndicator: React.FC = () => {
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");
  const [serverUrl, setServerUrl] = useState<string>("");
  const [pingMs, setPingMs] = useState<number | null>(null);

  const checkHealth = async () => {
    setStatus("checking");
    const startTime = performance.now();
    try {
      const baseUrl =
        localStorage.getItem("equigrade_server_url") ||
        ((import.meta.env?.VITE_API_BASE_URL as string) || window.location.origin);
      setServerUrl(baseUrl);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const res = await fetch(`${baseUrl}/api/v1/health/`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      clearTimeout(timeoutId);

      const endTime = performance.now();
      if (res.ok) {
        setStatus("online");
        setPingMs(Math.round(endTime - startTime));
      } else {
        setStatus("offline");
        setPingMs(null);
      }
    } catch {
      setStatus("offline");
      setPingMs(null);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-3 backdrop-blur-md flex items-center justify-between text-xs gap-3">
      <div className="flex items-center gap-2.5">
        {status === "checking" ? (
          <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
        ) : status === "online" ? (
          <div className="relative flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping absolute opacity-75" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 relative" />
          </div>
        ) : (
          <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
        )}

        <div>
          <div className="flex items-center gap-1.5 font-bold text-slate-200">
            <span>
              {status === "online"
                ? "Server Online"
                : status === "offline"
                ? "Server Terputus / Offline"
                : "Memeriksa Koneksi..."}
            </span>
            {pingMs !== null && status === "online" && (
              <span className="text-[10px] text-emerald-400 font-mono font-normal">
                ({pingMs}ms)
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 font-mono truncate max-w-[220px]">
            {serverUrl || window.location.origin}
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={checkHealth}
        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
        title="Refresh Status Server"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${status === "checking" ? "animate-spin text-indigo-400" : ""}`} />
      </button>
    </div>
  );
};
