import React, { useState, useEffect } from "react";

interface MultilingualTypingWelcomeProps {
  userName: string;
  className?: string;
}

const WELCOME_PHRASES = [
  { prefix: "Selamat Datang", lang: "Bahasa Indonesia", flag: "🇮🇩" },
  { prefix: "Welcome", lang: "English", flag: "🇬🇧" },
  { prefix: "Horas", lang: "Batak Toba", flag: "🇮🇩" },
  { prefix: "Mejuah-juah", lang: "Batak Karo", flag: "🇮🇩" },
  { prefix: "Aloi", lang: "Simalungun", flag: "🇮🇩" },
  { prefix: "Sugeng Rawuh", lang: "Jawa", flag: "🇮🇩" },
  { prefix: "Wilujeng Sumping", lang: "Sunda", flag: "🇮🇩" },
  { prefix: "Tabik Pun", lang: "Lampung", flag: "🇮🇩" },
  { prefix: "Bienvenue", lang: "Français", flag: "🇫🇷" },
  { prefix: "¡Bienvenido", lang: "Español", flag: "🇪🇸" },
  { prefix: "Willkommen", lang: "Deutsch", flag: "🇩🇪" },
  { prefix: "いらっしゃいませ", lang: "Japanese", flag: "🇯🇵" },
  { prefix: "환영합니다", lang: "Korean", flag: "🇰🇷" },
];

export const MultilingualTypingWelcome: React.FC<MultilingualTypingWelcomeProps> = ({
  userName,
  className = "",
}) => {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [displayedText, setDisplayedText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [typingSpeed, setTypingSpeed] = useState(80);

  const nameToUse = userName || "Pengguna Equigrade";

  useEffect(() => {
    const currentPhraseObj = WELCOME_PHRASES[phraseIndex];
    let fullText = `${currentPhraseObj.prefix}, ${nameToUse}!`;
    if (currentPhraseObj.prefix.startsWith("¡")) {
      fullText = `¡Bienvenido, ${nameToUse}!`;
    }

    const handleTyping = () => {
      if (!isDeleting) {
        // Typing forward
        setDisplayedText(fullText.substring(0, displayedText.length + 1));
        setTypingSpeed(70);

        if (displayedText === fullText) {
          // Finished typing phrase, pause before deleting
          setTimeout(() => setIsDeleting(true), 2200);
        }
      } else {
        // Deleting backward
        setDisplayedText(fullText.substring(0, displayedText.length - 1));
        setTypingSpeed(35);

        if (displayedText === "") {
          setIsDeleting(false);
          setPhraseIndex((prev) => (prev + 1) % WELCOME_PHRASES.length);
        }
      }
    };

    const timer = setTimeout(handleTyping, typingSpeed);
    return () => clearTimeout(timer);
  }, [displayedText, isDeleting, phraseIndex, nameToUse, typingSpeed]);

  return (
    <div className={`space-y-1 ${className}`}>
      <div className="flex items-center gap-2">
        <h2 className="text-2xl sm:text-3xl font-black text-slate-100 min-h-[40px] flex items-center">
          <span className="bg-gradient-to-r from-slate-100 via-indigo-200 to-indigo-400 bg-clip-text text-transparent">
            {displayedText}
          </span>
          <span className="w-0.5 h-7 bg-indigo-400 ml-1 inline-block animate-pulse" />
        </h2>
      </div>
    </div>
  );
};
