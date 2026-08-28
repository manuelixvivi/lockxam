import { apiClient } from "./client";

export interface Subject {
  id: number;
  public_id: string;
  school_id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubjectCreateRequest {
  code: string;
  name: string;
  description?: string | null;
}

export interface SubjectUpdateRequest {
  code: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface TeacherCandidate {
  teacher_id: number;
  public_id: string;
  name: string;
  username: string;
  nip?: string | null;
  is_active: boolean;
  status: string;
}

export interface TeacherSubjectResponse {
  id: number;
  school_id: number;
  teacher_id: number;
  subject_id: number;
  created_at: string;
  teacher_name?: string | null;
  teacher_username?: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
}

export const subjectApi = {
  listSubjects: (isActive?: boolean): Promise<Subject[]> => {
    const query = isActive !== undefined ? `?is_active=${isActive}` : "";
    return apiClient.get<Subject[]>(`/api/v1/admin/subjects${query}`);
  },

  getSubject: (publicId: string): Promise<Subject> =>
    apiClient.get<Subject>(`/api/v1/admin/subjects/${publicId}`),

  createSubject: (data: SubjectCreateRequest): Promise<Subject> =>
    apiClient.post<Subject>("/api/v1/admin/subjects", data),

  updateSubject: (publicId: string, data: SubjectUpdateRequest): Promise<Subject> =>
    apiClient.put<Subject>(`/api/v1/admin/subjects/${publicId}`, data),

  deleteSubject: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/subjects/${publicId}`),

  bulkDeleteSubjects: (subjectIds: number[]): Promise<void> =>
    apiClient.post<void>("/api/v1/admin/subjects/bulk-delete", { subject_ids: subjectIds }),

  bulkDeactivateSubjects: (subjectIds: number[]): Promise<void> =>
    apiClient.post<void>("/api/v1/admin/subjects/bulk-deactivate", { subject_ids: subjectIds }),

  bulkActivateSubjects: (subjectIds: number[]): Promise<void> =>
    apiClient.post<void>("/api/v1/admin/subjects/bulk-activate", { subject_ids: subjectIds }),

  assignTeacherCompetency: (subjectId: number, teacherId: number): Promise<TeacherSubjectResponse> =>
    apiClient.post<TeacherSubjectResponse>(`/api/v1/admin/subjects/${subjectId}/teachers/${teacherId}`),

  unassignTeacherCompetency: (subjectId: number, teacherId: number): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/subjects/${subjectId}/teachers/${teacherId}`),

  listQualifiedTeachers: (subjectId: number): Promise<TeacherCandidate[]> =>
    apiClient.get<TeacherCandidate[]>(`/api/v1/admin/subjects/${subjectId}/teachers`),

  importSubjects: (data: {
    subjects: Array<{
      code: string;
      name: string;
      description?: string;
      row_num?: number;
    }>;
  }): Promise<{
    status: string;
    imported_count: number;
    data: Subject[];
  }> => apiClient.post("/api/v1/admin/subjects/import", data),
};

// Batch 3 Bulk Import Remediation Verified

