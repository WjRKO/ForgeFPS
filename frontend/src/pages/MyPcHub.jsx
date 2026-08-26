import { useSearchParams } from "react-router-dom";
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

export default function MyPcHub() {
  // La tab sta nell'URL (?tab=live), non in useState: prima il back tornava
  // fuori dalla pagina e il link a una tab non era condivisibile.
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((x) => x.id === params.get("tab")) ? params.get("tab") : "overview";
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
          <button key={tb.id} data-testid={`mypc-tab-${tb.id}`} onClick={() => setParams({ tab: tb.id })}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-bold transition-colors ${tab === tb.id ? "bg-volt text-black" : "border border-hud text-zinc-400 hover:border-volt"}`}>
            <tb.icon size={16} /> {t(tb.key, { defaultValue: tb.id })}
          </button>
        ))}
      </div>
      {renderTab()}
    </div>
  );
}
