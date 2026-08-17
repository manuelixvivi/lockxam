import { useState, useEffect } from "react";
import {
  Award,
  BookOpen,
  RefreshCw,
  Search,
  FileSpreadsheet,
  FileText,
  Eye,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useToast } from "../../context/ToastContext";
import { apiClient } from "../../api/client";

export function TeacherExamHistoryView() {
  const { showToast } = useToast();
  const [groupedPackages, setGroupedPackages] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // BAP & Student Answers Modal States
  const [selectedSchedule, setSelectedSchedule] = useState<any | null>(null);
  const [isBapModalOpen, setIsBapModalOpen] = useState(false);
  const [bapDoc, setBapDoc] = useState<any | null>(null);
  const [isLoadingBap, setIsLoadingBap] = useState(false);

  const [isAnswersModalOpen, setIsAnswersModalOpen] = useState(false);
  const [studentAnswers, setStudentAnswers] = useState<any[]>([]);
  const [isLoadingAnswers, setIsLoadingAnswers] = useState(false);
  const [selectedStudentAnswer, setSelectedStudentAnswer] = useState<any | null>(null);

  const fetchHistory = async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.get<{ grouped_packages: any[] }>("/api/v1/teacher/dashboard/exam-history");
      setGroupedPackages(res.grouped_packages || []);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Riwayat Ujian",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleOpenBap = async (sch: any) => {
    setSelectedSchedule(sch);
    setIsBapModalOpen(true);
    setIsLoadingBap(true);
    try {
      const doc = await apiClient.get(`/api/v1/proctor/assignments/${sch.schedule_id}/bau`);
      setBapDoc(doc);
    } catch (err: any) {
      setBapDoc(null);
    } finally {
      setIsLoadingBap(false);
    }
  };

  const handleOpenStudentAnswers = async (sch: any) => {
    setSelectedSchedule(sch);
    setIsAnswersModalOpen(true);
    setIsLoadingAnswers(true);
    try {
      const res = await apiClient.get<{ students: any[] }>(
        `/api/v1/teacher/dashboard/exam-history/${sch.schedule_id}/student-answers`
      );
      setStudentAnswers(res.students || []);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Jawaban Siswa",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoadingAnswers(false);
    }
  };

  const formatDateTime = (dtStr: string) => {
    if (!dtStr) return "-";
    try {
      return new Date(dtStr).toLocaleString("id-ID", {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dtStr;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Banner */}
      <div className="glass-panel p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="indigo">TEACHER PORTAL</Badge>
            <Badge variant="emerald">RIWAYAT BAP & JAWABAN SISWA</Badge>
          </div>
          <h1 className="text-xl font-bold text-slate-100">Riwayat Ujian & Hasil Berita Acara (BAP)</h1>
          <p className="text-xs text-slate-400 mt-1">
            Daftar ujian selesai dikelompokkan berdasarkan Nama Paket Jadwal Ujian Admin Sekolah untuk mata pelajaran & kelas yang Anda ampu.
          </p>
        </div>
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />} onClick={fetchHistory}>
          Refresh Data
        </Button>
      </div>

      {/* Header Search */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
          <Award className="w-4 h-4 text-emerald-400" />
          Paket Ujian Selesai ({groupedPackages.length} Kelompok Paket)
        </h3>

        <div className="w-full sm:w-64">
          <Input placeholder="Cari paket atau mapel..." leftIcon={<Search className="w-4 h-4 text-slate-400" />} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
      </div>

      {/* Grouped Packages List */}
      {isLoading ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center gap-3"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" /><p className="text-xs text-slate-400">Memuat riwayat ujian...</p></div>
      ) : groupedPackages.length === 0 ? (
        <div className="glass-panel p-12 text-center flex flex-col items-center gap-3 border-dashed">
          <BookOpen className="w-12 h-12 text-slate-600" />
          <h3 className="text-sm font-bold text-slate-300">Belum Ada Riwayat Ujian Selesai</h3>
          <p className="text-xs text-slate-500 max-w-sm">Belum ada sesi ujian selesai untuk mata pelajaran &amp; kelas yang Anda ampu.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {groupedPackages.map((pkg, idx) => (
            <div key={idx} className="space-y-4">
              {/* Package Heading */}
              <div className="flex items-center gap-3 border-b border-slate-800 pb-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold text-xs">
                  #{idx + 1}
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                    {pkg.package_title}
                    <Badge variant="indigo">{pkg.schedules.length} Sesi Ujian</Badge>
                  </h2>
                  <p className="text-[11px] text-slate-400">Paket Jadwal Resmi Admin Sekolah</p>
                </div>
              </div>

              {/* Schedules Grid under Package */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {pkg.schedules.map((sch: any) => (
                  <div key={sch.schedule_id} className="glass-panel p-6 flex flex-col justify-between gap-5 border border-slate-800 hover:border-slate-700 transition-all">
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-bold text-slate-100 text-base">{sch.title}</h3>
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <Badge variant="indigo">{sch.subject_name}</Badge>
                            <Badge variant="emerald">{sch.class_name}</Badge>
                          </div>
                        </div>
                        <Badge variant="emerald">SELESAI</Badge>
                      </div>

                      <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-850 text-xs space-y-1.5 text-slate-400">
                        <div className="flex justify-between items-center"><span>Peserta Selesai:</span><span className="font-bold text-emerald-400">{sch.submitted_students} / {sch.total_students} Siswa</span></div>
                        <div className="flex justify-between items-center"><span>Rata-Rata Nilai:</span><span className="font-bold text-amber-300">{sch.average_score !== null ? `${sch.average_score} / 100` : "-"}</span></div>
                        <div className="flex justify-between items-center pt-1 border-t border-slate-800"><span>Waktu Selesai:</span><span className="font-semibold text-slate-200">{formatDateTime(sch.end_time)}</span></div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="outline" size="sm" leftIcon={<FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />} onClick={() => handleOpenBap(sch)}>
                        Dokumen BAP
                      </Button>
                      <Button variant="primary" size="sm" leftIcon={<FileText className="w-3.5 h-3.5" />} onClick={() => handleOpenStudentAnswers(sch)}>
                        Jawaban Siswa
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal BAP Document */}
      <Modal isOpen={isBapModalOpen} onClose={() => setIsBapModalOpen(false)} title={`Dokumen BAP: ${selectedSchedule?.title || ""}`} maxWidth="md">
        <div className="space-y-4 text-xs">
          {isLoadingBap ? (
            <div className="p-8 text-center"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto" /><p className="text-slate-400 mt-2">Memuat BAP...</p></div>
          ) : bapDoc ? (
            <>
              <div className="p-4 bg-slate-900 rounded-xl border border-slate-800 space-y-2">
                <div className="flex justify-between"><span className="text-slate-400">Status Berita Acara:</span><Badge variant="emerald">{bapDoc.status || "SUBMITTED"}</Badge></div>
                <div className="flex justify-between"><span className="text-slate-400">Pengawas:</span><span className="text-slate-200 font-bold">{bapDoc.proctor_name || "Guru Pengawas"}</span></div>
              </div>
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-850">
                <span className="text-slate-400 font-bold block mb-1">Catatan Insiden & Pelanggaran (Auto BAP):</span>
                <p className="text-slate-200 font-mono text-[11px] whitespace-pre-wrap">{bapDoc.proctor_notes || "Tidak ada insiden khusus tercatat."}</p>
              </div>
            </>
          ) : (
            <p className="text-slate-400 text-center">Dokumen Berita Acara belum disubmit oleh pengawas.</p>
          )}
          <div className="flex justify-end pt-2"><Button variant="outline" onClick={() => setIsBapModalOpen(false)}>Tutup</Button></div>
        </div>
      </Modal>

      {/* Modal Jawaban Siswa */}
      <Modal isOpen={isAnswersModalOpen} onClose={() => setIsAnswersModalOpen(false)} title={`Hasil Jawaban Siswa: ${selectedSchedule?.title || ""}`} maxWidth="lg">
        <div className="space-y-4 text-xs">
          {isLoadingAnswers ? (
            <div className="p-8 text-center"><RefreshCw className="w-8 h-8 text-indigo-500 animate-spin mx-auto" /><p className="text-slate-400 mt-2">Memuat jawaban siswa...</p></div>
          ) : (
            <div className="space-y-3">
              <div className="overflow-x-auto max-h-96">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400">
                      <th className="py-2.5 px-3 font-bold">Nama Siswa</th>
                      <th className="py-2.5 px-3 font-bold text-center">Status</th>
                      <th className="py-2.5 px-3 font-bold text-center">Nilai Akhir</th>
                      <th className="py-2.5 px-3 font-bold text-center">Total Dijawab</th>
                      <th className="py-2.5 px-3 font-bold text-right">Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-850">
                    {studentAnswers.map((s) => (
                      <tr key={s.student_id} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3">
                          <div className="font-bold text-slate-200">{s.student_name}</div>
                          <span className="text-[10px] text-slate-500">{s.nisn ? `NISN: ${s.nisn}` : s.student_username}</span>
                        </td>
                        <td className="py-2.5 px-3 text-center"><Badge variant="emerald">{s.status}</Badge></td>
                        <td className="py-2.5 px-3 text-center font-bold text-emerald-400">{s.final_score !== null ? `${s.final_score} / 100` : "-"}</td>
                        <td className="py-2.5 px-3 text-center text-slate-300 font-mono">{s.answers_count} Soal</td>
                        <td className="py-2.5 px-3 text-right">
                          <Button variant="ghost" size="sm" leftIcon={<Eye className="w-3.5 h-3.5 text-indigo-400" />} onClick={() => setSelectedStudentAnswer(s)}>
                            Lihat
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selectedStudentAnswer && (
                <div className="p-4 bg-slate-900/80 rounded-2xl border border-indigo-500/30 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <h4 className="font-bold text-indigo-300">Detail Lembar Jawaban: {selectedStudentAnswer.student_name}</h4>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedStudentAnswer(null)}>Tutup Rincian</Button>
                  </div>
                  <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                    {selectedStudentAnswer.answers.map((ans: any, i: number) => (
                      <div key={i} className="p-2.5 bg-slate-950 rounded-xl border border-slate-850 flex justify-between items-center text-[11px]">
                        <div>
                          <span className="text-slate-400 font-semibold block">Soal #{ans.question_id}:</span>
                          <p className="text-slate-200">{ans.selected_option ? `Jawaban PG: ${ans.selected_option}` : ans.text_answer || "Tidak dijawab"}</p>
                        </div>
                        <Badge variant={ans.is_correct ? "emerald" : "slate"}>Skor: {ans.score_earned ?? (ans.is_correct ? "Benar" : "Salah")}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <div className="flex justify-end pt-2"><Button variant="outline" onClick={() => setIsAnswersModalOpen(false)}>Tutup</Button></div>
        </div>
      </Modal>
    </div>
  );
}
