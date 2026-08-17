import { apiClient } from "./client";

export interface AcademicSemester {
  id: number;
  public_id: string;
  academic_year_id: number;
  code: string;
  display_name: string;
  status: "PLANNED" | "ACTIVE" | "ARCHIVED";
  is_active?: boolean;
  created_at: string;
}


export interface AcademicYear {
  id: number;
  public_id: string;
  school_id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: "PLANNED" | "ACTIVE" | "PENDING_ARCHIVE" | "ARCHIVED";
  created_at: string;
  updated_at: string;
  semesters?: AcademicSemester[];
}

export interface CreateAcademicYearPayload {
  name: string;
  start_date: string;
  end_date: string;
}

export interface CreateAcademicSemesterPayload {
  academic_year_id: number;
  code: string;
  display_name: string;
}

export const academicApi = {
  getAcademicYears: async (): Promise<AcademicYear[]> => {
    return apiClient.get<AcademicYear[]>("/api/v1/academic/periods");
  },

  createAcademicYear: async (payload: CreateAcademicYearPayload): Promise<AcademicYear> => {
    return apiClient.post<AcademicYear>("/api/v1/academic/years", payload);
  },

  rolloverAcademicYear: async (publicId: string): Promise<AcademicYear> => {
    return apiClient.post<AcademicYear>(`/api/v1/academic/years/${publicId}/rollover`);
  },

  closeAcademicYear: async (publicId: string): Promise<AcademicYear> => {
    return apiClient.post<AcademicYear>(`/api/v1/academic/years/${publicId}/close`);
  },

  finalizeArchiveAcademicYear: async (publicId: string): Promise<AcademicYear> => {
    return apiClient.post<AcademicYear>(`/api/v1/academic/years/${publicId}/finalize`);
  },

  deleteAcademicYear: async (publicId: string): Promise<void> => {
    return apiClient.delete<void>(`/api/v1/academic/years/${publicId}`);
  },

  createAcademicSemester: async (
    payload: CreateAcademicSemesterPayload
  ): Promise<AcademicSemester> => {
    return apiClient.post<AcademicSemester>("/api/v1/academic/semesters", payload);
  },

  activateAcademicSemester: async (publicId: string): Promise<AcademicSemester> => {
    return apiClient.post<AcademicSemester>(`/api/v1/academic/semesters/${publicId}/activate`);
  },
};
