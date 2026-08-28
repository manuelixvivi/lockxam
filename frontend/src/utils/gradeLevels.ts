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

/**
 * Normalizes AI generated rubric weights proportionally based on criteria length & keyword density
 * so weights dynamically reflect the importance/complexity of each criterion in the answer key,
 * summing to 100%.
 */
export function normalizeRubricWeights(
  rawRubrics: Array<{ criteria?: string; text?: string; weight?: number; max_score?: number }>,
  answerKey: string = ""
): Array<{ criteria: string; max_score: number }> {
  if (!rawRubrics || rawRubrics.length === 0) return [];

  const items = rawRubrics.map((r) => ({
    criteria: (r.criteria || r.text || "Kriteria Penilaian").trim(),
    rawWeight: typeof r.weight === "number" && r.weight > 0 ? r.weight : (r.max_score || 0),
  }));

  const firstW = items[0].rawWeight;
  const isUniform = items.length > 1 && items.every((item) => Math.abs(item.rawWeight - firstW) < 0.01);

  if (!isUniform && items.some((item) => item.rawWeight > 0)) {
    const totalRaw = items.reduce((sum, item) => sum + item.rawWeight, 0);
    let cumulative = 0;
    return items.map((item, idx) => {
      if (idx === items.length - 1) {
        return { criteria: item.criteria, max_score: Math.max(5, 100 - cumulative) };
      }
      const score = Math.max(5, Math.round((item.rawWeight / totalRaw) * 100));
      cumulative += score;
      return { criteria: item.criteria, max_score: score };
    });
  }

  const keyLower = answerKey.toLowerCase();
  const rawScores = items.map((item) => {
    const text = item.criteria.toLowerCase();
    const words = text.split(/\s+/).filter((w) => w.length > 2);
    let matches = 0;
    words.forEach((w) => {
      if (keyLower.includes(w)) matches += 1;
    });
    return Math.max(1, words.length * 2 + matches * 3);
  });

  const totalScore = rawScores.reduce((a, b) => a + b, 0);
  let accumulated = 0;

  return items.map((item, idx) => {
    if (idx === items.length - 1) {
      const finalScore = Math.max(5, 100 - accumulated);
      return { criteria: item.criteria, max_score: finalScore };
    }
    const prop = (rawScores[idx] / totalScore) * 100;
    const rounded5 = Math.max(5, Math.round(prop / 5) * 5);
    accumulated += rounded5;
    return { criteria: item.criteria, max_score: rounded5 };
  });
}
