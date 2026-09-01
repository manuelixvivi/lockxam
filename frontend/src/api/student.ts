import { apiClient } from "./client";

export interface StudentAccount {
  id: number;
  public_id: string;
  username: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  name?: string;
  nis?: string;
  nisn?: string;
  birth_date?: string; // YYYY-MM-DD
  gender?: string;
  class_name?: string;
  registered_year?: number;
}

export interface StudentCreateRequest {
  name: string;
  nisn: string;
  gender: string;
  nis?: string;
  birth_date?: string; // YYYY-MM-DD
  class_name?: string;
  registered_year?: number;
}

export interface StudentUpdateRequest {
  is_active?: boolean;
  name?: string;
  nisn?: string;
  nis?: string | null;
  birth_date?: string | null; // YYYY-MM-DD
  gender?: string;
  class_name?: string | null;
  registered_year?: number | null;
}

export interface StudentCreateResponse {
  account: StudentAccount;
  default_password: string;
}

export interface StudentResetPasswordResult {
  message: string;
  username: string;
  new_password: string;
}

export const studentApi = {
  listStudents: (): Promise<StudentAccount[]> =>
    apiClient.get<StudentAccount[]>("/api/v1/admin/students"),

  createStudent: (data: StudentCreateRequest): Promise<StudentCreateResponse> =>
    apiClient.post<StudentCreateResponse>("/api/v1/admin/students", data),

  updateStudent: (publicId: string, data: StudentUpdateRequest): Promise<StudentAccount> =>
    apiClient.put<StudentAccount>(`/api/v1/admin/students/${publicId}`, data),

  deleteStudent: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/students/${publicId}`),

  toggleActive: (publicId: string): Promise<StudentAccount> =>
    apiClient.post<StudentAccount>(`/api/v1/admin/students/${publicId}/toggle-active`),

  resetPassword: (publicId: string): Promise<StudentResetPasswordResult> =>
    apiClient.post<StudentResetPasswordResult>(`/api/v1/admin/students/${publicId}/reset-password`),

  clearSessions: (publicId: string): Promise<{ message: string; username: string }> =>
    apiClient.post<{ message: string; username: string }>(`/api/v1/admin/students/${publicId}/clear-sessions`),

  importStudents: (data: {
    academic_year_id: number;
    rows: Array<{
      name?: string;
      nisn?: string;
      nis?: string;
      gender?: string;
      birth_date?: string;
      class_name?: string;
      registered_year?: number;
    }>;
  }): Promise<{
    status: "success" | "error";
    message: string;
    imported_count: number;
    errors?: Array<{
      row: number;
      field: string;
      value?: string;
      code: string;
      message: string;
    }>;
    data?: StudentAccount[];
    skipped?: Array<{
      row: number;
      sheet?: string;
      content?: string;
      reason?: string;
    }>;
  }> => apiClient.post("/api/v1/admin/students/import", data),
};
