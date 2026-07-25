/**
 * FirstScanBanner — orchestratore del flusso "primo scan":
 * - Utente veterano (dati preesistenti) -> null (banner nascosto silenziosamente)
 * - Utente nuovo in attesa dell'agent -> <ScanPendingBanner/> (guida 4 step + polling)
 * - Scan appena arrivato durante la sessione -> <ScanCompleteBanner/>
 *
 * Logica di polling isolata nel hook `useFirstScanPolling`.
 */
import { useTranslation } from "react-i18next";
import { useFirstScanPolling } from "@/hooks/useFirstScanPolling";
import ScanCompleteBanner from "./ScanCompleteBanner";
import ScanPendingBanner from "./ScanPendingBanner";

export default function FirstScanBanner() {
  const { i18n } = useTranslation();
  const en = (i18n.language || "").startsWith("en");
  const { status, specs } = useFirstScanPolling();

  if (status === "checking" || status === "idle") return null;
  if (status === "done-fresh") return <ScanCompleteBanner specs={specs} en={en} />;
  return <ScanPendingBanner en={en} />;
}
