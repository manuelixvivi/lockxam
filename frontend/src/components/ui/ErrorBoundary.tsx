import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";
import { Button } from "./Button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-slate-100">
          <div className="max-w-md w-full p-8 rounded-2xl bg-slate-900 border border-red-500/30 shadow-2xl text-center">
            <div className="w-14 h-14 bg-red-500/10 border border-red-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertOctagon className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-bold text-slate-100">Terjadi Kesalahan Aplikasi</h2>
            <p className="text-xs text-slate-400 mt-2 mb-6">
              {this.state.error?.message || "Terdapat masalah yang tidak terduga pada antarmuka."}
            </p>
            <Button
              variant="primary"
              leftIcon={<RotateCcw className="w-4 h-4" />}
              onClick={() => window.location.reload()}
              className="w-full"
            >
              Muat Ulang Halaman
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
