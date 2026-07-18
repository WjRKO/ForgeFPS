import { useEffect, useState } from "react";
import axios from "axios";
import { MessagesSquare, Github, Mail, Bug } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;
const DISCORD_INVITE_FALLBACK = "https://discord.gg/KU3m9YFFnm";
const GITHUB_REPO = "https://github.com/WjRKO/ForgeFPS";
const GITHUB_ISSUES = `${GITHUB_REPO}/issues/new/choose`;
const CONTACT_EMAIL = "hello@forgefps.dev";

/**
 * Colonna "Community" del footer: Discord (con conteggio live opzionale),
 * GitHub, Report Bug, Contatti. Riutilizzabile in Landing e MarketingChrome.
 */
export function FooterCommunity({ t }) {
  const [discord, setDiscord] = useState({ enabled: false, presence_count: 0, invite_url: DISCORD_INVITE_FALLBACK });
  useEffect(() => {
    let cancelled = false;
    axios
      .get(`${API}/api/discord/live-stats`, { timeout: 6000 })
      .then((r) => !cancelled && setDiscord({ ...r.data, invite_url: r.data.invite_url || DISCORD_INVITE_FALLBACK }))
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const items = [
    {
      href: discord.invite_url,
      icon: MessagesSquare,
      label: t("landing.footer_discord"),
      extra: discord.enabled && discord.presence_count > 0 ? (
        <span className="inline-flex items-center gap-1 ml-2 text-[10px] font-mono text-[#00FF66]" data-testid="discord-online-badge">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00FF66] animate-pulse" />
          {discord.presence_count} {t("landing.footer_discord_online")}
        </span>
      ) : null,
      testid: "footer-discord",
    },
    { href: GITHUB_REPO, icon: Github, label: t("landing.footer_github"), testid: "footer-github" },
    { href: GITHUB_ISSUES, icon: Bug, label: t("landing.footer_report_bug"), testid: "footer-report-bug" },
    { href: `mailto:${CONTACT_EMAIL}`, icon: Mail, label: CONTACT_EMAIL, testid: "footer-contact" },
  ];

  return (
    <div>
      <div className="text-xs font-mono uppercase tracking-widest text-zinc-500 mb-4">
        {t("landing.footer_community")}
      </div>
      <ul className="space-y-2 text-sm text-zinc-400">
        {items.map((it) => (
          <li key={it.testid}>
            <a
              href={it.href}
              target={it.href.startsWith("mailto:") ? undefined : "_blank"}
              rel="noreferrer"
              data-testid={it.testid}
              className="inline-flex items-center gap-2 hover:text-[#E5FF00] transition-colors"
            >
              <it.icon size={13} className="text-zinc-500" />
              <span>{it.label}</span>
              {it.extra}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Legal row + firma discreta. Da inserire come fondo del footer.
 */
export function FooterLegal({ t }) {
  return (
    <div className="max-w-6xl mx-auto mt-10 pt-6 border-t border-[#1A1A24] flex flex-col md:flex-row items-center justify-between gap-3 text-xs font-mono">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-zinc-500">
        <span>{t("landing.footer_copyright")}</span>
        <span className="text-zinc-700">·</span>
        <a
          href="/privacy-telemetry#cookies"
          data-testid="footer-cookies"
          className="hover:text-[#E5FF00] transition-colors"
        >
          {t("landing.footer_legal_cookies")}
        </a>
        <span className="text-zinc-700">·</span>
        <a
          href="/terms"
          data-testid="footer-terms"
          className="hover:text-[#E5FF00] transition-colors"
        >
          {t("landing.footer_legal_terms")}
        </a>
        <span className="text-zinc-700">·</span>
        <a
          href="/privacy-telemetry"
          data-testid="footer-privacy"
          className="hover:text-[#E5FF00] transition-colors"
        >
          {t("landing.footer_legal_privacy")}
        </a>
      </div>
      <div className="text-zinc-600 italic" data-testid="footer-made-with-love">
        {t("landing.footer_made")}
      </div>
    </div>
  );
}
