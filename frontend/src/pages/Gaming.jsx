import { useState } from "react";
import { Swords, Gamepad2 } from "lucide-react";
import Games from "./Games";
import Profiles from "./Profiles";

const TABS = [
  { id: "games", label: "I miei giochi", icon: Swords },
  { id: "profiles", label: "Profili Gioco", icon: Gamepad2 },
];

export default function Gaming({ initialTab = "games" }) {
  const [tab, setTab] = useState(initialTab);
  return (
    <div className="fade-up" data-testid="gaming-page">
      <div className="max-w-6xl mx-auto mb-4 flex gap-2">
        {TABS.map((t) => (
          <button key={t.id} data-testid={`gaming-tab-${t.id}`} onClick={() => setTab(t.id)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === t.id ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>
      {tab === "games" ? <Games /> : <Profiles />}
    </div>
  );
}
