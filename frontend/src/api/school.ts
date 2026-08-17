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

export const schoolApi = {
  getSchoolProfile: async (schoolIdOrPublicId: string | number): Promise<SchoolProfile> => {
    // If it's a UUID string, fetch directly by public_id
    if (typeof schoolIdOrPublicId === "string" && schoolIdOrPublicId.includes("-")) {
      return apiClient.get<SchoolProfile>(`/api/v1/schools/${schoolIdOrPublicId}`);
    }

    // Otherwise, fetch all schools and find matching school_id
    const schools = await apiClient.get<SchoolProfile[]>("/api/v1/schools");
    const numId = typeof schoolIdOrPublicId === "number" ? schoolIdOrPublicId : parseInt(schoolIdOrPublicId, 10);
    const found = schools.find((s) => s.id === numId);

    if (!found) {
      throw {
        statusCode: 404,
        message: `Sekolah dengan ID #${schoolIdOrPublicId} tidak ditemukan.`,
      };
    }

    return found;
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
