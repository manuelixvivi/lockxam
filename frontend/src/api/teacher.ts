import { apiClient } from "./client";

export interface TeacherAccount {
  id: number;
  public_id: string;
  username: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  
  // Profile fields
  name: string | null;
  nip: string | null;
  teacher_code: string | null;
  gender: string | null;
  registered_year: number | null;
  classes_taught: string[] | null;
  subjects_taught: string[] | null;
}

export interface TeacherCreateRequest {
  name: string;
  nip?: string;
  teacher_code?: string;
  gender: string;
  registered_year?: number | string;
  classes_taught?: string[];
  subjects_taught?: string[];
}

export interface TeacherUpdateRequest {
  name?: string;
  nip?: string;
  teacher_code?: string;
  gender?: string;
  registered_year?: number | string;
  classes_taught?: string[];
  subjects_taught?: string[];
  is_active?: boolean;
}

export interface TeacherCreateResponse {
  account: TeacherAccount;
  default_password: string;
}

export interface ResetPasswordResult {
  message: string;
  username: string;
  new_password: string;
}

export const teacherApi = {
  listTeachers: (): Promise<TeacherAccount[]> =>
    apiClient.get<TeacherAccount[]>("/api/v1/admin/teachers"),

  createTeacher: (data: TeacherCreateRequest): Promise<TeacherCreateResponse> =>
    apiClient.post<TeacherCreateResponse>("/api/v1/admin/teachers", data),

  updateTeacher: (publicId: string, data: TeacherUpdateRequest): Promise<TeacherAccount> =>
    apiClient.put<TeacherAccount>(`/api/v1/admin/teachers/${publicId}`, data),

  deleteTeacher: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/teachers/${publicId}`),

  toggleActive: (publicId: string): Promise<TeacherAccount> =>
    apiClient.post<TeacherAccount>(`/api/v1/admin/teachers/${publicId}/toggle-active`),

  resetPassword: (publicId: string): Promise<ResetPasswordResult> =>
    apiClient.post<ResetPasswordResult>(`/api/v1/admin/teachers/${publicId}/reset-password`),
};
