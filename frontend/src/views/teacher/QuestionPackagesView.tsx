import React, { useState, useEffect } from "react";
import {
  FolderOpen,
  Plus,
  Trash2,
  Eye,
  RefreshCw,
  FolderDot,
  Search,
  AlertCircle,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Modal } from "../../components/ui/Modal";
import { MessageBox } from "../../components/ui/MessageBox";
import { useToast } from "../../context/ToastContext";
import { useAuth } from "../../context/AuthContext";
import { teacherContentApi } from "../../api/teacherContent";
import type { QuestionPackage } from "../../api/teacherContent";
import { getTeacherAssignedSubjectOptions } from "../../utils/subjects";
import { getGradeOptionsForSchool } from "../../utils/gradeLevels";

interface QuestionPackagesViewProps {
  onNavigate?: (href: string) => void;
  onSelectPackage?: (id: number) => void;
}

export function QuestionPackagesView({ onNavigate, onSelectPackage }: QuestionPackagesViewProps) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [packages, setPackages] = useState<QuestionPackage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterSubject, setFilterSubject] = useState("");

  const gradeOptions = React.useMemo(() => {
    return getGradeOptionsForSchool(user?.school_level_code);
  }, [user?.school_level_code]);
  const defaultGrade = gradeOptions[0]?.value || "VII";

  // Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [subject, setSubject] = useState("");

  // Targets
  const [targetPG, setTargetPG] = useState("10");
  const [targetIS, setTargetIS] = useState("5");
  const [targetES, setTargetES] = useState("2");

  const [isCreating, setIsCreating] = useState(false);

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState<number>(25);

  // Get subjects strictly assigned to current teacher
  const [assignedSubjectsList, setAssignedSubjectsList] = useState<string[]>(user?.subjects_taught || []);

  useEffect(() => {
    if (user?.subjects_taught && user.subjects_taught.length > 0) {
      setAssignedSubjectsList((prev) => Array.from(new Set([...prev, ...(user.subjects_taught || [])])));
    }
    teacherContentApi
      .getAssignedSubjects()
      .then((subs) => {
        if (Array.isArray(subs) && subs.length > 0) {
          setAssignedSubjectsList((prev) => Array.from(new Set([...prev, ...subs])));
        }
      })
      .catch(() => {
        // Fallback to user?.subjects_taught
      });
  }, [user?.subjects_taught]);

  const assignedSubjectOptions = getTeacherAssignedSubjectOptions(assignedSubjectsList);
  const hasAssignedSubjects = assignedSubjectsList.length > 0;

  // Set default subject and grade level when opening or mounting
  useEffect(() => {
    if (!subject && assignedSubjectsList.length > 0) {
      setSubject(assignedSubjectsList[0]);
    }
    if (!classLevel || classLevel === "X") {
      setClassLevel(defaultGrade);
    }
  }, [assignedSubjectsList, defaultGrade]);

  const fetchPackages = async () => {
    setIsLoading(true);
    try {
      const skip = (currentPage - 1) * pageSize;
      const data = await teacherContentApi.listPackages(
        pageSize,
        skip,
        searchQuery.trim() || undefined
      );
      setPackages(data);
    } catch (err: any) {
      showToast({
        type: "error",
        title: "Gagal Memuat Paket Soal",
        message: err?.message || "Terjadi kesalahan.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPackages();
  }, [currentPage, pageSize, searchQuery]);

  const handleOpenAddModal = () => {
    setName("");
    setClassLevel(defaultGrade);
    setSubject(assignedSubjectsList.length > 0 ? assignedSubjectsList[0] : "");
    setTargetPG("10");
    setTargetIS("5");
    setTargetES("2");
    setIsAddModalOpen(true);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Nama paket soal wajib diisi." });
      return;
    }

    if (!subject) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Mata pelajaran wajib dipilih." });
      return;
    }

    const pg = parseInt(targetPG, 10) || 0;
    const is = parseInt(targetIS, 10) || 0;
    const es = parseInt(targetES, 10) || 0;

    if (pg + is + es === 0) {
      showToast({ type: "warning", title: "Validasi Gagal", message: "Target jumlah soal minimal harus 1 pada salah satu jenis soal." });
      return;
    }

    const targetCounts: Record<string, number> = {};
    if (pg > 0) targetCounts["PG"] = pg;
    if (is > 0) targetCounts["IS"] = is;
    if (es > 0) targetCounts["ES"] = es;

    setIsCreating(true);
    try {
      const created = await teacherContentApi.createPackage({
        name: name.trim(),
        class_level: classLevel,
        subject,
        target_counts: targetCounts,
      });
      showToast({ type: "success", title: "Paket soal baru berhasil dibuat." });
      setIsAddModalOpen(false);
      setName("");

      // Navigate or select details
      if (onSelectPackage) {
        onSelectPackage(created.id);
      } else if (onNavigate) {
        onNavigate(`/teacher/packages/${created.id}`);
      } else {
        fetchPackages();
      }
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal membuat paket soal", message: err?.message });
    } finally {
      setIsCreating(false);
    }
  };

  // Delete confirm state
  const [deletingPkg, setDeletingPkg] = useState<{ id: number; name: string } | null>(null);
  const [isDeletingPkg, setIsDeletingPkg] = useState(false);

  const handleDelete = (id: number, pkgName: string) => {
    setDeletingPkg({ id, name: pkgName });
  };

  const handleConfirmDeletePkg = async () => {
    if (!deletingPkg) return;
    setIsDeletingPkg(true);
    try {
      await teacherContentApi.deletePackage(deletingPkg.id);
      showToast({ type: "success", title: "Paket soal berhasil dihapus." });
      setDeletingPkg(null);
      fetchPackages();
    } catch (err: any) {
      showToast({ type: "error", title: "Gagal menghapus paket soal", message: err?.message });
    } finally {
      setIsDeletingPkg(false);
    }
  };

  // Distinct subjects in created packages for filter
  const distinctPackageSubjects = Array.from(
    new Set([...assignedSubjectsList, ...packages.map((p) => p.subject).filter((s): s is string => Boolean(s))])
  );

  const filtered = packages.filter((p) => {
    const matchQuery =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.class_level.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.subject && p.subject.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchSubject = filterSubject ? p.subject === filterSubject : true;
    return matchQuery && matchSubject;
  });

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <FolderOpen className="w-6 h-6 text-indigo-400" />
            Paket Soal Ujian (Question Packages)
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Buat dan susun kumpulan butir soal menjadi satu paket soal ujian resmi berdasarkan mata pelajaran yang Anda ampu.
          </p>
        </div>
        <Button
          variant="primary"
          size="md"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={handleOpenAddModal}
        >
          Buat Paket Soal
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="flex items-center gap-2 flex-1 w-full md:max-w-md">
          <div className="flex-1">
            <Input
              placeholder="Cari nama paket atau mata pelajaran..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>
          <Button
            variant="ghost"
            size="md"
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />}
            onClick={fetchPackages}
            isLoading={isLoading}
            className="shrink-0"
          >
            Refresh
          </Button>
        </div>

        {distinctPackageSubjects.length > 0 && (
          <div className="flex gap-2 w-full md:w-auto flex-wrap">
            <div className="w-48">
              <Select
                options={[
                  { value: "", label: "Semua Mata Pelajaran" },
                  ...distinctPackageSubjects.map((s) => ({ value: s, label: s })),
                ]}
                value={filterSubject}
                onChange={(e) => setFilterSubject(e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      {/* Grid of Packages */}
      <div className="glass-panel p-6">
        <h3 className="font-semibold text-slate-300 flex items-center gap-2 text-sm mb-4 border-b border-slate-800 pb-3">
          <FolderDot className="w-4 h-4 text-indigo-400" />
          <span>Daftar Paket Soal ({filtered.length})</span>
        </h3>

        {isLoading ? (
          <p className="text-center text-xs text-slate-500 py-10">Memuat paket soal...</p>
        ) : filtered.length === 0 ? (
          <p className="text-center text-xs text-slate-500 py-10">
            {searchQuery || filterSubject
              ? `Tidak ada paket soal dengan kriteria yang dipilih.`
              : "Belum ada paket soal dibuat. Klik 'Buat Paket Soal' untuk membuat pertama kali."}
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((item) => {
              const totalTarget = Object.values(item.target_counts).reduce((a, b) => a + b, 0);
              return (
                <div
                  key={item.id}
                  className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/80 hover:border-indigo-500/30 transition-all duration-300 flex flex-col justify-between group space-y-4 shadow-lg hover:shadow-indigo-500/5 relative overflow-hidden"
                >
                  <div className="space-y-2.5">
                    <div className="flex justify-between items-start flex-wrap gap-2">
                      <div className="flex gap-1.5 flex-wrap">
                        <Badge variant="indigo" size="sm">
                          Kelas {item.class_level}
                        </Badge>
                        {item.subject && (
                          <Badge variant="emerald" size="sm">
                            {item.subject}
                          </Badge>
                        )}
                      </div>
                      {item.status === "READY" ? (
                        <Badge variant="emerald" size="sm">
                          ● READY
                        </Badge>
                      ) : (
                        <Badge variant="amber" size="sm">
                          ⚠️ INCOMPLETE
                        </Badge>
                      )}
                    </div>

                    <h4 className="font-black text-slate-100 text-base leading-snug group-hover:text-indigo-300 transition-colors break-words pt-1.5">
                      {item.name}
                    </h4>

                    {/* Question type stats */}
                    <div className="grid grid-cols-3 gap-2 bg-slate-950/40 p-2.5 rounded-xl border border-slate-900 text-[10px] text-slate-400 text-center font-mono">
                      <div>
                        <span className="text-emerald-400 block font-bold text-xs">{item.target_counts.PG || 0}</span>
                        <span>Pilihan Ganda</span>
                      </div>
                      <div>
                        <span className="text-indigo-400 block font-bold text-xs">{item.target_counts.IS || 0}</span>
                        <span>Isian</span>
                      </div>
                      <div>
                        <span className="text-amber-400 block font-bold text-xs">{item.target_counts.ES || 0}</span>
                        <span>Essay</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-850">
                    <span className="text-[10px] text-slate-500 font-mono">
                      Total: {totalTarget} Soal
                    </span>
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Eye className="w-3.5 h-3.5" />}
                        onClick={() => {
                          if (onSelectPackage) onSelectPackage(item.id);
                          else if (onNavigate) onNavigate(`/teacher/packages/${item.id}`);
                        }}
                      >
                        Detail & Susun
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        leftIcon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                        onClick={() => handleDelete(item.id, item.name)}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination Bar */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-800 text-xs text-slate-400">
          <div>
            Menampilkan halaman <span className="font-semibold text-slate-200">{currentPage}</span> (25 paket per halaman)
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={currentPage <= 1 || isLoading}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              Sebelumnya
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={packages.length < pageSize || isLoading}
              onClick={() => setCurrentPage((p) => p + 1)}
            >
              Selanjutnya
            </Button>
          </div>
        </div>
      </div>

      {/* Add Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Buat Paket Soal Ujian"
        maxWidth="md"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          {!hasAssignedSubjects && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/40 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-200">
                <span className="font-bold block mb-0.5">Belum Ada Mata Pelajaran yang Di-Assign</span>
                Akun guru Anda belum memiliki mata pelajaran ampu yang di-assign oleh Admin Sekolah. Silakan hubungi Admin Sekolah untuk menambahkan mata pelajaran yang Anda ampu.
              </div>
            </div>
          )}

          <Input
            label="Nama Paket Soal (Wajib)"
            placeholder="Contoh: Penilaian Akhir Matematika Peminatan X"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Tingkat Kelas"
              options={getGradeOptionsForSchool(user?.school_level_code)}
              value={classLevel}
              onChange={(e) => setClassLevel(e.target.value)}
              required
            />
            <Select
              label="Mata Pelajaran (Subject)"
              placeholder={hasAssignedSubjects ? "-- Pilih Mata Pelajaran --" : "Belum ada mapel di-assign"}
              options={assignedSubjectOptions}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              disabled={!hasAssignedSubjects}
              required
            />
          </div>

          {/* Question Targets counts inputs */}
          <div className="space-y-2 bg-slate-950/40 p-4 rounded-xl border border-slate-900">
            <span className="text-xs font-bold text-slate-300 block mb-1">
              Target Jumlah Soal (Kuantitas Target)
            </span>
            <p className="text-[10px] text-slate-500 mb-3">
              Masukkan target kuantitas butir soal yang harus dipenuhi agar paket ujian ini berstatus READY.
            </p>

            <div className="grid grid-cols-3 gap-3">
              <Input
                label="Pilihan Ganda (PG)"
                type="number"
                min="0"
                value={targetPG}
                onChange={(e) => setTargetPG(e.target.value)}
                required
              />
              <Input
                label="Isian Singkat (IS)"
                type="number"
                min="0"
                value={targetIS}
                onChange={(e) => setTargetIS(e.target.value)}
                required
              />
              <Input
                label="Essay (ES)"
                type="number"
                min="0"
                value={targetES}
                onChange={(e) => setTargetES(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsAddModalOpen(false)}
            >
              Batal
            </Button>
            <Button
              type="submit"
              variant="primary"
              leftIcon={<Plus className="w-4 h-4" />}
              isLoading={isCreating}
              disabled={!hasAssignedSubjects}
            >
              Buat Paket
            </Button>
          </div>
        </form>
      </Modal>

      {/* ── Custom Confirmation MessageBox: Delete Package ── */}
      <MessageBox
        isOpen={deletingPkg !== null}
        onClose={() => setDeletingPkg(null)}
        type="warning"
        title="Hapus Paket Soal"
        message={
          <div>
            Apakah Anda yakin ingin menghapus paket soal <strong>"{deletingPkg?.name}"</strong>?
            <p className="text-[11px] text-slate-400 mt-1">
              Soal-soal di dalamnya tidak akan terhapus dari Bank Soal, tetapi hubungan paket soal ini akan dihapus permanen.
            </p>
          </div>
        }
        confirmText="Hapus Paket"
        cancelText="Batal"
        onConfirm={handleConfirmDeletePkg}
        isLoading={isDeletingPkg}
        confirmVariant="danger"
      />
    </div>
  );
}
