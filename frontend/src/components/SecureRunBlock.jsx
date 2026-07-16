import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import i18n from "@/i18n";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const isEn = () => i18n.language?.startsWith("en");

const CopyLine = ({ cmd, color, testid }) => {
  const [c, setC] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); } catch { const x = document.createElement("textarea"); x.value = cmd; document.body.appendChild(x); x.select(); document.execCommand("copy"); x.remove(); }
    setC(true); toast.success(i18n.t("desktop.copied")); setTimeout(() => setC(false), 1500);
  };
  return (
    <div className="flex items-stretch gap-2">
      <code className={`flex-1 bg-black border border-[#2A2A35] px-3 py-2.5 text-xs overflow-x-auto whitespace-nowrap ${color || "text-[#00FF66]"}`} data-testid={testid}>{cmd}</code>
      <button onClick={copy} data-testid={`${testid}-copy`} className="shrink-0 flex items-center border border-[#2A2A35] px-3 hover:border-[#E5FF00] transition-colors text-xs">
        {c ? <Check size={14} className="text-[#00FF66]" /> : <Copy size={14} />}
      </button>
    </div>
  );
};

export const SecureRunBlock = ({ token, mode, profile, testid = "secure-run" }) => {
  const en = isEn();
  const tk = token || "IL_TUO_TOKEN";
  const q = profile ? `?t=${tk}&profile=${profile}` : `?t=${tk}`;
  const dl = `irm "${BACKEND}/api/agent/script${q}" -OutFile "$HOME\\Downloads\\forgefps.ps1"`;
  const run = `powershell -ExecutionPolicy Bypass -File "$HOME\\Downloads\\forgefps.ps1" -Token ${tk} -Mode ${mode}`;
  return (
    <div className="space-y-1.5" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-widest text-zinc-500">{en ? "1) Download (does not run)" : "1) Scarica (non esegue)"}</div>
      <CopyLine cmd={dl} testid={`${testid}-dl`} color="text-[#00FF66]" />
      <div className="text-[10px] uppercase tracking-widest text-zinc-500 pt-1">{en ? "2) Run local file" : "2) Esegui il file locale"}</div>
      <CopyLine cmd={run} testid={`${testid}-run`} color="text-[#E5FF00]" />
      <Link to="/app/desktop" className="inline-flex items-center gap-1.5 text-[11px] text-[#00E0FF] hover:underline pt-1">
        <ShieldCheck size={12} /> {en ? "Verify integrity (SHA256) & full guide" : "Verifica integrità (SHA256) e guida completa"}
      </Link>
    </div>
  );
};
