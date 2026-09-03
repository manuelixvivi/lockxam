import { apiClient } from "./client";

export interface SchoolProfile {
  id: number;
  public_id: string;
  npsn: string;
  code: string;
  name: string;
  school_level_id: number;
  address: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  logo_url: string | null;
  is_active: boolean;
  status: string;
  admin_username?: string | null;
  subscription_status?: string | null;
  subscription_end_date?: string | null;
  domain?: string | null;
  created_at: string;
  updated_at: string;
}


export interface SchoolProfileUpdateRequest {
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  logo_url?: string | null;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

export interface SchoolDashboardSummary {
  school_id: number;
  school_name: string;
  school_code: string;
  total_students: number;
  total_teachers: number;
  total_classes: number;
  total_subjects: number;
  active_academic_year: string;
  active_academic_year_id?: number | null;
  active_exam_schedules: number;
}

const schoolProfilePromiseCache: Record<string, Promise<SchoolProfile>> = {};

export const schoolApi = {
  getSchoolProfile: async (schoolIdOrPublicId: string | number, forceFresh: boolean = false): Promise<SchoolProfile> => {
    const key = String(schoolIdOrPublicId);
    if (!forceFresh && schoolProfilePromiseCache[key] !== undefined) {
      return schoolProfilePromiseCache[key];
    }
    const p = apiClient.get<SchoolProfile>(`/api/v1/schools/${schoolIdOrPublicId}`).catch((err) => {
      delete schoolProfilePromiseCache[key];
      throw err;
    });
    schoolProfilePromiseCache[key] = p;
    return p;
  },

  getDashboardSummary: async (schoolIdOrPublicId: string | number): Promise<SchoolDashboardSummary> => {
    return apiClient.get<SchoolDashboardSummary>(`/api/v1/schools/${schoolIdOrPublicId}/dashboard-summary`);
  },

  updateSchoolProfile: async (
    publicId: string,
    data: SchoolProfileUpdateRequest
  ): Promise<SchoolProfile> => {
    return apiClient.request<SchoolProfile>(`/api/v1/schools/${publicId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  changeAdminPassword: async (data: { old_password: string; new_password: string }): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>("/api/v1/auth/change-password", data);
  },
};
