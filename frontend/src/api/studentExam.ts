import { apiClient } from "./client";

export interface StudentSchedule {
  schedule_id: number;
  session_id: number | null;
  title: string;
  subject_id: number;
  subject_name: string;
  class_id: number;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  lock_browser: boolean;
  eyd_language_evaluation: boolean;
  randomize_per_type: boolean;
  status: string;
  category?: "UPCOMING" | "ACTIVE" | "MISSED" | "COMPLETED" | "CANCELLED";
  attempt_id: number | null;
  attempt_status: string;
  attempt_remaining_seconds: number | null;
  // QR check-in fields
  has_checked_in: boolean;
  checked_in_at: string | null;
  final_score?: number | null;
}

export interface ClassLeaderboardItem {
  rank: number;
  student_id: number;
  student_name: string;
  avatar_initial: string;
  avg_score: number;
  total_exams: number;
  is_self: boolean;
}

export interface ClassLeaderboardResponse {
  rank_self: number | null;
  total_class_students: number;
  leaderboard: ClassLeaderboardItem[];
}

export interface StudentQuestionItem {
  question_id: number;
  question_type: "PG" | "IS" | "ES";
  content: string;
  options?: { key: string; text: string }[];
  score_weight: number;
}

export interface ExamAttemptData {
  id: number;
  exam_session_id: number;
  student_id: number;
  status: string;
  started_at: string;
  deadline_at: string;
  remaining_seconds: number | null;
  randomized_order?: any;
  questions?: StudentQuestionItem[];
  answers?: Record<number, { selected_option?: string; text_answer?: string; is_flagged?: boolean }>;
}

let activeDeviceId: string | null = null;
let activeDeviceToken: string | null = null;

export const setDeviceToken = (token: string | null) => {
  activeDeviceToken = token;
};

export const getDeviceId = (): string => {
  if (!activeDeviceId) {
    try {
      activeDeviceId = sessionStorage.getItem("equigrade_device_id");
    } catch {}
    if (!activeDeviceId) {
      const randomUuid =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : Math.random().toString(36).substring(2, 15);
      activeDeviceId = `DEV_${randomUuid}`;
      try {
        sessionStorage.setItem("equigrade_device_id", activeDeviceId);
      } catch {}
    }
  }
  return activeDeviceId;
};

export const studentExamApi = {
  // Get active exam schedules for the student
  getMySchedules: async (): Promise<StudentSchedule[]> => {
    const res = await apiClient.get<StudentSchedule[]>("/api/v1/exam/my-schedules");
    return res;
  },

  // Start or resume exam attempt
  startAttempt: async (sessionId: number): Promise<ExamAttemptData> => {
    const deviceId = getDeviceId();
    const res = await apiClient.post<ExamAttemptData & { device_session_token?: string }>(
      `/api/v1/exam/sessions/${sessionId}/start-attempt`,
      {},
      { "X-Device-Id": deviceId }
    );
    if (res.device_session_token) {
      activeDeviceToken = res.device_session_token;
    }
    return res;
  },

  // Autosave single question answer (JSON Body)
  autosaveAnswer: async (
    attemptId: number,
    questionId: number,
    selectedOption?: string,
    textAnswer?: string,
    deviceToken?: string
  ) => {
    const token = deviceToken || activeDeviceToken || "";

    const payload: any = { question_id: questionId };
    if (selectedOption !== undefined && selectedOption !== null) {
      payload.selected_option = selectedOption;
    }
    if (textAnswer !== undefined && textAnswer !== null) {
      payload.text_answer = textAnswer;
    }

    const res = await apiClient.post(
      `/api/v1/exam/attempts/${attemptId}/autosave`,
      payload,
      { "X-Device-Token": token }
    );
    return res;
  },

  // Batch flush all local answers before submit
  flushAnswers: async (
    attemptId: number,
    answers: Record<number, { selected_option?: string; text_answer?: string }>
  ) => {
    const token = activeDeviceToken || "";
    const res = await apiClient.post(
      `/api/v1/exam/attempts/${attemptId}/flush-answers`,
      { answers },
      token ? { "X-Device-Token": token } : {}
    );
    return res;
  },

  // Final submit attempt
  submitAttempt: async (attemptId: number): Promise<ExamAttemptData> => {
    const res = await apiClient.post<ExamAttemptData>(`/api/v1/exam/attempts/${attemptId}/submit`, {});
    return res;
  },

  // QR Absensi — siswa submit token yang discan dari QR pengawas
  checkin: async (
    token: string,
    expectedScheduleId?: number
  ): Promise<{
    success: boolean;
    message: string;
    schedule_id: number;
    schedule_title: string;
    start_time: string;
    end_time: string;
    checked_in_at: string;
    device_id: string;
  }> => {
    const deviceId = getDeviceId();
    const query = new URLSearchParams({ token });
    if (expectedScheduleId) query.append("expected_schedule_id", expectedScheduleId.toString());

    const res = await apiClient.post(
      `/api/v1/exam/checkin?${query.toString()}`,
      {},
      { "X-Device-Id": deviceId }
    );
    return res as any;
  },

  // Send device telemetry & violation reports
  sendTelemetry: async (
    attemptId: number,
    data: {
      battery_level?: number;
      is_charging?: boolean;
      ping_ms?: number;
      is_offline?: boolean;
      violation_type?: string;
      violation_reason?: string;
    }
  ) => {
    const res = await apiClient.post(`/api/v1/exam/attempts/${attemptId}/telemetry`, data);
    return res as any;
  },

  // Get class leaderboard data
  getClassLeaderboard: async (): Promise<ClassLeaderboardResponse> => {
    const res = await apiClient.get<ClassLeaderboardResponse>("/api/v1/exam/class-leaderboard");
    return res;
  },

  getAttemptReview: async (attemptId: number): Promise<any> => {
    const res = await apiClient.get(`/api/v1/exam/attempts/${attemptId}/review`);
    return res;
  },
};
