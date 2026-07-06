import { useState } from "react";
import { Activity, Radio } from "lucide-react";
import MyPc from "./MyPc";
import Live from "./Live";

const TABS = [
  { id: "overview", label: "Panoramica", icon: Activity },
  { id: "live", label: "Monitoraggio Live", icon: Radio },
];

export default function MyPcHub({ initialTab = "overview" }) {
  const [tab, setTab] = useState(initialTab);
  return (
    <div className="fade-up" data-testid="mypc-hub">
      <div className="max-w-6xl mx-auto mb-4 flex gap-2">
        {TABS.map((t) => (
          <button key={t.id} data-testid={`mypc-tab-${t.id}`} onClick={() => setTab(t.id)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === t.id ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            <t.icon size={16} /> {t.label}
          </button>
        ))}
      </div>
      {tab === "overview" ? <MyPc /> : <Live />}
    </div>
  );
}
