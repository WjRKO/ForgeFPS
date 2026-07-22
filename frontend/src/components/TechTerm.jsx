import { useTranslation } from "react-i18next";
import { HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * TechTerm — inline tooltip for jargon.
 * Usage:  <TechTerm term="bufferbloat">Bufferbloat</TechTerm>
 *         <TechTerm term="mpo" iconOnly />   // just a "?" next to the word
 *
 * The dictionary lives here (single source of truth) so we don't scatter
 * translations for the same acronym across pages.
 */
const GLOSSARY_IT = {
  bufferbloat: "Ritardo di rete extra causato da buffer troppo pieni. Causa lag anche quando il ping è basso — critico per FPS competitivi.",
  mpo: "Multi-Plane Overlay: funzione Windows che compone il desktop con più layer. Ha bug con OBS Game Capture (schermo nero) e alcuni driver.",
  hags: "Hardware-accelerated GPU Scheduling: sposta la pianificazione dei frame dalla CPU al chip della GPU. Riduce la latenza di 1-3 ms.",
  msi_mode: "Message Signaled Interrupts: interrupt più veloci per dispositivi (mouse, GPU). Riduce input lag di 1-2 ms.",
  mmcss: "MultiMedia Class Scheduler Service: dà priorità di CPU ai processi multimediali e giochi in primo piano.",
  ulps: "Ultra Low Power State (solo GPU AMD): abbassa il clock in idle. Causa stutter per la lentezza dei risvegli. Meglio disabilitato per gaming.",
  hiberfil: "Il file `hiberfil.sys` usato per la sospensione ibrida. Su desktop occupa 4-32 GB inutili — puoi disabilitare con `powercfg -h off`.",
  dpi: "Dots Per Inch del mouse: sensibilità hardware. Combinato con la sensibilità in-game determina il conteggio effettivo di conteggi/pixel.",
  dwm: "Desktop Window Manager: il compositor di Windows che disegna il desktop. Influenza la latenza percepita nelle app windowed.",
  ping: "Tempo di andata + ritorno di un pacchetto verso un server. Sotto 30ms = ottimo per online gaming.",
  jitter: "Variazione del ping nel tempo. Un ping stabile a 40ms è meglio di un ping variabile 20-80ms.",
  frametime: "Tempo (in ms) impiegato dalla GPU per generare un frame. 16.7ms = 60 FPS, 8.3ms = 120 FPS. La costanza è più importante del picco.",
};
const GLOSSARY_EN = {
  bufferbloat: "Extra network latency caused by oversized buffers. Adds lag even when ping is low — critical for competitive FPS.",
  mpo: "Multi-Plane Overlay: Windows feature that composes the desktop with multiple layers. Has bugs with OBS Game Capture (black screen) and some drivers.",
  hags: "Hardware-accelerated GPU Scheduling: moves frame scheduling from the CPU to the GPU chip. Reduces latency by 1-3 ms.",
  msi_mode: "Message Signaled Interrupts: faster interrupts for devices (mouse, GPU). Reduces input lag by 1-2 ms.",
  mmcss: "MultiMedia Class Scheduler Service: gives CPU priority to multimedia and foreground games.",
  ulps: "Ultra Low Power State (AMD GPU only): lowers clocks at idle. Causes stutter due to slow wake-ups. Better disabled for gaming.",
  hiberfil: "The `hiberfil.sys` file used for hybrid sleep. On desktops it wastes 4-32 GB — you can disable it with `powercfg -h off`.",
  dpi: "Dots Per Inch of the mouse: hardware sensitivity. Combined with in-game sensitivity, it defines counts/pixel.",
  dwm: "Desktop Window Manager: Windows' compositor that draws the desktop. Affects perceived latency in windowed apps.",
  ping: "Round-trip time of a packet to a server. Under 30ms = great for online gaming.",
  jitter: "Ping variability over time. A steady 40ms ping is better than a jittery 20-80ms.",
  frametime: "Time (in ms) the GPU takes to render a frame. 16.7ms = 60 FPS, 8.3ms = 120 FPS. Consistency matters more than peak.",
};

export default function TechTerm({ term, children, iconOnly = false, testid }) {
  const { i18n } = useTranslation();
  const dict = (i18n.resolvedLanguage || i18n.language || "en").startsWith("it") ? GLOSSARY_IT : GLOSSARY_EN;
  const definition = dict[term];
  if (!definition) return <>{children}</>;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid={testid || `tech-term-${term}`}
            className={`inline-flex items-baseline gap-1 cursor-help ${iconOnly ? "" : "border-b border-dashed border-[#00E0FF]/40 hover:border-[#00E0FF]"}`}>
            {!iconOnly && children}
            <HelpCircle size={11} className="text-[#00E0FF]/70 hover:text-[#00E0FF] shrink-0 translate-y-[1px]" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs bg-[#0F0F12] border-[#00E0FF]/40 text-xs leading-relaxed">
          {definition}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
