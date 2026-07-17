// Google Ads conversion tracking (gtag.js already loaded in public/index.html).
const AW_ID = "AW-18329532067";

// Conversion labels from Google Ads. For each conversion action, Google gives a
// send_to value like "AW-18329532067/AbC-D_efGh". Paste ONLY the part AFTER the
// slash here. Leave as "" to keep a conversion disabled until you have its label.
export const CONVERSION_LABELS = {
  signup: "",          // "Registrazione completata"
  demo_scan: "",       // "Scansione demo completata"
  agent_download: "",  // "Download agent"
};

export function trackConversion(key) {
  const label = CONVERSION_LABELS[key];
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  if (!label) return; // no label configured yet -> skip silently
  window.gtag("event", "conversion", { send_to: `${AW_ID}/${label}` });
}
