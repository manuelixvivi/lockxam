export interface SubjectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

/**
 * Returns strictly the subjects assigned to the teacher.
 */
export function getTeacherAssignedSubjectOptions(teacherSubjects?: string[]): SubjectOption[] {
  const assigned = (teacherSubjects || []).filter(Boolean);
  if (assigned.length === 0) {
    return [
      {
        value: "",
        label: "⚠️ Belum ada mata pelajaran yang di-assign oleh Admin",
        disabled: true,
      },
    ];
  }
  return assigned.map((s) => ({
    value: s,
    label: s,
  }));
}
