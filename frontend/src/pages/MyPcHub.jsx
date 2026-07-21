import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Activity, Radio, Gauge } from "lucide-react";
import MyPc from "./MyPc";
import Live from "./Live";
import Benchmark from "./Benchmark";

const TABS = [
  { id: "overview", key: "mypc.tab_overview", icon: Activity },
  { id: "live", key: "mypc.tab_live", icon: Radio },
  { id: "benchmark", key: "mypc.tab_benchmark", icon: Gauge },
];

export default function MyPcHub({ initialTab = "overview" }) {
  const [tab, setTab] = useState(initialTab);
  const { t } = useTranslation();
  const renderTab = () => {
    if (tab === "live") return <Live />;
    if (tab === "benchmark") return <Benchmark />;
    return <MyPc />;
  };
  return (
    <div className="fade-up" data-testid="mypc-hub">
      <div className="max-w-6xl mx-auto mb-4 flex gap-2 flex-wrap">
        {TABS.map((tb) => (
          <button key={tb.id} data-testid={`mypc-tab-${tb.id}`} onClick={() => setTab(tb.id)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === tb.id ? "bg-[#E5FF00] text-black" : "border border-[#2A2A35] text-zinc-400 hover:border-[#E5FF00]"}`}>
            <tb.icon size={16} /> {t(tb.key, { defaultValue: tb.id })}
          </button>
        ))}
      </div>
      {renderTab()}
    </div>
  );
}
