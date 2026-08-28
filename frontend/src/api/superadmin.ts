import { apiClient } from "./client";
import type { SchoolProfile } from "./school";



export interface SchoolLevelOption {
  id: number;
  name: string;
  code: string;
  description?: string;
}

export interface CreateSchoolPayload {
  npsn: string;
  code: string;
  name: string;
  domain: string;
  school_level_id: number;
  initial_subscription_preset?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  logo_url?: string;
}

export interface GenerateKeyPayload {
  school_id: number;
  license_type_id: number;
  validity_days?: number;
}

export interface GeneratedKeyResponse {
  public_id: string;
  key_plain: string;
  valid_until: string;
  status: string;
}

export interface GeneratedKeyListItem {
  public_id: string;
  key: string;
  school_id: number;
  license_type_id: number;
  status: string;
  valid_until: string;
  created_at: string;
}

export interface SuperAdminRenewalItem {
  id?: number;
  public_id: string;
  request_number?: string;
  school_id: number;
  requested_by_id?: number;
  license_type_id: number;
  status: "PENDING" | "REQUESTED" | "APPROVED" | "REJECTED" | string;

  payment_proof_url?: string;
  superadmin_notes?: string;
  created_at: string;
}


export interface ProcessRenewalPayload {
  status: "APPROVED" | "REJECTED";
  superadmin_notes?: string;
}

export interface ProcessRenewalResponse {
  renewal: SuperAdminRenewalItem;
  key_plain?: string;
}

export interface SchoolCreateResponse {
  school: SchoolProfile;
  admin_credentials: {
    username: string;
    temporary_password: string;
  };
}

export const superadminApi = {
  getSchools: async (): Promise<SchoolProfile[]> => {
    return apiClient.get<SchoolProfile[]>("/api/v1/schools");
  },

  getSchoolLevels: async (): Promise<SchoolLevelOption[]> => {
    return apiClient.get<SchoolLevelOption[]>("/api/v1/master/school-levels");
  },

  createSchool: async (payload: CreateSchoolPayload): Promise<SchoolCreateResponse> => {
    return apiClient.post<SchoolCreateResponse>("/api/v1/schools", payload);
  },

  updateSchool: async (publicId: string, payload: Partial<CreateSchoolPayload>): Promise<SchoolProfile> => {
    return apiClient.request<SchoolProfile>(`/api/v1/schools/${publicId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteSchool: async (publicId: string): Promise<{ message: string }> => {
    return apiClient.delete<{ message: string }>(`/api/v1/schools/${publicId}`);
  },

  resetSchoolAdminPassword: async (
    publicId: string
  ): Promise<{ message: string; username: string; new_password: string }> => {
    return apiClient.post<{ message: string; username: string; new_password: string }>(
      `/api/v1/schools/${publicId}/reset-admin-password`
    );
  },

  toggleSchoolSubscription: async (publicId: string): Promise<SchoolProfile> => {
    return apiClient.post<SchoolProfile>(`/api/v1/schools/${publicId}/toggle-subscription`);
  },



  generateActivationKey: async (payload: GenerateKeyPayload): Promise<GeneratedKeyResponse> => {
    return apiClient.post<GeneratedKeyResponse>("/api/v1/licenses/keys", payload);
  },

  getActivationKeys: async (): Promise<GeneratedKeyListItem[]> => {
    return apiClient.get<GeneratedKeyListItem[]>("/api/v1/licenses/keys");
  },

  cancelActivationKey: async (publicId: string): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(`/api/v1/licenses/keys/${publicId}/cancel`);
  },

  getRenewalRequests: async (): Promise<SuperAdminRenewalItem[]> => {
    return apiClient.get<SuperAdminRenewalItem[]>("/api/v1/licenses/renewals");
  },

  processRenewal: async (
    publicId: string,
    payload: ProcessRenewalPayload
  ): Promise<ProcessRenewalResponse> => {
    return apiClient.post<ProcessRenewalResponse>(`/api/v1/licenses/renewals/${publicId}/process`, payload);
  },
};
