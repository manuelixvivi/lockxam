import React, { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

interface MathTextProps {
  text: string;
  className?: string;
}

export const MathText: React.FC<MathTextProps> = ({ text, className = "" }) => {
  const renderedHtml = useMemo(() => {
    if (!text) return "";

    // Regex matching LaTeX block ($$...$$ or \[...\]) and inline ($...$ or \(...\))
    const regex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\$[\s\S]*?\$|\\\([\s\S]*?\\\))/g;

    const parts = text.split(regex);

    return parts
      .map((part) => {
        if (!part) return "";

        // Block math $$...$$
        if (part.startsWith("$$") && part.endsWith("$$")) {
          const math = part.slice(2, -2).trim();
          try {
            return katex.renderToString(math, { displayMode: true, throwOnError: false });
          } catch {
            return part;
          }
        }
        // Block math \[...\]
        if (part.startsWith("\\[") && part.endsWith("\\]")) {
          const math = part.slice(2, -2).trim();
          try {
            return katex.renderToString(math, { displayMode: true, throwOnError: false });
          } catch {
            return part;
          }
        }

        // Inline math $...$
        if (part.startsWith("$") && part.endsWith("$") && part.length > 2) {
          const math = part.slice(1, -1).trim();
          try {
            return katex.renderToString(math, { displayMode: false, throwOnError: false });
          } catch {
            return part;
          }
        }
        // Inline math \(...\)
        if (part.startsWith("\\(") && part.endsWith("\\)")) {
          const math = part.slice(2, -2).trim();
          try {
            return katex.renderToString(math, { displayMode: false, throwOnError: false });
          } catch {
            return part;
          }
        }

        // Plain text: escape HTML and replace newlines with line breaks
        return part
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/\n/g, "<br/>");
      })
      .join("");
  }, [text]);

  return (
    <span
      className={`katex-wrapper inline-block ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
    />
  );
};
