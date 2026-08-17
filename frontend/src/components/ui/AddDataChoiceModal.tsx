import React, { useState } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";
import { PlusCircle, FileSpreadsheet, Download, Upload, Loader2 } from "lucide-react";

interface AddDataChoiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  entityName: string; // e.g. "Siswa", "Mata Pelajaran", "Guru", "Kelas", "Soal"
  onSelectManual: () => void;
  onDownloadTemplate?: () => void;
  onImportXlsx?: (file: File) => Promise<void>;
  isLoadingImport?: boolean;
}

export const AddDataChoiceModal: React.FC<AddDataChoiceModalProps> = ({
  isOpen,
  onClose,
  entityName,
  onSelectManual,
  onDownloadTemplate,
  onImportXlsx,
  isLoadingImport = false,
}) => {
  const [step, setStep] = useState<"choice" | "import">("choice");
  const [dragOver, setDragOver] = useState(false);

  const handleClose = () => {
    setStep("choice");
    onClose();
  };

  const handleManualClick = () => {
    handleClose();
    onSelectManual();
  };

  const handleFileSelected = async (file: File) => {
    if (onImportXlsx) {
      await onImportXlsx(file);
      handleClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={step === "choice" ? `Tambah ${entityName}` : `Impor Data ${entityName} via Excel`}
      maxWidth="md"
    >
      {step === "choice" ? (
        <div className="space-y-4 py-2 animate-fade-in">
          <p className="text-xs text-slate-400">
            Pilih metode yang ingin Anda gunakan untuk menambahkan data <strong>{entityName}</strong> baru:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Choice 1: Manual Input */}
            <button
              type="button"
              onClick={handleManualClick}
              className="flex flex-col items-center text-center p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-indigo-500/50 hover:bg-indigo-950/20 transition-all group cursor-pointer"
            >
              <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-3 group-hover:scale-110 transition-transform">
                <PlusCircle className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-100 group-hover:text-indigo-300 transition-colors">
                Input Manual
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                Isi formulir pembuatan data {entityName.toLowerCase()} satu per satu secara langsung.
              </p>
            </button>

            {/* Choice 2: Import via Excel */}
            {onImportXlsx && (
              <button
                type="button"
                onClick={() => setStep("import")}
                className="flex flex-col items-center text-center p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-emerald-500/50 hover:bg-emerald-950/20 transition-all group cursor-pointer"
              >
                <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-3 group-hover:scale-110 transition-transform">
                  <FileSpreadsheet className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-bold text-slate-100 group-hover:text-emerald-300 transition-colors">
                  Impor via Excel (XLSX)
                </h3>
                <p className="text-[11px] text-slate-400 mt-1">
                  Upload file Excel berformat .xlsx untuk menambahkan data masal sekaligus.
                </p>
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-5 py-2 animate-fade-in">
          {/* Step 1: Download Template */}
          {onDownloadTemplate && (
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold text-slate-200">1. Unduh Template Format Excel</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Gunakan format kolom resmi agar data terbaca dengan sempurna.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
                onClick={onDownloadTemplate}
              >
                Unduh Template
              </Button>
            </div>
          )}

          {/* Step 2: Dropzone Upload File */}
          <div className="space-y-2">
            <p className="text-xs font-bold text-slate-200">
              {onDownloadTemplate ? "2." : "1."} Unggah File Excel (.xlsx)
            </p>

            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                if (e.dataTransfer.files?.[0]) {
                  handleFileSelected(e.dataTransfer.files[0]);
                }
              }}
              className={`flex flex-col items-center justify-center p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer ${
                dragOver
                  ? "border-emerald-500 bg-emerald-950/20"
                  : "border-slate-800 hover:border-slate-700 bg-slate-950/40"
              }`}
            >
              {isLoadingImport ? (
                <div className="flex flex-col items-center py-4 space-y-2">
                  <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
                  <p className="text-xs text-slate-300 font-medium">Memproses file Excel…</p>
                </div>
              ) : (
                <>
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-2">
                    <Upload className="w-6 h-6" />
                  </div>
                  <p className="text-xs font-bold text-slate-200">Klik atau Tarik File Excel (.xlsx) ke Sini</p>
                  <p className="text-[11px] text-slate-400 mt-1">Mendukung file ekstensi .xlsx</p>
                  <input
                    type="file"
                    accept=".xlsx, .xls"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) {
                        handleFileSelected(e.target.files[0]);
                      }
                    }}
                  />
                </>
              )}
            </label>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-800">
            <Button variant="ghost" size="sm" onClick={() => setStep("choice")}>
              &larr; Kembali
            </Button>
            <Button variant="ghost" size="sm" onClick={handleClose}>
              Tutup
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
