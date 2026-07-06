import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";

const LANGS = [
  { code: "it", label: "IT" },
  { code: "en", label: "EN" },
];

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const current = (i18n.resolvedLanguage || "it").slice(0, 2);
  return (
    <div className="flex items-center gap-1" data-testid="language-switcher">
      <Languages size={14} className="text-zinc-500 mr-0.5" />
      {LANGS.map((l) => (
        <button key={l.code} data-testid={`lang-${l.code}`} onClick={() => i18n.changeLanguage(l.code)}
          className={`text-xs font-bold px-2 py-1 transition-colors ${current === l.code ? "bg-[#E5FF00] text-black" : "text-zinc-400 hover:text-white"}`}>
          {l.label}
        </button>
      ))}
    </div>
  );
}
