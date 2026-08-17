import { apiClient } from "./client";

export interface ExamSchedule {
  id: number;
  public_id: string;
  school_id: number;
  academic_year_id: number;
  academic_semester_id: number;
  class_id: number;
  subject_id: number;
  teacher_id: number;
  proctor_id?: number | null;
  name: string;
  date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  status: "DRAFT" | "SCHEDULED" | "LOCKED" | "ACTIVE" | "COMPLETED" | "ARCHIVED" | string;
  target_type?: "ALL_CLASS" | "SPECIFIC_STUDENTS" | string;
  allowed_student_ids?: number[] | null;
  lock_browser?: boolean;
  eyd_language_evaluation?: boolean;
  randomize_per_type?: boolean;
  token?: string | null;
  created_at: string;
  updated_at: string;

  // Joined metadata
  class_name?: string | null;
  subject_name?: string | null;
  teacher_name?: string | null;
  proctor_name?: string | null;
  semester_name?: string | null;
}

export interface ExamSchedulePackage {
  id: number;
  public_id: string;
  school_id: number;
  academic_year_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  academic_year_name?: string | null;
  schedules: ExamSchedule[];
}

export interface ExamSchedulePackageCreateRequest {
  title: string;
  academic_year_id: number;
}

export interface ExamScheduleCreateRequest {
  academic_year_id?: number;
  academic_semester_id?: number;
  class_id?: number;
  subject_id?: number;
  name?: string;
  date?: string;
  start_time?: string;
  end_time?: string;
  duration_minutes?: number;
  proctor_id?: number | null;
  package_id?: number | null;
  status?: string;
  target_type?: "ALL_CLASS" | "SPECIFIC_STUDENTS" | string;
  allowed_student_ids?: number[] | null;
  lock_browser?: boolean;
  eyd_language_evaluation?: boolean;
  randomize_per_type?: boolean;
}

export interface ExamScheduleProctorAssignRequest {
  proctor_id: number;
}

export const examScheduleApi = {
  listSchedules: (
    academicYearId?: number,
    academicSemesterId?: number,
    classId?: number
  ): Promise<ExamSchedule[]> => {
    const params = new URLSearchParams();
    if (academicYearId !== undefined) params.append("academic_year_id", academicYearId.toString());
    if (academicSemesterId !== undefined) params.append("academic_semester_id", academicSemesterId.toString());
    if (classId !== undefined) params.append("class_id", classId.toString());
    const queryString = params.toString() ? `?${params.toString()}` : "";
    return apiClient.get<ExamSchedule[]>(`/api/v1/admin/exam-schedules${queryString}`);
  },

  getSchedule: (publicId: string): Promise<ExamSchedule> =>
    apiClient.get<ExamSchedule>(`/api/v1/admin/exam-schedules/${publicId}`),

  createSchedule: (data: ExamScheduleCreateRequest): Promise<ExamSchedule> =>
    apiClient.post<ExamSchedule>("/api/v1/admin/exam-schedules", data),

  updateSchedule: (publicId: string, data: Partial<ExamScheduleCreateRequest>): Promise<ExamSchedule> =>
    apiClient.put<ExamSchedule>(`/api/v1/admin/exam-schedules/${publicId}`, data),

  assignProctor: (publicId: string, data: ExamScheduleProctorAssignRequest): Promise<ExamSchedule> =>
    apiClient.put<ExamSchedule>(`/api/v1/admin/exam-schedules/${publicId}/proctor`, data),

  deleteSchedule: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/exam-schedules/${publicId}`),

  // Package Management Endpoints
  listPackages: (academicYearId?: number): Promise<ExamSchedulePackage[]> => {
    const q = academicYearId ? `?academic_year_id=${academicYearId}` : "";
    return apiClient.get<ExamSchedulePackage[]>(`/api/v1/admin/exam-schedules/packages${q}`);
  },

  getPackage: (publicId: string): Promise<ExamSchedulePackage> =>
    apiClient.get<ExamSchedulePackage>(`/api/v1/admin/exam-schedules/packages/${publicId}`),

  createPackage: (data: ExamSchedulePackageCreateRequest): Promise<ExamSchedulePackage> =>
    apiClient.post<ExamSchedulePackage>("/api/v1/admin/exam-schedules/packages", data),

  deletePackage: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/exam-schedules/packages/${publicId}`),

  importSchedulesXlsx: (publicId: string, rows: any[]): Promise<ExamSchedule[]> =>
    apiClient.post<ExamSchedule[]>(`/api/v1/admin/exam-schedules/packages/${publicId}/import`, rows),
};
