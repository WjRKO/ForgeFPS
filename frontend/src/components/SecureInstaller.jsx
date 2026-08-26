import { Download, ShieldCheck, FileCheck2, Lock, RefreshCw } from "lucide-react";
import { useLang } from "@/components/MarketingChrome";
import { AGENT_EXE_URL, AGENT_EXE_SHA256, AGENT_EXE_VERSION } from "@/config/agent";
import { HUDCard } from "@/components/hud";

const COPY = {
  it: {
    eyebrow: "// installer sicuro",
    title: "Installer verificabile",
    sub: "Niente comandi remoti. Scarichi un installer, lo verifichi e lo esegui tu.",
    version: "v0.4.2 · Windows 10/11 · x64",
    download: "Scarica installer",
    badges: [
      { icon: ShieldCheck, t: "Firmato da ForgeFPS", d: "Firma Authenticode Windows (in arrivo)" },
      { icon: FileCheck2, t: "SHA256 verificato", d: "Checksum pubblicato per ogni release" },
      { icon: Lock, t: "Installer sicuro", d: "Nessuno script remoto, nessun irm|iex" },
      { icon: RefreshCw, t: "Aggiornamenti trasparenti", d: "Changelog pubblico per ogni versione" },
    ],
    disclaimer: "La firma digitale è in fase di attivazione. Fino ad allora i badge sono informativi e ogni download riporta il suo checksum SHA256.",
  },
  en: {
    eyebrow: "// secure installer",
    title: "Verifiable installer",
    sub: "No remote commands. Download an installer, verify it, and run it yourself.",
    version: "v0.4.2 · Windows 10/11 · x64",
    download: "Download installer",
    badges: [
      { icon: ShieldCheck, t: "Signed by ForgeFPS", d: "Windows Authenticode signature (coming soon)" },
      { icon: FileCheck2, t: "SHA256 verified", d: "Checksum published for every release" },
      { icon: Lock, t: "Secure installer", d: "No remote scripts, no irm|iex" },
      { icon: RefreshCw, t: "Transparent updates", d: "Public changelog for every version" },
    ],
    disclaimer: "Code signing is being provisioned. Until then badges are informational and every download ships its SHA256 checksum.",
  },
};

export const SecureInstaller = ({ compact }) => {
  const lang = useLang();
  const c = COPY[lang];
  return (
    <HUDCard testid="secure-installer" pad="p-6">
      <div className="text-[11px] font-mono tracking-[0.2em] uppercase text-volt mb-2">{c.eyebrow}</div>
      <h3 className="font-display font-black text-2xl tracking-tight mb-2">{c.title}</h3>
      <p className="text-zinc-400 text-sm mb-5 max-w-md">{c.sub}</p>

      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
        <a href={AGENT_EXE_URL} target="_blank" rel="noreferrer" data-testid="secure-installer-download"
          className="group inline-flex items-center gap-2 bg-volt text-black font-bold px-6 py-3 hover:bg-volt-dim transition-colors btn-volt uppercase tracking-wide text-sm">
          <Download size={16} /> {c.download}
        </a>
        <span className="text-xs font-mono text-zinc-500">{AGENT_EXE_VERSION} · Windows 10/11 · x64</span>
      </div>

      <div className="flex items-center gap-2 mb-5 text-xs">
        <FileCheck2 size={13} className="text-ok shrink-0" />
        <span className="text-zinc-500">SHA256:</span>
        <code className="text-zinc-300 break-all" data-testid="secure-installer-sha256">{AGENT_EXE_SHA256}</code>
      </div>

      <div className={`grid ${compact ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1 sm:grid-cols-2"} gap-2`}>
        {c.badges.map((b, i) => (
          <div key={i} className="flex items-start gap-2.5 bg-black border border-hud-soft px-3 py-2.5">
            <b.icon size={16} className="text-ok shrink-0 mt-0.5" />
            <div>
              <div className="text-sm text-zinc-100 font-semibold">{b.t}</div>
              <div className="text-[11px] text-zinc-500">{b.d}</div>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-zinc-600 mt-4 leading-relaxed">{c.disclaimer}</p>
    </HUDCard>
  );
};
