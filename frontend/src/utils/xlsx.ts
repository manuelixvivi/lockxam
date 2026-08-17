import * as XLSX from "xlsx";

/** Export an array of plain objects to an .xlsx file download. */
export function exportToXlsx<T extends Record<string, unknown>>(
  rows: T[],
  filename: string,
  sheetName = "Data"
): void {
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

/** Read an xlsx/xls file uploaded by the user and return rows as plain objects. */
export function readXlsxFile(file: File): Promise<Record<string, string>[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json<Record<string, string>>(ws, {
          defval: "",
        });
        resolve(rows);
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(new Error("Gagal membaca file."));
    reader.readAsArrayBuffer(file);
  });
}

/** Generate a template xlsx with given column headers and optional sample rows. */
export function downloadXlsxTemplate(
  headers: string[],
  sampleRows: Record<string, string>[],
  filename: string,
  sheetName = "Template"
): void {
  const ws = XLSX.utils.json_to_sheet(
    sampleRows.length > 0 ? sampleRows : [Object.fromEntries(headers.map((h) => [h, ""]))],
    { header: headers }
  );
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

/** Generate a multi-sheet template xlsx. */
export function downloadMultiSheetXlsxTemplate(
  sheets: {
    name: string;
    headers: string[];
    samples: Record<string, string>[];
  }[],
  filename: string
): void {
  const wb_new = XLSX.utils.book_new();
  sheets.forEach((sheet) => {
    const ws = XLSX.utils.json_to_sheet(
      sheet.samples.length > 0 ? sheet.samples : [Object.fromEntries(sheet.headers.map((h) => [h, ""]))],
      { header: sheet.headers }
    );
    XLSX.utils.book_append_sheet(wb_new, ws, sheet.name);
  });
  XLSX.writeFile(wb_new, `${filename}.xlsx`);
}

/** Read a multi-sheet xlsx file and return rows grouped by sheet name. */
export function readMultiSheetXlsxFile(file: File): Promise<Record<string, Record<string, string>[]>> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        const result: Record<string, Record<string, string>[]> = {};
        wb.SheetNames.forEach((sheetName) => {
          const ws = wb.Sheets[sheetName];
          result[sheetName] = XLSX.utils.sheet_to_json<Record<string, string>>(ws, {
            defval: "",
          });
        });
        resolve(result);
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = () => reject(new Error("Gagal membaca file."));
    reader.readAsArrayBuffer(file);
  });
}

export interface ExtractedXlsxImage {
  sheetName: string;
  row: number; // 0-indexed row number
  colName: string;
  file: File;
}

/**
 * Method 2: Extract embedded drawings/images pasted directly inside cells of an .xlsx file using JSZip.
 */
export async function extractEmbeddedImagesFromXlsx(file: File): Promise<ExtractedXlsxImage[]> {
  const images: ExtractedXlsxImage[] = [];
  try {
    const JSZip = (await import("jszip")).default;
    const zip = await JSZip.loadAsync(file);

    const drawingRelsFiles = Object.keys(zip.files).filter((path) => path.includes("xl/drawings/_rels/"));
    for (const relPath of drawingRelsFiles) {
      const relsContent = await zip.files[relPath].async("text");
      const drawingPath = relPath.replace("_rels/", "").replace(".rels", "");
      if (!zip.files[drawingPath]) continue;

      const drawingXml = await zip.files[drawingPath].async("text");

      const relMatches = Array.from(relsContent.matchAll(/Id="(rId\d+)"\s+Target="\.\.\/media\/([^"]+)"/g));
      const ridToMedia: Record<string, string> = {};
      relMatches.forEach((m) => {
        ridToMedia[m[1]] = `xl/media/${m[2]}`;
      });

      const parser = new DOMParser();
      const doc = parser.parseFromString(drawingXml, "application/xml");
      const anchors = Array.from(doc.querySelectorAll("twoCellAnchor, oneCellAnchor, cellAnchor"));

      for (const anchor of anchors) {
        const rowElem = anchor.querySelector("from row, row");
        const colElem = anchor.querySelector("from col, col");
        const blipElem = anchor.querySelector("blip");
        if (rowElem && blipElem) {
          const rowIdx = parseInt(rowElem.textContent || "0", 10);
          const colIdx = parseInt(colElem?.textContent || "0", 10);
          const rId = blipElem.getAttribute("r:embed") || blipElem.getAttribute("embed");
          const mediaPath = rId ? ridToMedia[rId] : null;

          if (mediaPath && zip.files[mediaPath]) {
            const blob = await zip.files[mediaPath].async("blob");
            const filename = mediaPath.split("/").pop() || "image.png";
            const imgFile = new File([blob], filename, { type: blob.type || "image/png" });

            images.push({
              sheetName: "Sheet1",
              row: rowIdx,
              colName: colIdx >= 3 ? "Gambar Opsi" : "Gambar Pertanyaan",
              file: imgFile,
            });
          }
        }
      }
    }
  } catch (err) {
    console.warn("Notice: Cell drawings extraction handled:", err);
  }
  return images;
}
