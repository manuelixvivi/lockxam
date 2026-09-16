import { apiClient } from "./client";

export type QuestionType = "PG" | "IS" | "ES";
export type PackageStatus = "INCOMPLETE" | "READY";

export interface Question {
  id: number;
  type: QuestionType;
  content: string;
  options: string[] | null;
  answer_key: string;
  rubrics: any[];
  owner_teacher_account_id: number;
  subject?: string;
  class_level?: string;
  ai_grading?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface QuestionPackage {
  id: number;
  public_id: string;
  school_id: number;
  name: string;
  class_level: string;
  subject?: string;
  target_counts: Record<QuestionType, number>;
  status: PackageStatus;
  owner_teacher_account_id: number;
  created_at?: string;
  updated_at?: string;
}

export interface PackageQuestion extends Question {
  canonical_order: number;
  score: number;
}

export interface QuestionPackageDetail extends QuestionPackage {
  questions: PackageQuestion[];
}

export interface QuestionPackageCreate {
  name: string;
  class_level: string;
  subject: string;
  target_counts: Record<string, number>;
}

export interface QuestionCreate {
  type: QuestionType;
  content: string;
  options: string[] | null;
  answer_key: string;
  rubrics: any[];
  subject: string;
  class_level?: string;
  ai_grading?: boolean;
}

export interface QuestionUpdate {
  content?: string;
  options?: string[] | null;
  answer_key?: string;
  rubrics?: any[];
  subject?: string;
  class_level?: string;
  ai_grading?: boolean;
}

export interface TeacherDashboardSummary {
  package_count: number;
  ready_package_count: number;
  question_count: number;
}

export const teacherContentApi = {
  getDashboardSummary: (): Promise<TeacherDashboardSummary> =>
    apiClient.get<TeacherDashboardSummary>("/api/v1/teacher/dashboard-summary"),

  // Question Packages
  listPackages: (limit?: number, skip: number = 0, search?: string): Promise<QuestionPackage[]> => {
    const params = new URLSearchParams();
    if (limit !== undefined) params.set("limit", limit.toString());
    if (skip > 0) params.set("skip", skip.toString());
    if (search && search.trim()) params.set("search", search.trim());
    const qs = params.toString();
    return apiClient.get<QuestionPackage[]>(`/api/v1/teacher/packages${qs ? `?${qs}` : ""}`);
  },

  getAssignedSubjects: (): Promise<string[]> =>
    apiClient.get<string[]>("/api/v1/teacher/packages/assigned-subjects"),

  createPackage: (data: QuestionPackageCreate): Promise<QuestionPackage> =>
    apiClient.post<QuestionPackage>("/api/v1/teacher/packages", data),

  getPackageDetail: (packageId: number): Promise<QuestionPackageDetail> =>
    apiClient.get<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}`),

  deletePackage: (packageId: number): Promise<void> =>
    apiClient.delete<void>(`/api/v1/teacher/packages/${packageId}`),

  revertPackageToDraft: (packageId: number): Promise<QuestionPackageDetail> =>
    apiClient.post<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/revert-draft`),

  publishPackage: (packageId: number): Promise<QuestionPackageDetail> =>
    apiClient.post<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/publish`),

  addQuestionToPackage: (packageId: number, questionId: number, score: number = 0.0): Promise<QuestionPackageDetail> =>
    apiClient.post<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/questions/${questionId}?score=${score}`),

  removeQuestionFromPackage: (packageId: number, questionId: number): Promise<QuestionPackageDetail> =>
    apiClient.delete<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/questions/${questionId}`),

  replaceQuestionInPackage: (packageId: number, oldQuestionId: number, newQuestionId: number, score?: number): Promise<QuestionPackageDetail> =>
    apiClient.post<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/questions/${oldQuestionId}/replace/${newQuestionId}${score !== undefined ? `?score=${score}` : ""}`),

  reorderQuestions: (packageId: number, orderMap: Record<number, number>): Promise<QuestionPackageDetail> =>
    apiClient.post<QuestionPackageDetail>(`/api/v1/teacher/packages/${packageId}/reorder`, orderMap),

  // Question Bank (Questions)
  listQuestions: (subject?: string, limit?: number, skip: number = 0, search?: string): Promise<Question[]> => {
    const params = new URLSearchParams();
    if (subject && subject.trim()) params.set("subject", subject.trim());
    if (limit !== undefined) params.set("limit", limit.toString());
    if (skip > 0) params.set("skip", skip.toString());
    if (search && search.trim()) params.set("search", search.trim());
    const qs = params.toString();
    return apiClient.get<Question[]>(`/api/v1/teacher/questions${qs ? `?${qs}` : ""}`);
  },

  createQuestion: (data: QuestionCreate): Promise<Question> =>
    apiClient.post<Question>("/api/v1/teacher/questions", data),

  updateQuestion: (questionId: number, data: QuestionUpdate): Promise<Question> =>
    apiClient.put<Question>(`/api/v1/teacher/questions/${questionId}`, data),

  deleteQuestion: (questionId: number): Promise<void> =>
    apiClient.delete<void>(`/api/v1/teacher/questions/${questionId}`),

  uploadQuestionImage: (file: File): Promise<{ url: string; filename: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<{ url: string; filename: string }>("/api/v1/teacher/questions/upload-image", formData);
  },

  generateAiRubric: (data: {
    question_text: string;
    answer_key: string;
    education_level?: string;
    education_class?: string;
  }): Promise<{ status: string; rubrics: any[]; concepts: string[]; error?: string }> =>
    apiClient.post<{ status: string; rubrics: any[]; concepts: string[]; error?: string }>("/api/v1/teacher/ai/generate-rubric", data),

  importQuestions: (data: {
    subject: string;
    rows: Array<{
      type: string;
      content: string;
      options: string[] | null;
      answer_key: string;
      rubrics: any[];
      class_level?: string;
      ai_grading?: boolean;
      row_num?: number;
      sheet?: string;
    }>;
  }): Promise<{
    status: string;
    message: string;
    imported_count: number;
    errors?: any[];
    skipped?: Array<{
      row: number;
      sheet?: string;
      content?: string;
      reason?: string;
    }>;
  }> => apiClient.post("/api/v1/teacher/questions/import", data),
};
