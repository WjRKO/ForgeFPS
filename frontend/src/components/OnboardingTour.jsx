import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Joyride, STATUS } from "react-joyride";
import { useTranslation } from "react-i18next";

const TOUR_KEY = "ff_tour_done_v1";

// I passi puntano a data-testid gia' presenti nella UI. Se un elemento non c'e' (utente mobile,
// tab non montata) Joyride lo skippa in automatico.
function buildSteps(t) {
  return [
    {
      target: "body",
      placement: "center",
      title: t("tour.welcome_t"),
      content: t("tour.welcome_c"),
      disableBeacon: true,
    },
    {
      target: '[data-testid="nav-pc"]',
      title: t("tour.pc_t"),
      content: t("tour.pc_c"),
    },
    {
      target: '[data-testid="nav-advisor"]',
      title: t("tour.advisor_t"),
      content: t("tour.advisor_c"),
    },
    {
      target: '[data-testid="nav-network"]',
      title: t("tour.network_t"),
      content: t("tour.network_c"),
    },
    {
      target: '[data-testid="nav-desktop"]',
      title: t("tour.desktop_t"),
      content: t("tour.desktop_c"),
    },
    {
      target: '[data-testid="nav-gaming"]',
      title: t("tour.gaming_t"),
      content: t("tour.gaming_c"),
    },
    {
      target: '[data-testid="notifications-btn"]',
      title: t("tour.notif_t"),
      content: t("tour.notif_c"),
    },
    {
      target: '[data-testid="nav-account"]',
      title: t("tour.done_t"),
      content: t("tour.done_c"),
      placement: "top",
    },
  ];
}

export default function OnboardingTour() {
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  const [run, setRun] = useState(false);
  const [steps, setSteps] = useState([]);

  useEffect(() => {
    // Auto-start la prima volta che l'utente atterra su /app
    if (!pathname.startsWith("/app")) return;
    const done = typeof window !== "undefined" && window.localStorage.getItem(TOUR_KEY);
    if (!done) {
      // Delay per lasciar montare la sidebar
      const to = setTimeout(() => {
        setSteps(buildSteps(t));
        setRun(true);
      }, 800);
      return () => clearTimeout(to);
    }
  }, [pathname, i18n.language, t]);

  // Espone un handler globale per riavviare il tour da altre parti (es. Account page)
  useEffect(() => {
    const handler = () => {
      setSteps(buildSteps(t));
      setRun(true);
    };
    window.addEventListener("ff:tour:start", handler);
    return () => window.removeEventListener("ff:tour:start", handler);
  }, [t]);

  const onCallback = (data) => {
    const { status } = data;
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      try { window.localStorage.setItem(TOUR_KEY, "1"); } catch {}
      setRun(false);
    }
  };

  if (!steps.length) return null;
  return (
    <Joyride
      steps={steps}
      run={run}
      continuous
      showProgress
      showSkipButton
      disableOverlayClose
      hideCloseButton={false}
      spotlightPadding={6}
      callback={onCallback}
      locale={{
        back: t("tour.back"),
        close: t("tour.close"),
        last: t("tour.last"),
        next: t("tour.next"),
        skip: t("tour.skip"),
      }}
      styles={{
        options: {
          arrowColor: "#0F0F12",
          backgroundColor: "#0F0F12",
          overlayColor: "rgba(0, 0, 0, 0.78)",
          primaryColor: "#E5FF00",
          textColor: "#e6e6ec",
          zIndex: 10000,
        },
        tooltip: {
          padding: 20,
          borderRadius: 0,
          border: "1px solid #2A2A35",
          fontFamily: "inherit",
          backgroundColor: "#0F0F12",
          color: "#e6e6ec",
          boxShadow: "0 20px 60px rgba(229,255,0,0.08), 0 0 0 1px rgba(229,255,0,0.15)",
          maxWidth: 380,
        },
        tooltipContainer: { textAlign: "left" },
        tooltipTitle: {
          color: "#E5FF00",
          fontWeight: 800,
          fontSize: 14,
          letterSpacing: 1.2,
          textTransform: "uppercase",
          margin: 0,
          textShadow: "0 0 12px rgba(229,255,0,0.35)",
        },
        tooltipContent: {
          padding: "12px 0 6px",
          fontSize: 14,
          lineHeight: 1.6,
          color: "#dcdce5",
          textAlign: "left",
        },
        tooltipFooter: {
          marginTop: 14,
          alignItems: "center",
        },
        buttonNext: {
          backgroundColor: "#E5FF00",
          color: "#000",
          fontWeight: 800,
          borderRadius: 0,
          padding: "10px 22px",
          fontSize: 12,
          letterSpacing: 1.4,
          textTransform: "uppercase",
          border: "none",
          outline: "none",
          cursor: "pointer",
        },
        buttonBack: {
          color: "#a3a3b0",
          fontSize: 12,
          marginRight: 10,
          padding: "10px 14px",
          fontWeight: 600,
          letterSpacing: 0.6,
          textTransform: "uppercase",
        },
        buttonSkip: {
          color: "#7d7d8a",
          fontSize: 12,
          padding: "10px 14px",
          fontWeight: 600,
          letterSpacing: 0.6,
          textTransform: "uppercase",
        },
        buttonClose: { display: "none" },
        spotlight: { borderRadius: 0, boxShadow: "0 0 0 3px rgba(229,255,0,0.4), 0 0 30px rgba(229,255,0,0.25)" },
        beacon: { display: "none" },
      }}
    />
  );
}
