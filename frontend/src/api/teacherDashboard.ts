import { apiClient } from "./client";

export interface TeacherAssignment {
  id: number;
  public_id: string;
  title: string;
  class_id: number;
  class_name: string | null;
  grade_level?: string | null;
  academic_year_name?: string | null;
  subject_id: number;
  subject_name: string | null;
  start_time: string;
  end_time: string;
  status: string;
  has_snapshot: boolean;
  snapshot_id: number | null;
  snapshot_package_name: string | null;
  assigned_package_public_id?: string | null;
}

export interface TeacherProctorAssignment {
  id: number;
  public_id: string;
  title: string;
  class_id: number;
  class_name: string | null;
  subject_id: number;
  subject_name: string | null;
  start_time: string;
  end_time: string;
  status: string;
  exam_session_id: number | null;
  exam_session_status: string | null;
}

export interface StudentAttemptProctor {
  attempt_id: number;
  student_id: number;
  student_name: string;
  student_username: string;
  nisn: string | null;
  nis: string | null;
  status: string;
  started_at: string | null;
  deadline_at: string | null;
  remaining_seconds: number | null;
  device_status: string | null;
  device_id: string | null;
  ip_address: string | null;
}

export interface EssayGradingEvaluation {
  evaluation_id: number;
  attempt_id: number;
  student_name: string;
  exam_title: string;
  class_name: string;
  question_id: number;
  question_content: string;
  student_answer: string | null;
  ai_score: number;
  max_score?: number;
  ai_feedback: string | null;
  grading_status: string;
  final_score: number | null;
}

export const teacherDashboardApi = {
  listAssignments: (): Promise<TeacherAssignment[]> =>
    apiClient.get<TeacherAssignment[]>("/api/v1/teacher/assignments"),

  finalizeAssignment: (
    schedulePublicId: string,
    packagePublicId: string,
    options?: {
      lock_browser?: boolean;
      eyd_language_evaluation?: boolean;
      randomize_per_type?: boolean;
    }
  ): Promise<any> =>
    apiClient.post<any>(`/api/v1/teacher/assignments/${schedulePublicId}/finalize`, {
      package_public_id: packagePublicId,
      lock_browser: options?.lock_browser ?? true,
      eyd_language_evaluation: options?.eyd_language_evaluation ?? false,
      randomize_per_type: options?.randomize_per_type ?? true,
    }),

  unassignAssignment: (schedulePublicId: string): Promise<any> =>
    apiClient.post<any>(`/api/v1/teacher/assignments/${schedulePublicId}/unassign`),

  listProctorAssignments: (): Promise<TeacherProctorAssignment[]> =>
    apiClient.get<TeacherProctorAssignment[]>("/api/v1/teacher/proctor/assignments"),

  listClassStudents: (classId: number): Promise<any[]> =>
    apiClient.get<any[]>(`/api/v1/teacher/classes/${classId}/students`),

  listSessionAttempts: (examSessionId: number): Promise<StudentAttemptProctor[]> =>
    apiClient.get<StudentAttemptProctor[]>(`/api/v1/teacher/sessions/${examSessionId}/attempts`),

  listGradingEvaluations: (): Promise<EssayGradingEvaluation[]> =>
    apiClient.get<EssayGradingEvaluation[]>("/api/v1/teacher/grading/evaluations"),

  finalizeGrading: (evaluationId: number, score: number, feedback?: string): Promise<any> =>
    apiClient.post<any>(`/api/v1/teacher/grading/evaluations/${evaluationId}/finalize`, {
      score,
      feedback,
    }),
};
