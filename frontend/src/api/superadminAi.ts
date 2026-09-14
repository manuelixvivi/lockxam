import { apiClient } from "./client";

export interface AiProviderConfig {
  provider: string;
  api_key_masked: string;
  is_api_key_configured: boolean;
  model_name: string;
  eval_model_name: string;
  fallback_model: string;
  temperature: number;
  max_output_tokens: number;
  rag_enabled: boolean;
  strict_transformer: boolean;
  embedding_model: string;
  rag_top_k: number;
  rag_similarity_threshold: number;
  max_rag_tokens: number;
  last_tested_at?: string | null;
  last_test_status?: "CONNECTED" | "ERROR" | string | null;
  last_test_latency_ms?: number | null;
  updated_at?: string | null;
  updated_by_name?: string | null;
}

export interface AiProviderConfigUpdatePayload {
  provider: string;
  api_key?: string;
  model_name: string;
  eval_model_name?: string;
  fallback_model?: string;
  temperature: number;
  max_output_tokens: number;
  rag_enabled?: boolean;
  strict_transformer?: boolean;
  embedding_model?: string;
  rag_top_k?: number;
  rag_similarity_threshold?: number;
  max_rag_tokens?: number;
}


export interface AiTestConnectionPayload {
  provider?: string;
  api_key?: string;
  model_name?: string;
}

export interface AiTestConnectionResult {
  success: boolean;
  latency_ms?: number | null;
  provider: string;
  model_name: string;
  message: string;
  error_detail?: string | null;
}

export interface AvailableAiModel {
  id: string;
  name: string;
  provider: string;
  context_window: number;
  is_recommended: boolean;
  description?: string;
}

export interface AiConfigHistoryItem {
  id: number;
  changed_by_name?: string | null;
  change_summary: string;
  provider: string;
  model_name: string;
  temperature?: number | null;
  created_at: string;
}

export interface ProductionModelSummary {
  version_tag: string;
  status: string;
  base_model_name: string;
  adapter_type: string;
  dataset_version?: string | null;
  trained_at?: string | null;
  artifact_verified: boolean;
  manifest_hash?: string | null;
}

export interface AiSystemOverview {
  production_model?: ProductionModelSummary | null;
  rag_enabled: boolean;
  strict_transformer: boolean;
  database_status: string;
  database_stats: {
    status: string;
    driver: string;
    pool_size: number;
    checked_out: number;
    overflow: number;
  };
  ai_provider_status: {
    provider: string;
    model: string;
    is_configured: boolean;
    last_test_status: string;
    last_test_latency_ms: number;
  };
  ai_safety_status?: {
    hmac_callback_configured: boolean;
    webhook_secret_set: boolean;
    replay_protection_active: boolean;
  };
  counts: {

    assessment_histories: number;
    training_candidates: number;
    dataset_versions: number;
    model_versions: number;
    schools: number;
    users: number;
  };
  training_stats: {
    running: number;
    completed: number;
    failed: number;
    total: number;
  };
  latest_evaluation?: {
    base_model: string;
    fine_tuned_model: string;
    mae: number;
    base_mae: number;
    rmse: number;
    base_rmse: number;
    pearson: number;
    base_pearson: number;
    spearman: number;
    base_spearman: number;
    agreement_rate_pct: number;
    base_agreement_rate_pct: number;
  } | null;
}

export interface ModelRegistryVersion {
  id: number;
  version_number: string;
  version_tag: string;
  status: "PRODUCTION" | "STAGED" | "ARCHIVED" | "FAILED" | string;
  base_model_name: string;
  adapter_type: string;
  dataset_version?: string | null;
  manifest_hash?: string | null;
  artifact_hash?: string | null;
  created_at?: string | null;
}

export interface RegisteredModelItem {
  id: number;
  name: string;
  display_name?: string;
  task_type: string;
  description?: string;
  current_production_version_id?: number | null;
  current_staged_version_id?: number | null;
  versions: ModelRegistryVersion[];
}

export interface TrainingJobItem {
  id: number;
  job_id: string;
  task_type: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | string;
  base_model_name: string;
  dataset_version_id: number;
  dataset_version_tag: string;
  training_config?: Record<string, any>;
  training_metrics?: Record<string, any>;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface EvaluationMetric {
  metric_name: string;
  base_value: number;
  fine_tuned_value: number;
  improvement_pct: number;
  unit: string;
  is_higher_better: boolean;
}

export interface EvaluationReport {
  model_name: string;
  version_tag: string;
  base_model_name: string;
  test_sample_count: number;
  evaluated_at: string;
  metrics: EvaluationMetric[];
  summary_verdict: string;
}

export const superadminAiApi = {
  getOverview: (): Promise<AiSystemOverview> =>
    apiClient.get<AiSystemOverview>("/api/v1/superadmin/ai-system/overview"),

  getConfig: (): Promise<AiProviderConfig> =>
    apiClient.get<AiProviderConfig>("/api/v1/superadmin/ai-system/config"),

  updateConfig: (payload: AiProviderConfigUpdatePayload): Promise<AiProviderConfig> =>
    apiClient.put<AiProviderConfig>("/api/v1/superadmin/ai-system/config", payload),

  testConnection: (payload: AiTestConnectionPayload): Promise<AiTestConnectionResult> =>
    apiClient.post<AiTestConnectionResult>("/api/v1/superadmin/ai-system/test-connection", payload),

  getAvailableModels: (apiKey?: string): Promise<AvailableAiModel[]> => {
    const qs = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
    return apiClient.get<AvailableAiModel[]>(`/api/v1/superadmin/ai-system/available-models${qs}`);
  },

  getConfigHistory: (): Promise<AiConfigHistoryItem[]> =>
    apiClient.get<AiConfigHistoryItem[]>("/api/v1/superadmin/ai-system/config/history"),

  getModelRegistry: (): Promise<{ models: RegisteredModelItem[]; total: number }> =>
    apiClient.get<{ models: RegisteredModelItem[]; total: number }>("/api/v1/superadmin/ai-system/model-registry"),

  getTrainingJobs: (): Promise<{ jobs: TrainingJobItem[]; total: number }> =>
    apiClient.get<{ jobs: TrainingJobItem[]; total: number }>("/api/v1/superadmin/ai-system/training-jobs"),

  getEvaluationReport: (): Promise<EvaluationReport> =>
    apiClient.get<EvaluationReport>("/api/v1/superadmin/ai-system/evaluation"),
};
