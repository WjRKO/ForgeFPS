import { ShieldCheck, FileCheck2, Github, RotateCcw, ShieldOff, MonitorDown, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { AGENT_REPO_URL } from "@/config/agent";
import { useLang } from "@/components/MarketingChrome";

const COPY = {
  it: {
    vt: "Scansione VirusTotal",
    sha: "SHA256 verificabile",
    oss: "Open source · MIT",
    rev: "100% reversibile",
    norc: "Nessun codice remoto",
    local: "Local-first",
  },
  en: {
    vt: "VirusTotal scan",
    sha: "Verifiable SHA256",
    oss: "Open source · MIT",
    rev: "100% reversible",
    norc: "No remote code",
    local: "Local-first",
  },
};

export const TrustBar = ({ className = "" }) => {
  const lang = useLang();
  const c = COPY[lang];
  const items = [
    { icon: ShieldCheck, label: c.vt, to: "/security#faq-av", accent: "#00FF66", testid: "trust-virustotal" },
    { icon: FileCheck2, label: c.sha, accent: "#00E0FF", testid: "trust-sha256" },
    { icon: Github, label: c.oss, href: AGENT_REPO_URL, accent: "#E5FF00", testid: "trust-oss" },
    { icon: RotateCcw, label: c.rev, accent: "#B388FF", testid: "trust-reversible" },
    { icon: ShieldOff, label: c.norc, accent: "#FF6B00", testid: "trust-noremote" },
    { icon: MonitorDown, label: c.local, accent: "#00E0FF", testid: "trust-local" },
  ];
  return (
    <div className={`flex flex-wrap justify-center gap-2.5 ${className}`} data-testid="trust-bar">
      {items.map((it) => {
        const inner = (
          <>
            <it.icon size={15} style={{ color: it.accent }} className="shrink-0" />
            <span className="text-zinc-300">{it.label}</span>
            {it.href && <ExternalLink size={11} className="text-zinc-600 group-hover:text-zinc-300 transition-colors" />}
          </>
        );
        const base = "group inline-flex items-center gap-2 bg-[#0F0F12] border border-[#2A2A35] px-3.5 py-2 text-xs font-medium hover:border-[#E5FF00]/50 transition-colors";
        if (it.to) {
          return (
            <Link key={it.testid} to={it.to} data-testid={it.testid} className={base}>
              {inner}
            </Link>
          );
        }
        return it.href ? (
          <a key={it.testid} href={it.href} target="_blank" rel="noreferrer" data-testid={it.testid} className={base}>
            {inner}
          </a>
        ) : (
          <div key={it.testid} data-testid={it.testid} className={base.replace(" hover:border-[#E5FF00]/50 transition-colors", "")}>
            {inner}
          </div>
        );
      })}
    </div>
  );
};
