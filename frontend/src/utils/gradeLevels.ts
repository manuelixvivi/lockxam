export interface GradeLevelOption {
  value: string;
  label: string;
  category: "SD" | "SMP" | "SMA";
}

export const ALL_GRADE_OPTIONS: GradeLevelOption[] = [
  // SD (I - VI)
  { value: "I", label: "Tingkat I (SD/MI Kelas 1)", category: "SD" },
  { value: "II", label: "Tingkat II (SD/MI Kelas 2)", category: "SD" },
  { value: "III", label: "Tingkat III (SD/MI Kelas 3)", category: "SD" },
  { value: "IV", label: "Tingkat IV (SD/MI Kelas 4)", category: "SD" },
  { value: "V", label: "Tingkat V (SD/MI Kelas 5)", category: "SD" },
  { value: "VI", label: "Tingkat VI (SD/MI Kelas 6)", category: "SD" },
  // SMP (VII - IX)
  { value: "VII", label: "Tingkat VII (SMP/MTs Kelas 7)", category: "SMP" },
  { value: "VIII", label: "Tingkat VIII (SMP/MTs Kelas 8)", category: "SMP" },
  { value: "IX", label: "Tingkat IX (SMP/MTs Kelas 9)", category: "SMP" },
  // SMA / SMK / MA (X - XII)
  { value: "X", label: "Tingkat X (SMA/SMK/MA Kelas 10)", category: "SMA" },
  { value: "XI", label: "Tingkat XI (SMA/SMK/MA Kelas 11)", category: "SMA" },
  { value: "XII", label: "Tingkat XII (SMA/SMK/MA Kelas 12)", category: "SMA" },
];

/**
 * Returns grade level options filtered by school level code.
 * Defaults to SMA/SMK/MA (X, XI, XII).
 */
export function getGradeOptionsForSchool(schoolLevelCode?: string | null): GradeLevelOption[] {
  if (!schoolLevelCode) {
    return ALL_GRADE_OPTIONS.filter((g) => g.category === "SMA");
  }

  const code = schoolLevelCode.toUpperCase();
  if (["SD", "MI"].includes(code)) {
    return ALL_GRADE_OPTIONS.filter((g) => g.category === "SD");
  }
  if (["SMP", "MTS"].includes(code)) {
    return ALL_GRADE_OPTIONS.filter((g) => g.category === "SMP");
  }
  return ALL_GRADE_OPTIONS.filter((g) => g.category === "SMA");
}

export const ROMAN_GRADE_OPTIONS: GradeLevelOption[] = ALL_GRADE_OPTIONS.filter(
  (g) => g.category === "SMA"
);
