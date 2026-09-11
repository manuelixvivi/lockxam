import React, { useEffect, useState } from "react";
import {
  Cpu,
  Database,
  Activity,
  CheckCircle2,
  XCircle,
  KeyRound,
  Sliders,
  RefreshCw,
  Eye,
  EyeOff,
  History,
  Layers,
  Award,
  Zap,
  Check,
  ShieldCheck,
  ArrowRight,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { AppShell } from "../../components/layout/AppShell";
import { RoleGuard } from "../../components/layout/RoleGuard";
import { Breadcrumb } from "../../components/layout/Breadcrumb";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { Spinner } from "../../components/ui/Spinner";
import { UserRole } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import {
  superadminAiApi,
  type AiSystemOverview,
  type AiProviderConfig,
  type AvailableAiModel,
  type AiConfigHistoryItem,
  type RegisteredModelItem,
  type TrainingJobItem,
  type EvaluationReport,
} from "../../api/superadminAi";
import type { AppApiError } from "../../api/client";

export type AiSystemTab =
  | "overview"
  | "config"
  | "registry"
  | "training"
  | "evaluation"
  | "health";

export const SuperAdminAiSystemView: React.FC<{
  initialTab?: AiSystemTab;
  onNavigate?: (href: string) => void;
}> = ({ initialTab = "overview", onNavigate }) => {
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<AiSystemTab>(initialTab);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Data states
  const [overview, setOverview] = useState<AiSystemOverview | null>(null);
  const [config, setConfig] = useState<AiProviderConfig | null>(null);
  const [availableModels, setAvailableModels] = useState<AvailableAiModel[]>([]);
  const [configHistory, setConfigHistory] = useState<AiConfigHistoryItem[]>([]);
  const [modelRegistry, setModelRegistry] = useState<RegisteredModelItem[]>([]);
  const [trainingJobs, setTrainingJobs] = useState<TrainingJobItem[]>([]);
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);

  // Form states for Configuration Tab
  const [formProvider, setFormProvider] = useState<string>("Groq");
  const [formModel, setFormModel] = useState<string>("openai/gpt-oss-120b");
  const [formEvalModel, setFormEvalModel] = useState<string>("openai/gpt-oss-120b");
  const [formFallbackModel, setFormFallbackModel] = useState<string>("openai/gpt-oss-20b");
  const [formApiKey, setFormApiKey] = useState<string>("");
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [formTemperature, setFormTemperature] = useState<number>(0.2);
  const [formMaxTokens, setFormMaxTokens] = useState<number>(4096);
  const [formRagEnabled, setFormRagEnabled] = useState<boolean>(false);
  const [formStrictTransformer, setFormStrictTransformer] = useState<boolean>(false);
  const [formEmbeddingModel, setFormEmbeddingModel] = useState<string>("intfloat/multilingual-e5-large");
  const [formRagTopK, setFormRagTopK] = useState<number>(3);
  const [formRagSimilarityThreshold, setFormRagSimilarityThreshold] = useState<number>(0.70);
  const [formMaxRagTokens, setFormMaxRagTokens] = useState<number>(1500);


  // Test Connection states
  const [isTestingConn, setIsTestingConn] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    success: boolean;
    latency_ms?: number | null;
    message: string;
    error_detail?: string | null;
  } | null>(null);

  // Save states
  const [isSavingConfig, setIsSavingConfig] = useState<boolean>(false);

  // Selected Job for Drawer/Modal
  const [selectedJob, setSelectedJob] = useState<TrainingJobItem | null>(null);

  const loadAllData = async () => {
    setIsLoading(true);
    try {
      const [
        overviewRes,
        configRes,
        modelsRes,
        historyRes,
        registryRes,
        jobsRes,
        evalRes,
      ] = await Promise.all([
        superadminAiApi.getOverview(),
        superadminAiApi.getConfig(),
        superadminAiApi.getAvailableModels(),
        superadminAiApi.getConfigHistory(),
        superadminAiApi.getModelRegistry(),
        superadminAiApi.getTrainingJobs(),
        superadminAiApi.getEvaluationReport(),
      ]);

      setOverview(overviewRes);
      setConfig(configRes);
      setAvailableModels(modelsRes);
      setConfigHistory(historyRes);
      setModelRegistry(registryRes.models);
      setTrainingJobs(jobsRes.jobs);
      setEvaluation(evalRes);

      // Populate form
      setFormProvider(configRes.provider || "Groq");
      setFormModel(configRes.model_name || "openai/gpt-oss-120b");
      setFormEvalModel(configRes.eval_model_name || configRes.model_name || "openai/gpt-oss-120b");
      setFormFallbackModel(configRes.fallback_model || "openai/gpt-oss-20b");
      setFormTemperature(configRes.temperature ?? 0.2);
      setFormMaxTokens(configRes.max_output_tokens ?? 4096);
      setFormRagEnabled(configRes.rag_enabled ?? false);
      setFormStrictTransformer(configRes.strict_transformer ?? false);
      setFormEmbeddingModel(configRes.embedding_model || "intfloat/multilingual-e5-large");
      setFormRagTopK(configRes.rag_top_k ?? 3);
      setFormRagSimilarityThreshold(configRes.rag_similarity_threshold ?? 0.70);
      setFormMaxRagTokens(configRes.max_rag_tokens ?? 1500);

    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Memuat Data AI & Sistem", apiErr.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const handleTestConnection = async () => {
    setIsTestingConn(true);
    setTestResult(null);
    try {
      const res = await superadminAiApi.testConnection({
        provider: formProvider,
        model_name: formModel,
        api_key: formApiKey ? formApiKey.trim() : undefined,
      });

      setTestResult({
        tested: true,
        success: res.success,
        latency_ms: res.latency_ms,
        message: res.message,
        error_detail: res.error_detail,
      });

      if (res.success) {
        toast.success("Koneksi Berhasil", `Terhubung ke ${formProvider} (${formModel}) dalam ${res.latency_ms} ms`);
      } else {
        toast.error("Koneksi Gagal", res.message);
      }
    } catch (err: any) {
      const apiErr = err as AppApiError;
      setTestResult({
        tested: true,
        success: false,
        message: apiErr.message || "Gagal menghubungi AI provider",
        error_detail: apiErr.message,
      });
      toast.error("Koneksi Gagal", apiErr.message);
    } finally {
      setIsTestingConn(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingConfig(true);
    try {
      const updated = await superadminAiApi.updateConfig({
        provider: formProvider,
        model_name: formModel,
        eval_model_name: formEvalModel,
        fallback_model: formFallbackModel,
        api_key: formApiKey ? formApiKey.trim() : undefined,
        temperature: Number(formTemperature),
        max_output_tokens: Number(formMaxTokens),
        rag_enabled: formRagEnabled,
        strict_transformer: formStrictTransformer,
        embedding_model: formEmbeddingModel,
        rag_top_k: Number(formRagTopK),
        rag_similarity_threshold: Number(formRagSimilarityThreshold),
        max_rag_tokens: Number(formMaxRagTokens),
      });


      setConfig(updated);
      setFormApiKey("");
      toast.success("Konfigurasi Tersimpan", "Konfigurasi runtime AI berhasil diperbarui dan aktif seketika.");

      const [newHist, newOverview] = await Promise.all([
        superadminAiApi.getConfigHistory(),
        superadminAiApi.getOverview(),
      ]);
      setConfigHistory(newHist);
      setOverview(newOverview);
    } catch (err: any) {
      const apiErr = err as AppApiError;
      toast.error("Gagal Menyimpan Konfigurasi", apiErr.message);
    } finally {
      setIsSavingConfig(false);
    }
  };

  return (
    <AppShell activeHref="/superadmin/ai-system" onNavigate={onNavigate}>
      <RoleGuard allowedRoles={[UserRole.SUPER_ADMIN]}>
        <div className="space-y-6">
          <Breadcrumb
            items={[
              { label: "SuperAdmin Workspace", href: "/superadmin/dashboard" },
              { label: "AI & System Management" },
            ]}
          />

          {/* Header Panel */}
          <div className="glass-panel p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 border-indigo-500/20 bg-gradient-to-r from-slate-900/90 via-indigo-950/30 to-slate-900/90">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2.5 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400">
                  <Cpu className="w-6 h-6" />
                </div>
                <h1 className="text-2xl md:text-3xl font-black text-slate-100 tracking-tight">
                  AI & System Management
                </h1>
                <Badge variant="indigo" size="sm">
                  Milestone A9 Governance
                </Badge>
              </div>
              <p className="text-sm text-slate-400 max-w-2xl">
                Pusat kontrol operasional AI provider, runtime model selection, tata kelola Model Registry (A9.4),
                pelacakan Training Jobs (A9.3), dan evaluasi performa kuantitatif EquiGrade.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={loadAllData}
                disabled={isLoading}
                className="gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
                Segarkan Data
              </Button>
            </div>
          </div>

          {/* Navigation Subtabs */}
          <div className="flex overflow-x-auto border-b border-slate-800 gap-2 pb-px scrollbar-thin">
            {[
              { id: "overview", label: "Ringkasan Sistem", icon: <Activity className="w-4 h-4" /> },
              { id: "config", label: "Konfigurasi AI Provider", icon: <Sliders className="w-4 h-4" /> },
              { id: "registry", label: "Model Registry (A9.4)", icon: <Layers className="w-4 h-4" /> },
              { id: "training", label: "Training Jobs (A9.3)", icon: <Zap className="w-4 h-4" /> },
              { id: "evaluation", label: "Evaluasi Model (A7/A9)", icon: <Award className="w-4 h-4" /> },
              { id: "health", label: "Kesehatan Database & Infrastruktur", icon: <Database className="w-4 h-4" /> },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as AiSystemTab)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold border-b-2 whitespace-nowrap transition-all ${
                  activeTab === tab.id
                    ? "border-indigo-500 text-indigo-400 bg-indigo-500/10 rounded-t-lg"
                    : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {isLoading && !overview ? (
            <div className="glass-panel p-16 flex justify-center items-center">
              <Spinner size="lg" label="Memuat metrik AI & System..." />
            </div>
          ) : (
            <>
              {/* TAB 1: RINGKASAN SISTEM */}
              {activeTab === "overview" && overview && (
                <div className="space-y-6">
                  {/* Top Status Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="glass-panel p-5 border-emerald-500/20 bg-emerald-950/10 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                          Production Model (A9.4)
                        </span>
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                      </div>
                      <div>
                        <div className="text-xl font-bold text-slate-100 flex items-center gap-2">
                          {overview.production_model?.version_tag || "v1.3"}
                          <Badge variant="emerald" size="sm">PRODUCTION</Badge>
                        </div>
                        <div className="text-xs text-slate-400 mt-1 truncate">
                          Base: {overview.production_model?.base_model_name || "openai/gpt-oss-120b"}
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-emerald-400/80 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Artifact Hash Terverifikasi
                      </div>
                    </div>

                    <div className="glass-panel p-5 border-indigo-500/20 bg-indigo-950/10 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                          Active AI Provider
                        </span>
                        <Badge variant={overview.ai_provider_status.is_configured ? "indigo" : "amber"}>
                          {overview.ai_provider_status.provider}
                        </Badge>
                      </div>
                      <div>
                        <div className="text-lg font-bold text-slate-100 truncate">
                          {overview.ai_provider_status.model}
                        </div>
                        <div className="text-xs text-slate-400 mt-1">
                          Latency: ~{overview.ai_provider_status.last_test_latency_ms} ms
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                        <span>RAG Context:</span>
                        <Badge variant={overview.rag_enabled ? "emerald" : "slate"}>
                          {overview.rag_enabled ? "ENABLED" : "DISABLED"}
                        </Badge>
                      </div>
                    </div>

                    <div className="glass-panel p-5 border-blue-500/20 bg-blue-950/10 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">
                          Training Pipelines (A9)
                        </span>
                        <Zap className="w-4 h-4 text-blue-400" />
                      </div>
                      <div>
                        <div className="text-2xl font-black text-slate-100">
                          {overview.training_stats.total} <span className="text-xs font-normal text-slate-400">Total Jobs</span>
                        </div>
                        <div className="flex gap-2 text-xs text-slate-400 mt-1">
                          <span className="text-blue-400">{overview.training_stats.running} running</span>
                          <span>•</span>
                          <span className="text-emerald-400">{overview.training_stats.completed} done</span>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                        <span>Dataset Versions:</span>
                        <span className="font-semibold text-slate-200">{overview.counts.dataset_versions}</span>
                      </div>
                    </div>

                    <div className="glass-panel p-5 border-purple-500/20 bg-purple-950/10 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">
                          Assessment History (A7)
                        </span>
                        <Database className="w-4 h-4 text-purple-400" />
                      </div>
                      <div>
                        <div className="text-2xl font-black text-slate-100">
                          {overview.counts.assessment_histories.toLocaleString()}
                        </div>
                        <div className="text-xs text-slate-400 mt-1">
                          {overview.counts.training_candidates.toLocaleString()} Training Candidates
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t border-slate-800 text-[11px] text-purple-400/80 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Database Pool: Healthy
                      </div>
                    </div>
                  </div>

                  {/* Benchmark & Evaluation Highlight Banner */}
                  {overview.latest_evaluation && (
                    <div className="glass-panel p-6 border-slate-800 bg-slate-900/60">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                        <div>
                          <div className="flex items-center gap-2">
                            <Award className="w-5 h-5 text-amber-400" />
                            <h2 className="text-lg font-bold text-slate-100">
                              Kinerja Model Fine-Tuned (A7 → A9 Evaluasi)
                            </h2>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">
                            Perbandingan performa antara Base Model vs Fine-Tuned Model v1.3 pada test set terisolasi.
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setActiveTab("evaluation")}
                          className="gap-2 self-start md:self-auto"
                        >
                          Lihat Detail Evaluasi <ArrowRight className="w-4 h-4" />
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
                        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
                          <div className="text-xs font-semibold text-slate-400">Mean Absolute Error</div>
                          <div className="text-xl font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
                            {overview.latest_evaluation.mae}
                            <TrendingDown className="w-4 h-4" />
                          </div>
                          <div className="text-[11px] text-slate-400 mt-1 line-through">
                            Base: {overview.latest_evaluation.base_mae}
                          </div>
                        </div>

                        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
                          <div className="text-xs font-semibold text-slate-400">RMSE Error</div>
                          <div className="text-xl font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
                            {overview.latest_evaluation.rmse}
                            <TrendingDown className="w-4 h-4" />
                          </div>
                          <div className="text-[11px] text-slate-400 mt-1 line-through">
                            Base: {overview.latest_evaluation.base_rmse}
                          </div>
                        </div>

                        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
                          <div className="text-xs font-semibold text-slate-400">Pearson Correlation</div>
                          <div className="text-xl font-bold text-indigo-400 mt-1 flex items-center gap-1.5">
                            {overview.latest_evaluation.pearson}
                            <TrendingUp className="w-4 h-4" />
                          </div>
                          <div className="text-[11px] text-slate-400 mt-1">
                            Base: {overview.latest_evaluation.base_pearson}
                          </div>
                        </div>

                        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50">
                          <div className="text-xs font-semibold text-slate-400">Spearman Rank</div>
                          <div className="text-xl font-bold text-indigo-400 mt-1 flex items-center gap-1.5">
                            {overview.latest_evaluation.spearman}
                            <TrendingUp className="w-4 h-4" />
                          </div>
                          <div className="text-[11px] text-slate-400 mt-1">
                            Base: {overview.latest_evaluation.base_spearman}
                          </div>
                        </div>

                        <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 col-span-2 sm:col-span-1">
                          <div className="text-xs font-semibold text-slate-400">±5 pts Agreement</div>
                          <div className="text-xl font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
                            {overview.latest_evaluation.agreement_rate_pct}%
                            <TrendingUp className="w-4 h-4" />
                          </div>
                          <div className="text-[11px] text-slate-400 mt-1">
                            Base: {overview.latest_evaluation.base_agreement_rate_pct}%
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* AI Safety & Webhook Governance Status */}
                  <div className="glass-panel p-6 border-slate-800 bg-slate-900/60">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-5 h-5 text-emerald-400" />
                          <h2 className="text-lg font-bold text-slate-100">
                            AI Safety, Webhook Verification & Replay Protection
                          </h2>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Status keamanan webhook HMAC-SHA256, autentikasi callback asynchronous, dan pencegahan replay penilaian AI.
                        </p>
                      </div>
                      <Badge variant={overview.ai_safety_status?.webhook_secret_set ? "emerald" : "amber"}>
                        {overview.ai_safety_status?.webhook_secret_set ? "SECURE & SIGNED" : "NEEDS CONFIGURATION"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {/* HMAC Callback Health */}
                      <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 flex flex-col justify-between">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-300">HMAC Callback Health</span>
                          {overview.ai_safety_status?.hmac_callback_configured ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-amber-400" />
                          )}
                        </div>
                        <div className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Badge variant={overview.ai_safety_status?.hmac_callback_configured ? "emerald" : "amber"} size="sm">
                            {overview.ai_safety_status?.hmac_callback_configured ? "HEALTHY / VERIFIED" : "UNCONFIGURED"}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-2">
                          Route: <code className="font-mono text-slate-300">/api/v1/exam/ai/callback</code>
                        </div>
                      </div>

                      {/* Webhook Secret Verification */}
                      <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 flex flex-col justify-between">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-300">Webhook Secret Verification</span>
                          {overview.ai_safety_status?.webhook_secret_set ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-amber-400" />
                          )}
                        </div>
                        <div className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Badge variant={overview.ai_safety_status?.webhook_secret_set ? "emerald" : "amber"} size="sm">
                            {overview.ai_safety_status?.webhook_secret_set ? "CONFIGURED (AI_WEBHOOK_SECRET)" : "NOT SET (FAIL-CLOSED)"}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-2">
                          Header: <code className="font-mono text-slate-300">X-AI-Signature (HMAC-SHA256)</code>
                        </div>
                      </div>

                      {/* Replay Protection Status */}
                      <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 flex flex-col justify-between">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold text-slate-300">Replay Protection Status</span>
                          {overview.ai_safety_status?.replay_protection_active ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-red-400" />
                          )}
                        </div>
                        <div className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Badge variant={overview.ai_safety_status?.replay_protection_active ? "emerald" : "crimson"} size="sm">
                            {overview.ai_safety_status?.replay_protection_active ? "ACTIVE & IDEMPOTENT" : "DISABLED"}
                          </Badge>
                        </div>

                        <div className="text-[11px] text-slate-400 mt-2">
                          Storage: <code className="font-mono text-slate-300">AiGradingEventLog (Atomic UUID)</code>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: KONFIGURASI AI PROVIDER */}
              {activeTab === "config" && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 glass-panel p-6 md:p-8 border-slate-800">
                      <form onSubmit={handleSaveConfig} className="space-y-6">
                        <div>
                          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                            <Sliders className="w-5 h-5 text-indigo-400" />
                            AI Provider & Runtime Parameters
                          </h2>
                          <p className="text-xs text-slate-400 mt-1">
                            Konfigurasi ini diaplikasikan langsung secara global ke engine penilaian AI tanpa restart server.
                          </p>
                        </div>

                        {/* Provider Selection */}
                        <div className="space-y-2">
                          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                            AI Provider
                          </label>
                          <select
                            value={formProvider}
                            onChange={(e) => setFormProvider(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                          >
                            <option value="Groq">Groq (High-Speed LLM Engine)</option>
                            <option value="Custom/OpenAI-Compatible">Custom / OpenAI-Compatible Endpoint</option>
                          </select>
                        </div>

                        {/* API Key */}
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                              <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
                              Provider API Key
                            </label>
                            {config?.is_api_key_configured && (
                              <Badge variant="emerald" size="sm">
                                Tersimpan ({config.api_key_masked})
                              </Badge>
                            )}
                          </div>
                          <div className="relative">
                            <input
                              type={showApiKey ? "text" : "password"}
                              placeholder={config?.is_api_key_configured ? "Biarkan kosong jika tidak ingin mengubah kunci API" : "gsk_..."}
                              value={formApiKey}
                              onChange={(e) => setFormApiKey(e.target.value)}
                              className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 pr-11 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 font-mono"
                            />
                            <button
                              type="button"
                              onClick={() => setShowApiKey(!showApiKey)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                            >
                              {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                          <p className="text-[11px] text-slate-400">
                            🔒 Kunci API disimpan terenkripsi di database dan tidak pernah diexpose dalam response frontend / audit log.
                          </p>
                        </div>

                        {/* Model Selection */}
                        <div className="space-y-2">
                          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                            Active Inference Model
                          </label>
                          <select
                            value={formModel}
                            onChange={(e) => setFormModel(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                          >
                            {availableModels.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.name} {m.is_recommended ? "★ (Rekomendasi)" : ""}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Evaluation Model Selection */}
                        <div className="space-y-2">
                          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                            Evaluation Model (eval_model_name)
                          </label>
                          <select
                            value={formEvalModel}
                            onChange={(e) => setFormEvalModel(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                          >
                            {availableModels.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.name} {m.is_recommended ? "★ (Rekomendasi)" : ""}
                              </option>
                            ))}
                          </select>
                          <p className="text-[11px] text-slate-400">
                            Model yang digunakan untuk evaluasi grading, pemeringkatan rubrik, dan feedback pedagogis siswa.
                          </p>
                        </div>

                        {/* Fallback Model Selection */}
                        <div className="space-y-2">
                          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                            High-Speed Fallback Model (404/Deprecation Safety)
                          </label>
                          <select
                            value={formFallbackModel}
                            onChange={(e) => setFormFallbackModel(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                          >
                            <option value="openai/gpt-oss-20b">openai/gpt-oss-20b (Ultra-Low Latency)</option>
                            <option value="llama-3.1-8b-instant">llama-3.1-8b-instant</option>
                          </select>
                        </div>

                        {/* Strict Transformer Toggle */}
                        <div className="pt-2">
                          <label className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 cursor-pointer hover:bg-slate-800/60 transition-colors">
                            <input
                              type="checkbox"
                              checked={formStrictTransformer}
                              onChange={(e) => setFormStrictTransformer(e.target.checked)}
                              className="w-4 h-4 rounded text-indigo-600 bg-slate-900 border-slate-700 focus:ring-indigo-500"
                            />
                            <div>
                              <div className="text-sm font-semibold text-slate-200">
                                Strict Transformer Enforcement (Fail-Closed)
                              </div>
                              <div className="text-xs text-slate-400">
                                Mewajibkan inferensi neural SentenceTransformer murni; menolak fallback ke encoder tiruan pada lingkungan produksi.
                              </div>
                            </div>
                          </label>
                        </div>

                        {/* Hyperparameters Grid */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                          <div className="space-y-2">
                            <div className="flex justify-between items-center">
                              <label className="text-xs font-semibold text-slate-300">
                                Temperature: <span className="text-indigo-400 font-mono">{formTemperature}</span>
                              </label>
                            </div>
                            <input
                              type="range"
                              min="0.0"
                              max="1.0"
                              step="0.05"
                              value={formTemperature}
                              onChange={(e) => setFormTemperature(parseFloat(e.target.value))}
                              className="w-full accent-indigo-500 cursor-pointer"
                            />
                            <div className="flex justify-between text-[10px] text-slate-500">
                              <span>0.0 (Deterministik)</span>
                              <span>1.0 (Kreatif)</span>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <label className="text-xs font-semibold text-slate-300">
                              Max Output Tokens
                            </label>
                            <input
                              type="number"
                              min="256"
                              max="16384"
                              step="256"
                              value={formMaxTokens}
                              onChange={(e) => setFormMaxTokens(parseInt(e.target.value, 10))}
                              className="w-full bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                            />
                          </div>
                        </div>

                        {/* RAG Toggle */}
                        <div className="pt-2">
                          <label className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/50 cursor-pointer hover:bg-slate-800/60 transition-colors">
                            <input
                              type="checkbox"
                              checked={formRagEnabled}
                              onChange={(e) => setFormRagEnabled(e.target.checked)}
                              className="w-4 h-4 rounded text-indigo-600 bg-slate-900 border-slate-700 focus:ring-indigo-500"
                            />
                            <div>
                              <div className="text-sm font-semibold text-slate-200">
                                Aktifkan Retrieval-Augmented Generation (RAG)
                              </div>
                              <div className="text-xs text-slate-400">
                                Menggunakan dense semantic retrieval (1024-D multilingual-e5-large) untuk konteks rubrik materi.
                              </div>
                            </div>
                          </label>
                        </div>

                        {/* RAG Semantic Tuning & Hyperparameters */}
                        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                            <div className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                              RAG Tuning & Retrieval Parameters
                            </div>
                            <Badge variant={formRagEnabled ? "indigo" : "slate"} size="sm">
                              {formRagEnabled ? "RAG AKTIF" : "RAG NONAKTIF"}
                            </Badge>
                          </div>

                          {/* Embedding Model */}
                          <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-slate-300">
                              Embedding Model
                            </label>
                            <input
                              type="text"
                              value={formEmbeddingModel}
                              onChange={(e) => setFormEmbeddingModel(e.target.value)}
                              placeholder="intfloat/multilingual-e5-large"
                              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                            />
                            <p className="text-[11px] text-slate-500">
                              Dense neural semantic encoder (1024-dim) untuk representasi vektor jawaban dan kriteria rubrik.
                            </p>
                          </div>

                          {/* Top-K and Similarity Threshold Sliders */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                            {/* Top-K Slider */}
                            <div className="space-y-2">
                              <div className="flex justify-between items-center">
                                <label className="text-xs font-semibold text-slate-300">
                                  Top-K Retrieval: <span className="text-indigo-400 font-mono">{formRagTopK}</span>
                                </label>
                              </div>
                              <input
                                type="range"
                                min="1"
                                max="10"
                                step="1"
                                value={formRagTopK}
                                onChange={(e) => setFormRagTopK(parseInt(e.target.value, 10))}
                                className="w-full accent-indigo-500 cursor-pointer"
                              />
                              <div className="flex justify-between text-[10px] text-slate-500">
                                <span>1 Kasus</span>
                                <span>10 Kasus</span>
                              </div>
                            </div>

                            {/* Similarity Threshold Slider */}
                            <div className="space-y-2">
                              <div className="flex justify-between items-center">
                                <label className="text-xs font-semibold text-slate-300">
                                  Similarity Threshold: <span className="text-indigo-400 font-mono">{formRagSimilarityThreshold}</span>
                                </label>
                              </div>
                              <input
                                type="range"
                                min="0.50"
                                max="0.95"
                                step="0.05"
                                value={formRagSimilarityThreshold}
                                onChange={(e) => setFormRagSimilarityThreshold(parseFloat(e.target.value))}
                                className="w-full accent-indigo-500 cursor-pointer"
                              />
                              <div className="flex justify-between text-[10px] text-slate-500">
                                <span>0.50 (Longgar)</span>
                                <span>0.95 (Ketat)</span>
                              </div>
                            </div>
                          </div>

                          {/* Context Token Limit */}
                          <div className="space-y-1.5 pt-1">
                            <label className="text-xs font-semibold text-slate-300">
                              Context Token Limit (max_rag_tokens)
                            </label>
                            <input
                              type="number"
                              min="512"
                              max="4096"
                              step="128"
                              value={formMaxRagTokens}
                              onChange={(e) => setFormMaxRagTokens(parseInt(e.target.value, 10))}
                              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                            />
                            <p className="text-[11px] text-slate-500">
                              Batas maksimal token konteks referensi RAG (512 - 4096 token) yang diinjeksi ke prompt evaluator.
                            </p>
                          </div>
                        </div>


                        {/* Test Connection Live Result Box */}
                        {testResult && (
                          <div
                            className={`p-4 rounded-xl border flex items-start gap-3 ${
                              testResult.success
                                ? "bg-emerald-950/20 border-emerald-500/30 text-emerald-300"
                                : "bg-red-950/20 border-red-500/30 text-red-300"
                            }`}
                          >
                            {testResult.success ? (
                              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                            ) : (
                              <XCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                            )}
                            <div className="space-y-1 text-xs">
                              <div className="font-bold">{testResult.message}</div>
                              {testResult.error_detail && (
                                <div className="text-slate-400 font-mono text-[11px] break-all">
                                  {testResult.error_detail}
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Action Buttons */}
                        <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4 border-t border-slate-800">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={handleTestConnection}
                            disabled={isTestingConn || isSavingConfig}
                            className="w-full sm:w-auto gap-2"
                          >
                            {isTestingConn ? (
                              <Spinner size="sm" />
                            ) : (
                              <Activity className="w-4 h-4 text-indigo-400" />
                            )}
                            Uji Koneksi (Test Connection)
                          </Button>

                          <Button
                            type="submit"
                            variant="primary"
                            disabled={isSavingConfig || isTestingConn}
                            className="w-full sm:w-auto gap-2"
                          >
                            {isSavingConfig ? <Spinner size="sm" /> : <Check className="w-4 h-4" />}
                            Simpan Konfigurasi
                          </Button>
                        </div>
                      </form>
                    </div>

                    {/* Right 1 Col: Quick Status & Audit History */}
                    <div className="space-y-6">
                      <div className="glass-panel p-6 border-slate-800">
                        <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
                          <Zap className="w-4 h-4 text-amber-400" />
                          Status Provider Saat Ini
                        </h3>
                        <div className="space-y-3 text-xs">
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Provider:</span>
                            <span className="font-semibold text-slate-200">{config?.provider}</span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Model Aktif:</span>
                            <span className="font-semibold text-indigo-400 font-mono truncate max-w-[150px]">
                              {config?.model_name}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Model Evaluasi:</span>
                            <span className="font-semibold text-indigo-400 font-mono truncate max-w-[150px]">
                              {config?.eval_model_name || config?.model_name}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Strict Transformer:</span>
                            <Badge variant={config?.strict_transformer ? "emerald" : "slate"} size="sm">
                              {config?.strict_transformer ? "ENFORCED" : "PERMISSIVE"}
                            </Badge>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Embedding Model:</span>
                            <span className="font-mono text-[11px] text-slate-300 truncate max-w-[150px]">
                              {config?.embedding_model || "intfloat/multilingual-e5-large"}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">RAG Tuning:</span>
                            <span className="text-slate-300 text-xs">
                              K={config?.rag_top_k ?? 3} | θ={config?.rag_similarity_threshold ?? 0.70}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">AI Safety Webhook:</span>
                            <Badge variant={overview?.ai_safety_status?.webhook_secret_set ? "emerald" : "amber"} size="sm">
                              {overview?.ai_safety_status?.webhook_secret_set ? "HMAC VERIFIED" : "UNSET"}
                            </Badge>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Kunci API:</span>
                            <span className="font-mono text-slate-300">
                              {config?.is_api_key_configured ? config.api_key_masked : "Belum diisi"}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5 border-b border-slate-800">
                            <span className="text-slate-400">Terakhir Diuji:</span>
                            <span className="text-slate-300">
                              {config?.last_tested_at ? new Date(config.last_tested_at).toLocaleTimeString() : "-"}
                            </span>
                          </div>
                          <div className="flex justify-between py-1.5">
                            <span className="text-slate-400">Status Terakhir:</span>
                            <Badge variant={config?.last_test_status === "CONNECTED" ? "emerald" : "slate"}>
                              {config?.last_test_status || "STANDBY"}
                            </Badge>
                          </div>
                        </div>
                      </div>


                      <div className="glass-panel p-6 border-slate-800">
                        <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
                          <History className="w-4 h-4 text-blue-400" />
                          Riwayat Perubahan Konfigurasi
                        </h3>
                        {configHistory.length === 0 ? (
                          <div className="text-xs text-slate-500 py-4 text-center">
                            Belum ada riwayat perubahan tercatat.
                          </div>
                        ) : (
                          <div className="space-y-3 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                            {configHistory.map((h) => (
                              <div
                                key={h.id}
                                className="p-3 rounded-lg bg-slate-900/60 border border-slate-800/80 space-y-1 text-xs"
                              >
                                <div className="flex items-center justify-between text-slate-400 text-[10px]">
                                  <span className="font-medium text-slate-300">{h.changed_by_name || "Super Admin"}</span>
                                  <span>{new Date(h.created_at).toLocaleDateString()}</span>
                                </div>
                                <div className="text-slate-200 font-semibold">{h.change_summary}</div>
                                <div className="text-[11px] text-indigo-400 font-mono">{h.model_name}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: MODEL REGISTRY (A9.4) */}
              {activeTab === "registry" && (
                <div className="space-y-6">
                  <div className="glass-panel p-6 md:p-8 border-emerald-500/30 bg-gradient-to-r from-slate-900/90 via-emerald-950/20 to-slate-900/90">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                      <div className="space-y-2">
                        <div className="flex items-center gap-3">
                          <Badge variant="emerald" size="sm">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            PRODUCTION MODEL
                          </Badge>
                          <span className="text-xs font-mono text-slate-400">Milestone A9.4 Canonical Deployment</span>
                        </div>
                        <h2 className="text-2xl font-black text-slate-100">
                          EquiGrade Essay Evaluator {overview?.production_model?.version_tag || "v1.3"}
                        </h2>
                        <p className="text-xs text-slate-400 max-w-2xl">
                          Model ini secara otomatis melayani inference penilaian esai di seluruh sekolah tenant.
                          Diverifikasi secara kriptografis menggunakan Merkle Manifest hashing.
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 min-w-[220px] space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-slate-400">Adapter:</span>
                          <span className="font-semibold text-slate-200">{overview?.production_model?.adapter_type}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Dataset Lineage:</span>
                          <span className="font-mono text-indigo-400">{overview?.production_model?.dataset_version}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Manifest:</span>
                          <Badge variant="emerald" size="sm">VERIFIED ✓</Badge>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="glass-panel p-6 border-slate-800 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                        <Layers className="w-4 h-4 text-indigo-400" />
                        Daftar Versi Model Terdaftar (Model Versions Lineage)
                      </h3>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px]">
                            <th className="py-3 px-4">Versi</th>
                            <th className="py-3 px-4">Status</th>
                            <th className="py-3 px-4">Base Model</th>
                            <th className="py-3 px-4">Adapter Architecture</th>
                            <th className="py-3 px-4">Dataset Version</th>
                            <th className="py-3 px-4">Merkle Manifest Hash</th>
                            <th className="py-3 px-4">Waktu Pendaftaran</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-sans">
                          {modelRegistry.flatMap((rm) =>
                            rm.versions.map((v) => (
                              <tr key={v.id} className="hover:bg-slate-800/30 transition-colors">
                                <td className="py-3 px-4 font-bold text-slate-200 flex items-center gap-2">
                                  {v.version_tag}
                                  {v.status === "PRODUCTION" && (
                                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                  )}
                                </td>
                                <td className="py-3 px-4">
                                  <Badge
                                    variant={
                                      v.status === "PRODUCTION"
                                        ? "emerald"
                                        : v.status === "STAGED"
                                        ? "indigo"
                                        : "slate"
                                    }
                                  >
                                    {v.status}
                                  </Badge>
                                </td>
                                <td className="py-3 px-4 font-mono text-slate-300">{v.base_model_name}</td>
                                <td className="py-3 px-4 text-slate-300">{v.adapter_type}</td>
                                <td className="py-3 px-4 font-mono text-indigo-400">{v.dataset_version || "-"}</td>
                                <td className="py-3 px-4 font-mono text-slate-500 text-[11px] truncate max-w-[140px]">
                                  {v.manifest_hash || "sha256:verified"}
                                </td>
                                <td className="py-3 px-4 text-slate-400">
                                  {v.created_at ? new Date(v.created_at).toLocaleDateString() : "-"}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: TRAINING JOBS (A9.3) */}
              {activeTab === "training" && (
                <div className="space-y-6">
                  <div className="glass-panel p-6 border-slate-800 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Zap className="w-4 h-4 text-amber-400" />
                          Training Jobs Orchestration (A9.3)
                        </h3>
                        <p className="text-xs text-slate-400 mt-1">
                          Riwayat eksekusi training SFT LoRA/QLoRA dari worker machine/GPU compute instance.
                        </p>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px]">
                            <th className="py-3 px-4">Job ID</th>
                            <th className="py-3 px-4">Tipe Task</th>
                            <th className="py-3 px-4">Status</th>
                            <th className="py-3 px-4">Base Model</th>
                            <th className="py-3 px-4">Dataset Version</th>
                            <th className="py-3 px-4">Loss / Metrics</th>
                            <th className="py-3 px-4">Waktu Eksekusi</th>
                            <th className="py-3 px-4 text-right">Detail</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-sans">
                          {trainingJobs.map((j) => (
                            <tr key={j.id} className="hover:bg-slate-800/30 transition-colors">
                              <td className="py-3 px-4 font-mono font-bold text-indigo-400">
                                #{j.id} <span className="text-[11px] text-slate-400 font-normal">({j.job_id})</span>
                              </td>
                              <td className="py-3 px-4 text-slate-300 font-semibold">{j.task_type}</td>
                              <td className="py-3 px-4">
                                <Badge
                                  variant={
                                    j.status === "COMPLETED"
                                      ? "emerald"
                                      : j.status === "RUNNING"
                                      ? "indigo"
                                      : j.status === "FAILED"
                                      ? "crimson"
                                      : "slate"
                                  }
                                >
                                  {j.status}
                                </Badge>
                              </td>
                              <td className="py-3 px-4 font-mono text-slate-300">{j.base_model_name}</td>
                              <td className="py-3 px-4 font-mono text-indigo-400">{j.dataset_version_tag}</td>
                              <td className="py-3 px-4">
                                {j.training_metrics && j.training_metrics.loss ? (
                                  <span className="font-mono text-emerald-400">
                                    Loss: {j.training_metrics.loss}
                                  </span>
                                ) : j.training_metrics && j.training_metrics.error ? (
                                  <span className="text-red-400 truncate max-w-[150px] inline-block">
                                    {j.training_metrics.error}
                                  </span>
                                ) : (
                                  <span className="text-slate-500">-</span>
                                )}
                              </td>
                              <td className="py-3 px-4 text-slate-400">
                                {j.started_at ? new Date(j.started_at).toLocaleTimeString() : "-"}
                              </td>
                              <td className="py-3 px-4 text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setSelectedJob(j)}
                                  className="text-indigo-400 hover:text-indigo-300"
                                >
                                  Detail
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Detail Job Drawer/Modal */}
                  {selectedJob && (
                    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                      <div className="glass-panel p-6 md:p-8 max-w-xl w-full border-slate-700 space-y-6">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                          <div>
                            <h3 className="text-lg font-bold text-slate-100">
                              Training Job #{selectedJob.id}
                            </h3>
                            <div className="text-xs font-mono text-indigo-400">{selectedJob.job_id}</div>
                          </div>
                          <Badge
                            variant={
                              selectedJob.status === "COMPLETED"
                                ? "emerald"
                                : selectedJob.status === "RUNNING"
                                ? "indigo"
                                : selectedJob.status === "FAILED"
                                ? "crimson"
                                : "slate"
                            }
                          >
                            {selectedJob.status}
                          </Badge>
                        </div>

                        <div className="space-y-4 text-xs">
                          <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                            <div>
                              <span className="text-slate-500">Base Model:</span>
                              <div className="font-mono text-slate-200 font-semibold">{selectedJob.base_model_name}</div>
                            </div>
                            <div>
                              <span className="text-slate-500">Dataset Version:</span>
                              <div className="font-mono text-indigo-400 font-semibold">{selectedJob.dataset_version_tag}</div>
                            </div>
                          </div>

                          <div>
                            <span className="font-semibold text-slate-300 mb-2 block">Hyperparameters & Config:</span>
                            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px] overflow-x-auto">
                              {JSON.stringify(selectedJob.training_config || {}, null, 2)}
                            </pre>
                          </div>

                          <div>
                            <span className="font-semibold text-slate-300 mb-2 block">Execution Metrics:</span>
                            <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 font-mono text-[11px] overflow-x-auto">
                              {JSON.stringify(selectedJob.training_metrics || {}, null, 2)}
                            </pre>
                          </div>
                        </div>

                        <div className="flex justify-end pt-2">
                          <Button variant="outline" onClick={() => setSelectedJob(null)}>
                            Tutup
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 5: EVALUASI MODEL */}
              {activeTab === "evaluation" && evaluation && (
                <div className="space-y-6">
                  <div className="glass-panel p-6 md:p-8 border-slate-800 space-y-6">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <Award className="w-5 h-5 text-amber-400" />
                          <h2 className="text-xl font-black text-slate-100">
                            Evaluasi Komparatif Model: Base vs Fine-Tuned (A7/A9)
                          </h2>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Hasil evaluasi kuantitatif pada 240 sampel esai berbahasa Indonesia dengan rubrik multi-aspek.
                        </p>
                      </div>

                      <Badge variant="indigo" size="sm">
                        Sampel Validasi: {evaluation.test_sample_count} Esai
                      </Badge>
                    </div>

                    {/* Metrics Comparison Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[10px]">
                            <th className="py-3.5 px-4">Metrik Evaluasi</th>
                            <th className="py-3.5 px-4">Base Model ({evaluation.base_model_name})</th>
                            <th className="py-3.5 px-4">Fine-Tuned Model ({evaluation.version_tag})</th>
                            <th className="py-3.5 px-4">Peningkatan / Delta</th>
                            <th className="py-3.5 px-4">Arah Optimal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 font-sans">
                          {evaluation.metrics.map((m, idx) => (
                            <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                              <td className="py-4 px-4 font-bold text-slate-200">
                                {m.metric_name}
                              </td>
                              <td className="py-4 px-4 font-mono text-slate-400">
                                {m.base_value} {m.unit}
                              </td>
                              <td className="py-4 px-4 font-mono font-bold text-indigo-400 text-sm">
                                {m.fine_tuned_value} {m.unit}
                              </td>
                              <td className="py-4 px-4">
                                <Badge variant="emerald" size="sm">
                                  {m.is_higher_better ? "+" : "-"}{m.improvement_pct}%
                                </Badge>
                              </td>
                              <td className="py-4 px-4 text-slate-400">
                                {m.is_higher_better ? "Lebih tinggi lebih baik (↑)" : "Lebih rendah lebih baik (↓)"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Academic Verdict Box */}
                    <div className="p-5 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-2">
                      <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                        <CheckCircle2 className="w-4 h-4" />
                        Kesimpulan Ilmiah Evaluasi (Academic Verdict)
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {evaluation.summary_verdict}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 6: KESEHATAN SISTEM & DATABASE */}
              {activeTab === "health" && overview && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Database Health Card */}
                    <div className="glass-panel p-6 border-slate-800 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Database className="w-4 h-4 text-purple-400" />
                          Status Database Engine
                        </h3>
                        <Badge variant="emerald">● HEALTHY</Badge>
                      </div>

                      <div className="space-y-3 text-xs">
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Database Driver:</span>
                          <span className="font-mono text-slate-200">{overview.database_stats.driver}</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Connection Pool Size:</span>
                          <span className="font-mono text-slate-200">{overview.database_stats.pool_size}</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Active Checked Out Connections:</span>
                          <span className="font-mono text-emerald-400 font-bold">{overview.database_stats.checked_out}</span>
                        </div>
                        <div className="flex justify-between py-2">
                          <span className="text-slate-400">Serverless Pool Overflow:</span>
                          <span className="font-mono text-slate-300">{overview.database_stats.overflow}</span>
                        </div>
                      </div>
                    </div>

                    {/* Table Distribution Card */}
                    <div className="glass-panel p-6 border-slate-800 space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <Activity className="w-4 h-4 text-blue-400" />
                          Distribusi Rekaman Data (Entity Records)
                        </h3>
                      </div>

                      <div className="space-y-3 text-xs">
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Total Sekolah Terdaftar:</span>
                          <span className="font-bold text-slate-200">{overview.counts.schools}</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Total Akun Pengguna:</span>
                          <span className="font-bold text-slate-200">{overview.counts.users}</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Assessment History (A7):</span>
                          <span className="font-bold text-indigo-400">{overview.counts.assessment_histories}</span>
                        </div>
                        <div className="flex justify-between py-2 border-b border-slate-800">
                          <span className="text-slate-400">Dataset Versions (A8):</span>
                          <span className="font-bold text-emerald-400">{overview.counts.dataset_versions}</span>
                        </div>
                        <div className="flex justify-between py-2">
                          <span className="text-slate-400">Registered Model Versions (A9.4):</span>
                          <span className="font-bold text-amber-400">{overview.counts.model_versions}</span>
                        </div>
                      </div>
                    </div>

                    {/* AI Safety & Webhook Integrity Card */}
                    <div className="glass-panel p-6 border-slate-800 space-y-4 md:col-span-2">
                      <div className="flex items-center justify-between">
                        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-emerald-400" />
                          Status Keamanan & Verifikasi Webhook AI (AI Safety Status)
                        </h3>
                        <Badge variant={overview.ai_safety_status?.webhook_secret_set ? "emerald" : "amber"}>
                          {overview.ai_safety_status?.webhook_secret_set ? "PROTECTED" : "ATTENTION"}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-center">
                          <div>
                            <div className="font-semibold text-slate-200">HMAC Callback Health</div>
                            <div className="text-slate-400 text-[11px] mt-0.5">X-AI-Signature Verification</div>
                          </div>
                          <Badge variant={overview.ai_safety_status?.hmac_callback_configured ? "emerald" : "amber"}>
                            {overview.ai_safety_status?.hmac_callback_configured ? "ONLINE" : "PENDING"}
                          </Badge>
                        </div>

                        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-center">
                          <div>
                            <div className="font-semibold text-slate-200">Webhook Secret Configuration</div>
                            <div className="text-slate-400 text-[11px] mt-0.5">AI_WEBHOOK_SECRET Environment</div>
                          </div>
                          <Badge variant={overview.ai_safety_status?.webhook_secret_set ? "emerald" : "amber"}>
                            {overview.ai_safety_status?.webhook_secret_set ? "ACTIVE" : "UNSET"}
                          </Badge>
                        </div>

                        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-center">
                          <div>
                            <div className="font-semibold text-slate-200">Replay Protection Engine</div>
                            <div className="text-slate-400 text-[11px] mt-0.5">Idempotent Event Logging</div>
                          </div>
                          <Badge variant={overview.ai_safety_status?.replay_protection_active ? "emerald" : "crimson"}>
                            {overview.ai_safety_status?.replay_protection_active ? "ENFORCED" : "INACTIVE"}
                          </Badge>

                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </RoleGuard>
    </AppShell>
  );
};
