import { apiClient } from "./client";

export interface ClassEntity {
  id: number;
  public_id: string;
  school_id: number;
  academic_year_id: number;
  name: string;
  grade_level?: string | null;
  is_active: boolean;
  student_count: number;
  subject_count: number;
  created_at: string;
  updated_at: string;
}

export interface ClassCreateRequest {
  academic_year_id: number;
  name: string;
  grade_level?: string | null;
}

export interface ClassUpdateRequest {
  name: string;
  grade_level?: string | null;
  is_active?: boolean;
}

export interface StudentEnrollment {
  id: number;
  public_id: string;
  school_id: number;
  student_id: number;
  class_id: number;
  academic_year_id: number;
  status: string;
  start_date: string;
  end_date?: string | null;
  student_name?: string | null;
  student_username?: string | null;
  nisn?: string | null;
  nis?: string | null;
  class_name?: string | null;
}

export interface ClassSubject {
  id: number;
  school_id: number;
  class_id: number;
  subject_id: number;
  created_at: string;
  subject_code?: string | null;
  subject_name?: string | null;
  teacher_id?: number | null;
  teacher_name?: string | null;
}

export interface ClassSubjectTeacher {
  id: number;
  school_id: number;
  class_id: number;
  subject_id: number;
  teacher_id: number;
  created_at: string;
  teacher_name?: string | null;
  teacher_username?: string | null;
  teacher_nip?: string | null;
  subject_name?: string | null;
  class_name?: string | null;
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

export const classApi = {
  listClasses: (academicYearId?: number, isActive?: boolean): Promise<ClassEntity[]> => {
    const params = new URLSearchParams();
    if (academicYearId !== undefined) params.append("academic_year_id", academicYearId.toString());
    if (isActive !== undefined) params.append("is_active", isActive.toString());
    const queryString = params.toString() ? `?${params.toString()}` : "";
    return apiClient.get<ClassEntity[]>(`/api/v1/admin/classes${queryString}`);
  },

  getClass: (publicId: string): Promise<ClassEntity> =>
    apiClient.get<ClassEntity>(`/api/v1/admin/classes/${publicId}`),

  createClass: (data: ClassCreateRequest): Promise<ClassEntity> =>
    apiClient.post<ClassEntity>("/api/v1/admin/classes", data),

  updateClass: (publicId: string, data: ClassUpdateRequest): Promise<ClassEntity> =>
    apiClient.put<ClassEntity>(`/api/v1/admin/classes/${publicId}`, data),

  deleteClass: (publicId: string): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/classes/${publicId}`),

  // Student Enrollments
  enrollStudent: (classId: number, studentId: number): Promise<StudentEnrollment> =>
    apiClient.post<StudentEnrollment>(`/api/v1/admin/classes/${classId}/students`, { student_id: studentId }),

  listEnrolledStudents: (classId: number): Promise<StudentEnrollment[]> =>
    apiClient.get<StudentEnrollment[]>(`/api/v1/admin/classes/${classId}/students`),

  removeStudent: (classId: number, studentId: number): Promise<void> =>
    apiClient.delete<void>(`/api/v1/admin/classes/${classId}/students/${studentId}`),

  // Class ↔ Subject & Teachers
  assignSubject: (classId: number, subjectId: number): Promise<ClassSubject> =>
    apiClient.post<ClassSubject>(`/api/v1/admin/classes/${classId}/subjects`, { subject_id: subjectId }),

  listClassSubjects: (classId: number): Promise<ClassSubject[]> =>
    apiClient.get<ClassSubject[]>(`/api/v1/admin/classes/${classId}/subjects`),

  assignTeacher: (classId: number, subjectId: number, teacherId: number): Promise<ClassSubjectTeacher> =>
    apiClient.post<ClassSubjectTeacher>(`/api/v1/admin/classes/${classId}/subjects/${subjectId}/teachers`, {
      teacher_id: teacherId,
    }),

  // Bulk operations
  bulkEnrollStudents: (classId: number, studentIds: number[]): Promise<{ status: string; enrolled_count: number }> =>
    apiClient.post<{ status: string; enrolled_count: number }>(`/api/v1/admin/classes/${classId}/students/bulk-enroll`, {
      student_ids: studentIds,
    }),

  bulkRemoveStudents: (classId: number, studentIds: number[]): Promise<{ status: string; removed_count: number }> =>
    apiClient.post<{ status: string; removed_count: number }>(`/api/v1/admin/classes/${classId}/students/bulk-remove`, {
      student_ids: studentIds,
    }),

  bulkAssignSubjects: (classId: number, subjectIds: number[]): Promise<{ status: string; assigned_count: number }> =>
    apiClient.post<{ status: string; assigned_count: number }>(`/api/v1/admin/classes/${classId}/subjects/bulk-assign`, {
      subject_ids: subjectIds,
    }),

  bulkRemoveSubjects: (classId: number, subjectIds: number[]): Promise<{ status: string; removed_count: number }> =>
    apiClient.post<{ status: string; removed_count: number }>(`/api/v1/admin/classes/${classId}/subjects/bulk-remove`, {
      subject_ids: subjectIds,
    }),

  importFullClassesXlsx: (data: {
    academic_year_id: number;
    classes: Array<{
      name: string;
      grade_level?: string | null;
      students?: Array<Record<string, any>>;
      subjects?: Array<Record<string, any>>;
    }>;
  }): Promise<{
    status: string;
    imported_classes_count: number;
    total_students_enrolled: number;
    total_subjects_assigned: number;
  }> => apiClient.post("/api/v1/admin/classes/import-full", data),

  getTeacherCandidates: (classId: number, subjectId: number): Promise<TeacherCandidate[]> =>
    apiClient.get<TeacherCandidate[]>(`/api/v1/admin/classes/${classId}/subjects/${subjectId}/teacher-candidates`),
};
