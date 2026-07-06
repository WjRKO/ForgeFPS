import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Swords, Gamepad2 } from "lucide-react";
import Games from "./Games";
import Profiles from "./Profiles";

const TABS = [
  { id: "games", key: "gaming.tab_games", icon: Swords },
  { id: "profiles", key: "gaming.tab_profiles", icon: Gamepad2 },
];

export default function Gaming({ initialTab = "games" }) {
  const [tab, setTab] = useState(initialTab);
  const { t } = useTranslation();
  return (
    <div className="fade-up" data-testid="gaming-page">
      <div className="max-w-6xl mx-auto mb-4 flex gap-2">
        {TABS.map((tb) => (
          <button key={tb.id} data-testid={`gaming-tab-${tb.id}`} onClick={() => setTab(tb.id)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === tb.id ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            <tb.icon size={16} /> {t(tb.key)}
          </button>
        ))}
      </div>
      {tab === "games" ? <Games /> : <Profiles />}
    </div>
  );
}
