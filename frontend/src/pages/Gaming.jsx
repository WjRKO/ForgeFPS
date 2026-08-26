import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Swords, Gamepad2, Timer } from "lucide-react";
import Games from "./Games";
import Profiles from "./Profiles";
import { MissionContextStrip } from "@/components/MissionContextStrip";
import { PostGameRecap } from "@/components/PostGameRecap";

const TABS = [
  { id: "games", key: "gaming.tab_games", icon: Swords },
  { id: "sessions", key: "gaming.tab_sessions", icon: Timer },
  { id: "profiles", key: "gaming.tab_profiles", icon: Gamepad2 },
];

export default function Gaming() {
  // Come in MyPcHub: la tab e' un search param, cosi' back e deep-link funzionano.
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((x) => x.id === params.get("tab")) ? params.get("tab") : "games";
  const { t } = useTranslation();
  return (
    <div className="fade-up" data-testid="gaming-page">
      <div className="max-w-6xl mx-auto">
        <MissionContextStrip metrics={["boost_sessions"]} />
      </div>
      <div className="max-w-6xl mx-auto mb-4 flex gap-2">
        {TABS.map((tb) => (
          <button key={tb.id} data-testid={`gaming-tab-${tb.id}`} onClick={() => setParams({ tab: tb.id })}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === tb.id ? "bg-volt text-black" : "border border-hud text-zinc-400 hover:border-volt"}`}>
            <tb.icon size={16} /> {t(tb.key)}
          </button>
        ))}
      </div>
      {tab === "games" ? <Games /> : tab === "sessions" ? (
        <div className="max-w-6xl mx-auto"><PostGameRecap /></div>
      ) : <Profiles />}
    </div>
  );
}
