import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { Send, Plus, Trash2, Loader2, MessageSquareCode, Terminal, Cpu, Copy, Check,
  ThumbsUp, ThumbsDown, RefreshCw, Image as ImageIcon, X as XIcon, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api, { API } from "@/lib/api";
import { PageHeader } from "@/components/hud";
import DiagnosePanel from "@/components/DiagnosePanel";

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
  const [mode, setMode] = useState(() => (typeof localStorage !== "undefined" && localStorage.getItem("advisor_mode")) || "default");
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [followups, setFollowups] = useState([]);
  const [feedback, setFeedback] = useState({}); // {msgIndex: "up"|"down"}
  const [copied, setCopied] = useState(null); // msgIndex
  const fileInputRef = useRef(null);
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

  const send = async (text, opts = {}) => {
    const msg = text ?? input;
    if ((!msg.trim() && !imageDataUrl) || streaming) return;
    setInput("");
    setFollowups([]);
    const img = opts.keepImage ? imageDataUrl : imageDataUrl;
    setImageDataUrl("");
    setMessages((m) => [...m, { role: "user", content: msg, image: img }, { role: "assistant", content: "" }]);
    setStreaming(true);
    try {
      const res = await fetch(`${API}/advisor/chat`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msg, session_id: sessionId, mode,
          image_data_url: img || "",
          lang: (i18n.resolvedLanguage || "it").slice(0, 2),
        }),
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
      // Load follow-ups after successful stream
      const targetSid = sid || sessionId;
      if (targetSid) {
        api.post(`/advisor/followups?session_id=${targetSid}`).then(({ data }) => {
          setFollowups(data?.suggestions || []);
        }).catch(() => {});
      }
    } catch (e) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: t("advisor.error_conn") };
        return copy;
      });
    } finally { setStreaming(false); }
  };

  const submitFeedback = async (msgIndex, msg, rating) => {
    if (feedback[msgIndex] === rating) return;
    try {
      await api.post("/advisor/feedback", {
        target_type: "chat_message",
        target_id: `${sessionId || "new"}-${msgIndex}`,
        action_title: msg.content.slice(0, 100),
        rating,
      });
      setFeedback((prev) => ({ ...prev, [msgIndex]: rating }));
    } catch {}
  };

  const copyMessage = async (msgIndex, content) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(msgIndex);
      setTimeout(() => setCopied(null), 1500);
    } catch {}
  };

  const regenerateLast = async () => {
    // Trova l'ultimo messaggio utente e lo re-invia
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        // rimuovi l'ultima risposta AI
        setMessages((m) => m.slice(0, i + 1));
        setTimeout(() => send(messages[i].content, { keepImage: false }), 50);
        return;
      }
    }
  };

  const changeMode = (m) => {
    setMode(m);
    try { localStorage.setItem("advisor_mode", m); } catch {}
  };

  const handleImageChoose = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
      alert("Immagine troppo grande (max 4MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => setImageDataUrl(ev.target.result);
    reader.readAsDataURL(file);
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
      <PageHeader eyebrow={t("advisor.eyebrow")} title={t("advisor.subtitle")}
        actions={specs?.data?.cpu && (
          <div data-testid="specs-badge" className="inline-flex items-center gap-2 text-xs text-[#00FF66] border border-[#00FF66]/40 bg-[#00FF66]/10 px-3 py-1.5">
            <Cpu size={13} /> {t("advisor.personalized")}: {specs.data.cpu}{specs.data.gpu ? ` · ${specs.data.gpu}` : ""}
          </div>
        )} />

      <DiagnosePanel hasSpecs={!!specs?.data?.cpu} />

      <div className="grid lg:grid-cols-[240px_1fr] gap-4">
        <div className="bg-[#0F0F12] border border-[#2A2A35] flex flex-col h-[70vh]">
          <button data-testid="new-chat-btn" onClick={newChat}
            className="m-3 flex items-center justify-center gap-2 bg-[#E5FF00] text-black font-bold py-2 hover:bg-[#D4EC00] transition-colors btn-volt">
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
          {/* Coach mode selector */}
          <div className="border-b border-[#2A2A35] px-4 py-2 flex items-center gap-2 text-xs">
            <Sparkles size={12} className="text-[#E5FF00] shrink-0" />
            <span className="text-zinc-500 font-mono uppercase tracking-widest mr-1">Coach:</span>
            {[
              { id: "default", label: "Default" },
              { id: "fps", label: "🎮 FPS" },
              { id: "streaming", label: "🎬 Streaming" },
              { id: "troubleshoot", label: "🛠️ Troubleshoot" },
              { id: "build", label: "💰 Build" },
            ].map((opt) => (
              <button
                key={opt.id}
                onClick={() => changeMode(opt.id)}
                data-testid={`coach-mode-${opt.id}`}
                className={`px-2 py-1 border transition-colors ${mode === opt.id ? "border-[#E5FF00] bg-[#E5FF00]/10 text-[#E5FF00]" : "border-[#2A2A35] text-zinc-500 hover:text-white"}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-auto p-6 space-y-4">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <Terminal size={40} className="text-[#E5FF00] mb-4" />
                <h3 className="font-display font-semibold text-lg mb-2">{t("advisor.empty_title")}</h3>
                <p className="text-zinc-500 text-sm mb-6 max-w-sm">{t("advisor.suggestions")}</p>
                <div className="grid sm:grid-cols-2 gap-2 w-full max-w-lg">
                  {suggestions.map((s, i) => (
                    <button key={i} data-testid={`suggestion-${i}`} onClick={() => send(s)}
                      className="group flex items-start gap-2 text-left text-xs text-zinc-400 border border-[#2A2A35] p-3 hover:border-[#E5FF00] hover:text-white hover:-translate-y-0.5 transition-all">
                      <MessageSquareCode size={13} className="text-[#E5FF00] shrink-0 mt-0.5 icon-pop" /> {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
                <div className={`flex items-end gap-2 ${m.role === "user" ? "flex-row-reverse" : ""} w-full`}>
                  {m.role === "assistant" && (
                    <div data-testid="ai-avatar" className="w-7 h-7 bg-[#00E0FF]/15 border border-[#00E0FF]/40 flex items-center justify-center shrink-0 text-[#00E0FF]"><MessageSquareCode size={14} /></div>
                  )}
                  <div className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${
                    m.role === "user" ? "bg-[#E5FF00] text-black whitespace-pre-wrap" : "bg-black border border-[#2A2A35] text-zinc-200"}`}>
                    {m.image && (
                      <img src={m.image} alt="allegato" className="max-h-40 mb-2 border border-black/20" />
                    )}
                    {m.role === "user"
                      ? m.content
                      : (m.content
                          ? <div className="ai-md"><ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{m.content}</ReactMarkdown></div>
                          : (streaming && i === messages.length - 1
                              ? <span className="flex items-center gap-1 py-0.5">
                                  <span className="w-1.5 h-1.5 bg-[#00E0FF] rounded-full typing-dot" />
                                  <span className="w-1.5 h-1.5 bg-[#00E0FF] rounded-full typing-dot" style={{ animationDelay: "0.2s" }} />
                                  <span className="w-1.5 h-1.5 bg-[#00E0FF] rounded-full typing-dot" style={{ animationDelay: "0.4s" }} />
                                </span>
                              : ""))}
                  </div>
                </div>
                {/* Actions row: solo su AI messages completi */}
                {m.role === "assistant" && m.content && !(streaming && i === messages.length - 1) && (
                  <div className="ml-9 mt-1 flex items-center gap-1 opacity-40 hover:opacity-100 transition-opacity">
                    <button onClick={() => submitFeedback(i, m, "up")} data-testid={`msg-thumb-up-${i}`}
                      className={`p-1 border transition-colors ${feedback[i]==="up" ? "border-[#00FF66] bg-[#00FF66]/10 text-[#00FF66]" : "border-transparent text-zinc-500 hover:text-[#00FF66]"}`} aria-label="Utile">
                      <ThumbsUp size={11} />
                    </button>
                    <button onClick={() => submitFeedback(i, m, "down")} data-testid={`msg-thumb-down-${i}`}
                      className={`p-1 border transition-colors ${feedback[i]==="down" ? "border-[#FF3B30] bg-[#FF3B30]/10 text-[#FF3B30]" : "border-transparent text-zinc-500 hover:text-[#FF3B30]"}`} aria-label="Non utile">
                      <ThumbsDown size={11} />
                    </button>
                    <button onClick={() => copyMessage(i, m.content)} data-testid={`msg-copy-${i}`}
                      className="p-1 border border-transparent text-zinc-500 hover:text-[#00E0FF]" aria-label="Copia">
                      {copied === i ? <Check size={11} className="text-[#00FF66]" /> : <Copy size={11} />}
                    </button>
                    {i === messages.length - 1 && !streaming && (
                      <button onClick={regenerateLast} data-testid="msg-regen"
                        className="p-1 border border-transparent text-zinc-500 hover:text-[#E5FF00]" aria-label="Rigenera">
                        <RefreshCw size={11} />
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            {/* Follow-up chips (solo dopo l'ultima risposta AI non-streaming) */}
            {followups.length > 0 && !streaming && messages.length > 0 && messages[messages.length - 1].role === "assistant" && (
              <div className="ml-9 flex flex-wrap gap-1.5" data-testid="followup-chips">
                {followups.map((f, i) => (
                  <button key={i} onClick={() => send(f)} data-testid={`followup-${i}`}
                    className="text-xs px-3 py-1.5 border border-[#00E0FF]/40 bg-[#00E0FF]/5 text-[#00E0FF] hover:bg-[#00E0FF]/15 transition-colors">
                    {f}
                  </button>
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          <div className="border-t border-[#2A2A35] p-3 space-y-2">
            {imageDataUrl && (
              <div className="flex items-center gap-2 bg-black/40 border border-[#00E0FF]/40 p-2" data-testid="image-preview">
                <img src={imageDataUrl} alt="allegato" className="h-16 border border-[#2A2A35]" />
                <span className="text-xs text-[#00E0FF] font-mono flex-1">Immagine allegata (verrà inviata con il prossimo messaggio)</span>
                <button onClick={() => setImageDataUrl("")} className="text-zinc-500 hover:text-[#FF3B30]" data-testid="image-remove">
                  <XIcon size={16} />
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <input type="file" accept="image/*" ref={fileInputRef} onChange={handleImageChoose} className="hidden" data-testid="image-file-input" />
              <button onClick={() => fileInputRef.current?.click()} data-testid="image-attach-btn"
                className="border border-[#2A2A35] hover:border-[#00E0FF] text-zinc-500 hover:text-[#00E0FF] px-3 transition-colors" title="Allega screenshot (max 4MB)">
                <ImageIcon size={16} />
              </button>
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
    </div>
  );
}
