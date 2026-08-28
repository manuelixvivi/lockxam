import React, { useRef } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";
import { PlusCircle, FileSpreadsheet, Download } from "lucide-react";

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
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleManualClick = () => {
    onClose();
    onSelectManual();
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && onImportXlsx) {
      e.target.value = "";
      onClose();
      await onImportXlsx(file);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Tambah Data ${entityName}`}
      maxWidth="md"
    >
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
              onClick={handleImportClick}
              className="flex flex-col items-center text-center p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-emerald-500/50 hover:bg-emerald-950/20 transition-all group cursor-pointer"
            >
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-3 group-hover:scale-110 transition-transform">
                <FileSpreadsheet className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-100 group-hover:text-emerald-300 transition-colors">
                Impor via Excel (XLSX)
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                Pilih file .xlsx dari perangkat Anda untuk mengimpor data masal secara langsung.
              </p>
            </button>
          )}
        </div>

        {onDownloadTemplate && (
          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-3 mt-2">
            <div>
              <p className="text-xs font-bold text-slate-200">Format Official Template Excel</p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Gunakan template resmi agar data terbaca dengan sempurna.
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<Download className="w-4 h-4 text-emerald-400" />}
              onClick={onDownloadTemplate}
            >
              Template Excel
            </Button>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx, .xls"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>
    </Modal>
  );
};
