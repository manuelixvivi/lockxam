/**
 * Centralized secure-context aware clipboard utility for Equigrade.
 * Fallbacks to document.execCommand when navigator.clipboard is unavailable (e.g. insecure contexts over HTTP).
 */
export const copyToClipboard = async (text: string): Promise<boolean> => {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Fail silently without logging sensitive context
    }
  }

  // Fallback: temporary invisible textarea selection
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed"; // Keep out of document flow
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.width = "2em";
  textarea.style.height = "2em";
  textarea.style.padding = "0";
  textarea.style.border = "none";
  textarea.style.outline = "none";
  textarea.style.boxShadow = "none";
  textarea.style.background = "transparent";
  textarea.style.opacity = "0";
  
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  
  let success = false;
  try {
    success = document.execCommand("copy");
  } catch (err) {
    // Fail silently without logging sensitive context
  }
  
  document.body.removeChild(textarea);
  return success;
};
