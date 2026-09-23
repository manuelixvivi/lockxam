import { useEffect, useState } from "react";
import { studentExamApi } from "../../api/studentExam";
import { ArrowLeft, ShieldCheck } from "lucide-react";

interface StudentReviewViewProps {
  attemptId: number;
  onNavigate: (path: string) => void;
}

export function StudentReviewView({ attemptId, onNavigate }: StudentReviewViewProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    studentExamApi.getAttemptReview(attemptId)
      .then(setData)
      .catch((err) => {
        console.error("Gagal mengambil review", err);
        alert("Ujian belum selesai dinilai atau Anda tidak memiliki akses.");
        onNavigate("/student/history");
      })
      .finally(() => setLoading(false));
  }, [attemptId, onNavigate]);

  if (loading) return <div className="p-8 text-center text-slate-400 animate-pulse">Memuat hasil koreksi AI...</div>;
  if (!data) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in p-6">
      {/* HEADER */}
      <div className="flex items-center gap-4 border-b border-slate-800 pb-6">
        <button onClick={() => onNavigate("/student/history")} className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-300" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Detail Koreksi Ujian
            <ShieldCheck className="w-6 h-6 text-emerald-400" />
          </h1>
          <p className="text-sm text-slate-400 mt-1">Skor Akhir Anda: <span className="font-bold text-emerald-400 text-lg">{data.final_score}</span> / 100</p>
        </div>
      </div>

      {/* QUESTION LIST */}
      <div className="space-y-8">
        {data.questions.map((q: any, idx: number) => {
          const answer = data.answers[q.id] || {};
          const evalData = data.evaluations[q.id];

          return (
            <div key={q.id} className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
              {/* Indikator AI Confidence */}
              {evalData && (
                <div className={`absolute top-0 right-0 px-4 py-1 rounded-bl-xl text-xs font-bold ${evalData.confidence_level === 'HIGH' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
                  AI Confidence: {evalData.confidence ? `${(evalData.confidence * 100).toFixed(0)}%` : 'N/A'}
                </div>
              )}

              <h3 className="text-lg font-semibold text-slate-200 mb-4 border-b border-slate-800 pb-2">Soal {idx + 1}</h3>
              <div className="text-slate-300 mb-6 bg-slate-950 p-4 rounded-lg" dangerouslySetInnerHTML={{ __html: q.content }} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Jawaban Siswa */}
                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-500 uppercase">Jawaban Anda:</span>
                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-slate-300 min-h-[100px]">
                    {q.type === 'ES' || q.type === 'IS' ? (answer.text_answer || <span className="text-slate-600 italic">Kosong</span>) : (answer.selected_option || <span className="text-slate-600 italic">Kosong</span>)}
                  </div>
                </div>

                {/* Hasil Koreksi & Feedback */}
                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-500 uppercase flex justify-between">
                    <span>Feedback AI:</span>
                    <span className="text-emerald-400">Poin: {evalData ? evalData.score : 0} / {evalData ? evalData.max_score : 0}</span>
                  </span>
                  <div className={`border rounded-lg p-4 min-h-[100px] ${evalData && evalData.score > 0 ? 'bg-emerald-900/10 border-emerald-500/30' : 'bg-red-900/10 border-red-500/30'}`}>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {evalData ? evalData.feedback : <span className="text-slate-500 italic">Menunggu penilaian...</span>}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
