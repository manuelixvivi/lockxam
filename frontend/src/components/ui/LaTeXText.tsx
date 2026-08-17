import React, { useMemo, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { Modal } from "./Modal";

interface LaTeXTextProps {
  content: string | null | undefined;
  className?: string;
  inline?: boolean;
}

export const LaTeXText: React.FC<LaTeXTextProps> = ({ content, className = "", inline = false }) => {
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);

  const renderedHtml = useMemo(() => {
    if (!content) return "";
    let text = String(content);

    // Convert markdown image syntax ![alt](url) to styled img tags
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, src) => {
      const escapedSrc = src.replace(/"/g, "&quot;");
      const escapedAlt = (alt || "Gambar Soal").replace(/"/g, "&quot;");
      return `<img src="${escapedSrc}" alt="${escapedAlt}" class="q-image max-w-full max-h-72 object-contain rounded-xl border border-slate-700/80 my-2 cursor-zoom-in hover:brightness-110 transition-all inline-block" data-zoom-src="${escapedSrc}" />`;
    });

    // Regex to find math delimiters: $$...$$, $...$, \[...\], \(...\)
    const mathRegex = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^\$\n]+\$|\\\(.+?\\\))/g;

    const parts = text.split(mathRegex);

    return parts
      .map((part) => {
        if (!part) return "";

        // Check if this part is display math $$...$$ or \[...\]
        if ((part.startsWith("$$") && part.endsWith("$$")) || (part.startsWith("\\[") && part.endsWith("\\]"))) {
          const rawMath = part.slice(2, -2);
          try {
            return katex.renderToString(rawMath.trim(), { displayMode: true, throwOnError: false });
          } catch {
            return part;
          }
        }

        // Check if this part is inline math $...$ or \(...\)
        if ((part.startsWith("$") && part.endsWith("$")) || (part.startsWith("\\(") && part.endsWith("\\)"))) {
          const rawMath = part.startsWith("$") ? part.slice(1, -1) : part.slice(2, -2);
          try {
            return katex.renderToString(rawMath.trim(), { displayMode: false, throwOnError: false });
          } catch {
            return part;
          }
        }

        // Check if raw LaTeX math commands exist without delimiters
        if (/\\(frac|sqrt|sum|int|lim|alpha|beta|theta|pi|cdot|pm|infty|times|div|vec)|[\^_]/.test(part) && !part.includes("<img")) {
          try {
            return katex.renderToString(part.trim(), { displayMode: false, throwOnError: false });
          } catch {
            return part;
          }
        }

        // Standard plain text or HTML
        return part;
      })
      .join("");
  }, [content]);

  if (!content) return null;

  const Component = inline ? "span" : "div";

  const handleContainerClick = (e: React.MouseEvent<HTMLElement>) => {
    const target = e.target as HTMLElement;
    if (target && target.tagName === "IMG") {
      const zoomSrc = target.getAttribute("data-zoom-src") || (target as HTMLImageElement).src;
      if (zoomSrc) {
        e.stopPropagation();
        setZoomedImage(zoomSrc);
      }
    }
  };

  return (
    <>
      <Component
        className={`katex-wrapper ${className}`}
        onClick={handleContainerClick}
        dangerouslySetInnerHTML={{ __html: renderedHtml }}
      />

      {/* Image Zoom Lightbox Modal */}
      <Modal
        isOpen={Boolean(zoomedImage)}
        onClose={() => setZoomedImage(null)}
        title="Detail Gambar Soal"
        maxWidth="lg"
      >
        {zoomedImage && (
          <div className="space-y-4 text-center p-2">
            <div className="max-h-[75vh] overflow-auto flex items-center justify-center bg-slate-950 p-2 rounded-2xl border border-slate-800">
              <img
                src={zoomedImage}
                alt="Zoomed Question Detail"
                className="max-w-full h-auto object-contain rounded-xl"
              />
            </div>
            <p className="text-xs text-slate-400">
              Klik di luar gambar atau tombol di atas untuk menutup tampilan perbesaran.
            </p>
          </div>
        )}
      </Modal>
    </>
  );
};
