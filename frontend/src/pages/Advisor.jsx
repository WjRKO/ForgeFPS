import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Send, Plus, Trash2, Loader2, MessageSquareCode, Terminal, Cpu, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api, { API } from "@/lib/api";

function CodeBlock({ children }) {
  const [copied, setCopied] = useState(false);
  const text = String(children).replace(/\n$/, "");
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); } catch { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative my-2 group/code" data-testid="ai-code-block">
      <button onClick={copy} data-testid="ai-code-copy"
        className="absolute top-2 right-2 flex items-center gap-1 border border-[#2A2A35] bg-[#0F0F12] px-2 py-1 text-[10px] text-zinc-400 hover:border-[#E5FF00] hover:text-white transition-colors">
        {copied ? <Check size={12} className="text-[#00FF66]" /> : <Copy size={12} />} {copied ? i18n.t("advisor.copied") : i18n.t("advisor.copy_code")}
      </button>
      <pre className="bg-black border border-[#2A2A35] p-3 pr-16 overflow-x-auto text-xs text-[#00FF66] leading-relaxed">
        <code>{text}</code>
      </pre>
    </div>
  );
}

const MD = {
  pre({ children }) {
    const codeEl = Array.isArray(children) ? children[0] : children;
    const text = codeEl?.props?.children ?? "";
    return <CodeBlock>{text}</CodeBlock>;
  },
  code({ children }) {
    return <code className="bg-black/60 border border-[#2A2A35] px-1 py-0.5 text-[#00E0FF] text-[0.85em]">{children}</code>;
  },
  h1: ({ children }) => <h3 className="font-display font-bold text-base mt-3 mb-1">{children}</h3>,
  h2: ({ children }) => <h3 className="font-display font-bold text-base mt-3 mb-1">{children}</h3>,
  h3: ({ children }) => <h4 className="font-display font-semibold text-sm mt-2 mb-1">{children}</h4>,
  ul: ({ children }) => <ul className="list-disc pl-5 my-1 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 my-1 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="text-sm">{children}</li>,
  p: ({ children }) => <p className="my-1 text-sm leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="text-white font-bold">{children}</strong>,
  a: ({ children, href }) => <a href={href} target="_blank" rel="noreferrer" className="text-[#E5FF00] hover:underline">{children}</a>,
  table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border border-[#2A2A35]">{children}</table></div>,
  th: ({ children }) => <th className="border border-[#2A2A35] px-2 py-1 text-left bg-[#141419]">{children}</th>,
  td: ({ children }) => <td className="border border-[#2A2A35] px-2 py-1">{children}</td>,
};

export default function Advisor() {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [specs, setSpecs] = useState(null);
  const [suggestions, setSuggestions] = useState(() => i18n.t("advisor.default_suggestions", { returnObjects: true }));
  const endRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const autoSent = useRef(false);

  const loadSessions = async () => {
    try { const { data } = await api.get("/advisor/sessions"); setSessions(data); } catch {}
  };
  useEffect(() => {
    loadSessions();
    api.get("/pc-specs").then(({ data }) => setSpecs(data)).catch(() => {});
    const lng = (i18n.resolvedLanguage || "it").slice(0, 2);
    api.get(`/advisor/suggestions?lang=${lng}`).then(({ data }) => { if (data?.suggestions?.length) setSuggestions(data.suggestions); }).catch(() => {});
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const openSession = async (id) => {
    setSessionId(id);
    const { data } = await api.get(`/advisor/sessions/${id}`);
    setMessages(data);
  };

  const newChat = () => { setSessionId(null); setMessages([]); };

  const deleteSession = async (id, e) => {
    e.stopPropagation();
    await api.delete(`/advisor/sessions/${id}`);
    if (id === sessionId) newChat();
    loadSessions();
  };

  const send = async (text) => {
    const msg = text ?? input;
    if (!msg.trim() || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const res = await fetch(`${API}/advisor/chat`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, session_id: sessionId, lang: (i18n.resolvedLanguage || "it").slice(0, 2) }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let acc = "";
      let sid = sessionId;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        let chunk = decoder.decode(value, { stream: true });
        const m = chunk.match(/^__SESSION__(.+?)__\n/);
        if (m) { sid = m[1]; chunk = chunk.replace(m[0], ""); }
        acc += chunk;
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: "assistant", content: acc };
          return copy;
        });
      }
      if (!sessionId && sid) { setSessionId(sid); loadSessions(); }
      else loadSessions();
    } catch (e) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: t("advisor.error_conn") };
        return copy;
      });
    } finally { setStreaming(false); }
  };

  useEffect(() => {
    const ask = location.state?.ask;
    if (ask && !autoSent.current) {
      autoSent.current = true;
      navigate(location.pathname, { replace: true, state: {} });
      send(ask);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  return (
    <div className="max-w-6xl mx-auto fade-up">
      <div className="mb-6">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-2">{t("advisor.eyebrow")}</div>
        <h1 className="font-display font-black text-3xl tracking-tighter">{t("advisor.subtitle")}</h1>
        {specs?.data?.cpu && (
          <div data-testid="specs-badge" className="inline-flex items-center gap-2 mt-3 text-xs text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-3 py-1.5">
            <Cpu size={13} /> {t("advisor.personalized")}: {specs.data.cpu}{specs.data.gpu ? ` · ${specs.data.gpu}` : ""}
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-[240px_1fr] gap-4">
        <div className="bg-[#0F0F12] border border-[#2A2A35] flex flex-col h-[70vh]">
          <button data-testid="new-chat-btn" onClick={newChat}
            className="m-3 flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-2 hover:bg-[#D4EC00] transition-colors">
            <Plus size={16} /> {t("common.new_chat")}
          </button>
          <div className="flex-1 overflow-auto px-2 pb-2">
            {sessions.map((s) => (
              <div key={s.id} onClick={() => openSession(s.id)} data-testid={`session-${s.id}`}
                className={`group flex items-center gap-2 px-3 py-2 text-sm cursor-pointer transition-colors ${sessionId === s.id ? "bg-[#141419] text-white" : "text-zinc-400 hover:bg-[#141419]"}`}>
                <MessageSquareCode size={14} className="shrink-0" />
                <span className="flex-1 truncate">{s.title}</span>
                <button onClick={(e) => deleteSession(s.id, e)} className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-[#FF3B30]">
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#0F0F12] border border-[#2A2A35] flex flex-col h-[70vh] relative overflow-hidden">
          <div className="flex-1 overflow-auto p-6 space-y-4">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <Terminal size={40} className="text-[#E5FF00] mb-4" />
                <h3 className="font-display font-semibold text-lg mb-2">{t("advisor.empty_title")}</h3>
                <p className="text-zinc-500 text-sm mb-6 max-w-sm">{t("advisor.suggestions")}</p>
                <div className="grid sm:grid-cols-2 gap-2 w-full max-w-lg">
                  {suggestions.map((s, i) => (
                    <button key={i} data-testid={`suggestion-${i}`} onClick={() => send(s)}
                      className="text-left text-xs text-zinc-400 border border-[#2A2A35] p-3 hover:border-[#E5FF00] hover:text-white transition-colors">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user" ? "bg-[#E5FF00] text-black whitespace-pre-wrap" : "bg-black border border-[#2A2A35] text-zinc-200"}`}>
                  {m.role === "user"
                    ? m.content
                    : (m.content
                        ? <div className="ai-md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{m.content}</ReactMarkdown></div>
                        : (streaming && i === messages.length - 1 ? <span className="cursor-blink">▋</span> : ""))}
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="border-t border-[#2A2A35] p-3 flex gap-2">
            <input data-testid="chat-input" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()} placeholder={t("advisor.placeholder")}
              className="flex-1 bg-black border border-[#2A2A35] focus:border-[#E5FF00] outline-none px-3 py-2 text-sm transition-colors" />
            <button data-testid="chat-send-btn" onClick={() => send()} disabled={streaming}
              className="bg-[#E5FF00] text-black px-4 hover:bg-[#D4EC00] transition-colors disabled:opacity-60">
              {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
