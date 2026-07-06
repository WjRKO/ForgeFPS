import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";

const LANGS = [
  { code: "it", label: "IT", flag: "🇮🇹" },
  { code: "en", label: "EN", flag: "🇬🇧" },
];

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = (i18n.resolvedLanguage || "it").slice(0, 2);
  return (
    <div className="flex items-center gap-1" data-testid="language-switcher">
      <Languages size={14} className="text-zinc-500 mr-0.5" />
      {LANGS.map((l) => (
        <button key={l.code} data-testid={`lang-${l.code}`} onClick={() => i18n.changeLanguage(l.code)}
          title={l.code === "it" ? "Italiano" : "English"}
          className={`flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-sm transition-all duration-200 hover:-translate-y-0.5 ${current === l.code ? "bg-[#E5FF00] text-black shadow-[0_2px_10px_rgba(229,255,0,0.35)]" : "text-zinc-400 hover:text-white"}`}>
          <span className={`text-sm leading-none transition-transform duration-200 ${current === l.code ? "" : "grayscale opacity-70"}`}>{l.flag}</span>
          {l.label}
        </button>
      ))}
    </div>
  );
}
