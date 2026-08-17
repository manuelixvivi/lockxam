import { apiClient } from "./client";

export interface ActiveLicenseResponse {
  id?: number;
  public_id: string;
  school_id: number;
  license_type_id: number;
  license_type_name?: string;
  status: "ACTIVE" | "EXPIRED" | "SUSPENDED" | "PENDING" | string;
  start_date?: string;
  end_date?: string;
  valid_from?: string;
  valid_until?: string;
  max_users?: number;
  max_students?: number;
  created_at?: string;
}


export interface LicenseTypeOption {
  id: number;
  name: string;
  code: string;
  description: string;
  max_students: number;
  duration_days: number;
}

export interface RenewalRequestPayload {
  license_type_id: number;
  payment_proof_url?: string;
}

export interface RenewalRequestResponse {
  id: number;
  public_id: string;
  school_id: number;
  license_type_id: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  created_at: string;
}

export const licenseApi = {
  getMyLicense: async (): Promise<ActiveLicenseResponse | null> => {
    return apiClient.get<ActiveLicenseResponse | null>("/api/v1/licenses/my-license");
  },

  getLicenseTypes: async (): Promise<LicenseTypeOption[]> => {
    return apiClient.get<LicenseTypeOption[]>("/api/v1/master/license-types");
  },

  activateLicenseKey: async (keyPlain: string): Promise<ActiveLicenseResponse> => {
    return apiClient.post<ActiveLicenseResponse>("/api/v1/licenses/activate", {
      key_plain: keyPlain.trim(),
    });
  },

  requestRenewal: async (payload: RenewalRequestPayload): Promise<RenewalRequestResponse> => {
    return apiClient.post<RenewalRequestResponse>("/api/v1/licenses/renewals", payload);
  },
};
