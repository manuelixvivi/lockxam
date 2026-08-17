import React, { useRef, useState } from "react";
import { Download, Upload, FileSpreadsheet, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "./Button";
import { readXlsxFile, downloadXlsxTemplate, exportToXlsx } from "../../utils/xlsx";

export interface ImportResult {
  success: number;
  failed: { row: number; identifier: string; reason: string }[];
}

interface ImportExportBarProps<T> {
  /** Current table data to export */
  exportData: T[];
  /** Column mapping for export: { label, key } */
  exportColumns: { label: string; key: keyof T }[];
  /** Filename prefix for export, e.g. "daftar-guru" */
  exportFilename: string;
  /** Template column headers for import */
  templateHeaders: string[];
  /** Template sample rows */
  templateSamples: Record<string, string>[];
  /** Template filename */
  templateFilename: string;
  /** Called once per parsed row; should call the API and return success/error string */
  onImportRow: (row: Record<string, string>, rowIndex: number) => Promise<string | null>;
  /** Called after import completes */
  onImportDone?: () => void;
  /** Sheet name for export */
  sheetName?: string;
}

export function ImportExportBar<T>({
  exportData,
  exportColumns,
  exportFilename,
  templateHeaders,
  templateSamples,
  templateFilename,
  onImportRow,
  onImportDone,
  sheetName = "Data",
}: ImportExportBarProps<T>) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);

  const handleExport = () => {
    const rows = exportData.map((item) =>
      Object.fromEntries(exportColumns.map(({ label, key }) => [label, String(item[key] ?? "")])) as Record<string, unknown>
    );
    exportToXlsx(rows, exportFilename, sheetName);
  };

  const handleDownloadTemplate = () => {
    downloadXlsxTemplate(templateHeaders, templateSamples, templateFilename, "Template");
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    setIsImporting(true);
    setImportResult(null);
    setProgress(null);

    try {
      const rows = await readXlsxFile(file);
      if (rows.length === 0) {
        setImportResult({ success: 0, failed: [{ row: 0, identifier: "-", reason: "File kosong atau format tidak valid." }] });
        return;
      }

      let successCount = 0;
      const failed: ImportResult["failed"] = [];
      setProgress({ current: 0, total: rows.length });

      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        const identifier = Object.values(row)[0] as string || `Baris ${i + 2}`;
        const errorMsg = await onImportRow(row, i);
        if (errorMsg) {
          failed.push({ row: i + 2, identifier, reason: errorMsg });
        } else {
          successCount++;
        }
        setProgress({ current: i + 1, total: rows.length });
      }

      setImportResult({ success: successCount, failed });
      onImportDone?.();
    } catch (err: any) {
      setImportResult({
        success: 0,
        failed: [{ row: 0, identifier: "-", reason: err?.message || "Gagal memproses file." }],
      });
    } finally {
      setIsImporting(false);
      setProgress(null);
    }
  };

  return (
    <div className="space-y-3">
      {/* Action buttons row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Export */}
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Download className="w-3.5 h-3.5 text-emerald-400" />}
          onClick={handleExport}
          disabled={exportData.length === 0}
          title="Ekspor data ke file Excel"
        >
          <span className="hidden sm:inline">Ekspor XLSX</span>
          <span className="sm:hidden">Ekspor</span>
        </Button>

        {/* Download template */}
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" />}
          onClick={handleDownloadTemplate}
          title="Unduh template Excel untuk impor massal"
        >
          <span className="hidden sm:inline">Unduh Template</span>
          <span className="sm:hidden">Template</span>
        </Button>

        {/* Import */}
        <Button
          variant="ghost"
          size="sm"
          leftIcon={
            isImporting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
            ) : (
              <Upload className="w-3.5 h-3.5 text-amber-400" />
            )
          }
          onClick={() => fileInputRef.current?.click()}
          isLoading={isImporting}
          title="Impor data dari file Excel"
        >
          <span className="hidden sm:inline">Impor XLSX</span>
          <span className="sm:hidden">Impor</span>
        </Button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Progress bar */}
      {progress && (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-amber-950/20 border border-amber-500/30">
          <Loader2 className="w-4 h-4 animate-spin text-amber-400 shrink-0" />
          <div className="flex-1">
            <div className="flex justify-between text-xs text-amber-300 font-medium mb-1">
              <span>Mengimpor data…</span>
              <span>{progress.current}/{progress.total}</span>
            </div>
            <div className="h-1.5 rounded-full bg-amber-900/50">
              <div
                className="h-1.5 rounded-full bg-amber-400 transition-all"
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Result banner */}
      {importResult && (
        <div className={`p-3 rounded-xl border text-xs space-y-2 ${
          importResult.failed.length === 0
            ? "bg-emerald-950/20 border-emerald-500/30"
            : importResult.success === 0
            ? "bg-red-950/20 border-red-500/30"
            : "bg-amber-950/20 border-amber-500/30"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold">
              {importResult.failed.length === 0 ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertCircle className="w-4 h-4 text-amber-400" />
              )}
              <span className={importResult.failed.length === 0 ? "text-emerald-300" : "text-amber-300"}>
                Impor selesai: {importResult.success} berhasil
                {importResult.failed.length > 0 && `, ${importResult.failed.length} gagal`}
              </span>
            </div>
            <button onClick={() => setImportResult(null)} className="text-slate-500 hover:text-slate-300">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {importResult.failed.length > 0 && (
            <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
              {importResult.failed.map((f, i) => (
                <div key={i} className="flex items-start gap-2 text-red-300">
                  <AlertCircle className="w-3 h-3 mt-0.5 shrink-0 text-red-400" />
                  <span>
                    <span className="font-mono font-semibold">Baris {f.row}</span>
                    {f.identifier && f.identifier !== "-" && ` (${f.identifier})`}: {f.reason}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
