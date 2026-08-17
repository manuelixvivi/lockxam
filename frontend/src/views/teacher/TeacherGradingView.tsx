import React, { useState, useEffect } from "react";
import {
  Award,
  RefreshCw,
  Edit2,
  CheckCircle,
  FileText,
  Sparkles,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { teacherDashboardApi } from "../../api/teacherDashboard";
import type { EssayGradingEvaluation } from "../../api/teacherDashboard";

export function TeacherGradingView() {
  const { showToast } = useToast();
  const [evaluations, setEvaluations] = useState<EssayGradingEvaluation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Grading Modal State
  const [selectedEval, setSelectedEval] = useState<EssayGradingEvaluation | null>(null);
  const [score, setScore] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchEvaluations = async () => {
    setIsLoading(true);
    try {
      const data = await teacherDashboardApi.listGradingEvaluations();
      setEvaluations(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Hasil Ujian",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvaluations();
  }, []);

  const handleOpenGradingModal = (ev: EssayGradingEvaluation) => {
    setSelectedEval(ev);
    setScore(ev.ai_score.toString());
    setFeedback(ev.ai_feedback || "");
  };

  const handleFinalizeGrading = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEval) return;

    const numericScore = parseFloat(score);
    const maxScore = selectedEval.max_score || 100;
    if (isNaN(numericScore) || numericScore < 0 || numericScore > maxScore) {
      showToast({ type: "warning", title: "Validasi Gagal", message: `Nilai harus berupa angka antara 0 hingga ${maxScore}.` });
      return;
    }

    setIsSubmitting(true);
    try {
      await teacherDashboardApi.finalizeGrading(selectedEval.evaluation_id, numericScore, feedback.trim());
      showToast({ type: "success", title: "Penilaian Berhasil", message: "Skor esai berhasil dikunci." });
      setSelectedEval(null);
      fetchEvaluations();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal Menyimpan Penilaian", message: err?.message || "Terjadi kesalahan." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-slate-100 flex items-center gap-2">
            <Award className="w-5 h-5 text-indigo-400" />
            <span>Koreksi & Penilaian Essay (AI-Assisted)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Daftar lembar jawaban esai siswa yang telah dinilai otomatis oleh AI. Anda dapat menyetujui, merevisi, dan mengunci (finalize) nilai akhir siswa.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
          onClick={fetchEvaluations}
          disabled={isLoading}
        >
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="glass-panel p-12 flex flex-col items-center justify-center gap-3">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-xs text-slate-400">Memuat jawaban esai...</p>
        </div>
      ) : evaluations.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center justify-center gap-3 border-dashed">
          <FileText className="w-12 h-12 text-slate-600" />
          <h3 className="text-sm font-bold text-slate-300">Belum Ada Koreksi Esai</h3>
          <p className="text-xs text-slate-500 max-w-sm">
            Tidak ada lembar jawaban esai siswa yang membutuhkan penilaian atau review saat ini.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto glass-panel p-4">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="py-3 px-4 font-bold">Nama Ujian & Kelas</th>
                <th className="py-3 px-4 font-bold">Siswa</th>
                <th className="py-3 px-4 font-bold text-center">Rekomendasi AI</th>
                <th className="py-3 px-4 font-bold text-center">Status Nilai</th>
                <th className="py-3 px-4 font-bold text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {evaluations.map((item) => (
                <tr key={item.evaluation_id} className="hover:bg-slate-900/40">
                  <td className="py-3.5 px-4">
                    <span className="font-bold text-slate-200 block">{item.exam_title}</span>
                    <span className="text-[10px] text-slate-500 block">Kelas: {item.class_name}</span>
                  </td>
                  <td className="py-3.5 px-4 font-bold text-slate-300">{item.student_name}</td>
                  <td className="py-3.5 px-4 text-center font-bold text-indigo-400">
                    {item.ai_score} / 100
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    {item.grading_status === "FINALIZED" ? (
                      <Badge variant="emerald">
                        <span className="flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Finalized
                        </span>
                      </Badge>
                    ) : (
                      <Badge variant="amber">AI Evaluated</Badge>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <Button
                      variant={item.grading_status === "FINALIZED" ? "outline" : "primary"}
                      size="sm"
                      leftIcon={<Edit2 className="w-3.5 h-3.5" />}
                      onClick={() => handleOpenGradingModal(item)}
                    >
                      {item.grading_status === "FINALIZED" ? "Ubah Nilai" : "Koreksi Nilai"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modal: Review & Finalize Grading ── */}
      <Modal
        isOpen={selectedEval !== null}
        onClose={() => setSelectedEval(null)}
        title="Evaluasi Jawaban Esai Siswa"
        maxWidth="md"
      >
        {selectedEval && (
          <form onSubmit={handleFinalizeGrading} className="space-y-4 max-h-[85vh] overflow-y-auto pr-1">
            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-500 block">Siswa</span>
                <strong className="text-slate-200 block text-sm mt-0.5">{selectedEval.student_name}</strong>
              </div>
              <div>
                <span className="text-slate-500 block">Ujian</span>
                <strong className="text-slate-200 block text-sm mt-0.5">{selectedEval.exam_title}</strong>
              </div>
            </div>

            <div className="space-y-3">
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
                <span className="text-[10px] font-bold text-indigo-400 block uppercase tracking-wider">Pertanyaan/Soal</span>
                <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-line">{selectedEval.question_content}</p>
              </div>

              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
                <span className="text-[10px] font-bold text-amber-400 block uppercase tracking-wider">Jawaban Siswa</span>
                <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-line bg-slate-950 p-3 rounded-lg border border-slate-850">
                  {selectedEval.student_answer || "(Siswa tidak mengisi jawaban / kosong)"}
                </p>
              </div>
            </div>

            <div className="bg-indigo-950/20 border border-indigo-500/20 rounded-xl p-4 space-y-2">
              <span className="text-[10px] font-bold text-indigo-400 flex items-center gap-1.5 uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Analisis & Feedback Otomatis AI</span>
              </span>
              <p className="text-xs text-indigo-300 leading-relaxed">
                {selectedEval.ai_feedback || "Tidak ada feedback khusus dari AI."}
              </p>
              <div className="text-xs font-bold text-slate-200 pt-1">
                Rekomendasi Skor AI: <span className="text-emerald-400">{selectedEval.ai_score} / {selectedEval.max_score || 100}</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 items-end">
              <div className="col-span-1 space-y-1.5">
                <label className="text-xs font-bold text-slate-300">Skor Akhir (0 - {selectedEval.max_score || 100})</label>
                <Input
                  type="number"
                  placeholder={`0-${selectedEval.max_score || 100}`}
                  value={score}
                  onChange={(e) => setScore(e.target.value)}
                  min="0"
                  max={selectedEval.max_score || 100}
                  step="0.5"
                  required
                />
              </div>
              <div className="col-span-2 space-y-1.5">
                <label className="text-xs font-bold text-slate-300">Catatan/Koreksi Guru (Opsional)</label>
                <Input
                  placeholder="Catatan tambahan untuk siswa tentang jawabannya"
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <Button variant="outline" type="button" onClick={() => setSelectedEval(null)}>
                Batal
              </Button>
              <Button
                variant="primary"
                type="submit"
                disabled={isSubmitting}
                isLoading={isSubmitting}
              >
                Kunci Nilai Akhir
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
