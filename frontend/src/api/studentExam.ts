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

export const studentExamApi = {
  // Get active exam schedules for the student
  getMySchedules: async (): Promise<StudentSchedule[]> => {
    const res = await apiClient.get<StudentSchedule[]>("/api/v1/exam/my-schedules");
    return res;
  },

  // Start or resume exam attempt
  startAttempt: async (sessionId: number): Promise<ExamAttemptData> => {
    const deviceId = localStorage.getItem("equigrade_device_id") || `DEV_${Math.random().toString(36).substring(2, 10)}`;
    localStorage.setItem("equigrade_device_id", deviceId);

    const res = await apiClient.post<ExamAttemptData>(
      `/api/v1/exam/sessions/${sessionId}/start-attempt`,
      {},
      { "X-Device-Id": deviceId }
    );
    return res;
  },

  // Autosave single question answer
  autosaveAnswer: async (
    attemptId: number,
    questionId: number,
    selectedOption?: string,
    textAnswer?: string,
    deviceToken?: string
  ) => {
    const token = deviceToken || localStorage.getItem("equigrade_device_token") || "token_default";

    const params = new URLSearchParams();
    params.append("question_id", questionId.toString());
    if (selectedOption !== undefined && selectedOption !== null) {
      params.append("selected_option", selectedOption);
    }
    if (textAnswer !== undefined && textAnswer !== null) {
      params.append("text_answer", textAnswer);
    }

    const res = await apiClient.post(
      `/api/v1/exam/attempts/${attemptId}/autosave?${params.toString()}`,
      {},
      { "X-Device-Token": token }
    );
    return res;
  },

  // Final submit attempt
  submitAttempt: async (attemptId: number): Promise<ExamAttemptData> => {
    const res = await apiClient.post<ExamAttemptData>(`/api/v1/exam/attempts/${attemptId}/submit`, {});
    return res;
  },

  // QR Absensi — siswa submit token yang discan dari QR pengawas
  checkin: async (token: string): Promise<{
    success: boolean;
    message: string;
    schedule_id: number;
    schedule_title: string;
    start_time: string;
    end_time: string;
    checked_in_at: string;
    device_id: string;
  }> => {
    const deviceId = localStorage.getItem("equigrade_device_id") || `DEV_${Math.random().toString(36).substring(2, 10)}`;
    localStorage.setItem("equigrade_device_id", deviceId);

    const res = await apiClient.post(
      `/api/v1/exam/checkin?token=${encodeURIComponent(token)}`,
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
};
