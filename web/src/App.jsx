import { useEffect, useRef, useState } from "react";

const DISCLAIMER =
  "Noor finds and explains what your books say. It does not issue religious rulings. For a ruling on your own situation, ask a qualified scholar.";

async function api(path, body) {
  const res = await fetch(`/api/${path}`, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : undefined);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
  return res.json();
}

// "[1, 2]" in the answer becomes clickable citation markers.
function AnswerText({ text, citations, onCite }) {
  const parts = text.split(/(\[\d+(?:,\s*\d+)*\])/g);
  return (
    <p className="font-body text-[1.15rem] leading-relaxed text-parchment whitespace-pre-wrap">
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+(?:,\s*\d+)*)\]$/);
        if (!m) return <span key={i}>{part}</span>;
        return m[1].split(/,\s*/).map((n) => {
          const c = citations.find((x) => x.n === Number(n));
          return (
            <button key={`${i}-${n}`} onClick={() => c && onCite(c)} title={c?.label}
              className="mx-0.5 align-super rounded px-1 font-ui text-[0.7rem] text-gold-400 ring-1 ring-gold-600/50 hover:bg-gold-500/15">
              {n}
            </button>
          );
        });
      })}
    </p>
  );
}

// F13: how well each source matches the question. F20: warn on weak hadith grades.
function Badges({ c }) {
  return (
    <>
      {c.confidence && (
        <span title={`similarity ${c.similarity}`}
          className={`ml-2 rounded-full px-2 py-px text-[0.65rem] uppercase tracking-wide ${c.confidence === "strong"
            ? "bg-gold-500/15 text-gold-300" : "bg-parchment/10 text-parchment/50"}`}>
          {c.confidence} match
        </span>
      )}
      {c.grade_flag === "weak" && (
        <span title={c.grades} className="ml-2 rounded-full bg-red-500/15 px-2 py-px text-[0.65rem] uppercase tracking-wide text-red-300">
          weak grade
        </span>
      )}
    </>
  );
}

function Message({ m, question, onCite }) {
  const [vote, setVote] = useState(0);
  const [saved, setSaved] = useState(false);
  if (m.role === "user") {
    return <div className="font-serif text-xl text-gold-300">{m.text}</div>;
  }
  if (m.error) return <div className="font-ui text-sm text-red-300">Error: {m.error}</div>;
  const sendVote = (v) => api("feedback", { query_id: m.query_id, question, vote: v, cited_ids: m.citations.map((c) => c.id) })
    .then(() => setVote(v)).catch(() => {});
  const save = () => api("notes", { question, answer: m.answer, citations: m.citations }).then(() => setSaved(true)).catch(() => {});
  return (
    <div className="space-y-3">
      <AnswerText text={m.answer} citations={m.citations} onCite={onCite} />
      {m.refused && m.reason && <div className="font-ui text-xs text-parchment/50">({m.reason})</div>}
      {m.citations.length > 0 && (
        <ol className="space-y-1">
          {m.citations.map((c) => (
            <li key={c.id}>
              <button onClick={() => onCite(c)}
                className="text-left font-ui text-sm text-parchment/70 hover:text-gold-300">
                <span className="text-gold-500">[{c.n}]</span> {c.label}
              </button>
              <Badges c={c} />
            </li>
          ))}
        </ol>
      )}
      <div className="flex flex-wrap items-center gap-3 font-ui text-[0.7rem] text-parchment/40">
        <span>{m.cached ? "answer cache · $0" : `${m.model} · ${m.tokens_in} in / ${m.tokens_out} out · $${m.cost_usd.toFixed(5)} · ${(m.latency_ms / 1000).toFixed(1)} s`}</span>
        <span className="flex gap-1" aria-label="Rate this answer">
          <button onClick={() => sendVote(1)} aria-pressed={vote === 1} title="Good answer"
            className={`rounded px-1 ${vote === 1 ? "text-gold-300" : "hover:text-gold-300"}`}>👍</button>
          <button onClick={() => sendVote(-1)} aria-pressed={vote === -1} title="Bad answer: adds it to the eval candidates"
            className={`rounded px-1 ${vote === -1 ? "text-red-300" : "hover:text-red-300"}`}>👎</button>
        </span>
        {!m.refused && (
          <button onClick={save} disabled={saved} className="hover:text-gold-300 disabled:text-gold-500/70">
            {saved ? "Saved to notebook" : "Save"}
          </button>
        )}
      </div>
    </div>
  );
}

function Drawer({ cite, onClose }) {
  const [chunk, setChunk] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!cite) return;
    setChunk(null); setErr("");
    api(`chunk/${encodeURIComponent(cite.id)}`).then(setChunk).catch((e) => setErr(e.message));
  }, [cite]);
  if (!cite) return null;
  return (
    <aside aria-label="Source passage"
      className="fixed inset-y-0 right-0 z-20 flex w-full max-w-xl flex-col border-l border-gold-600/30 bg-ink-900 shadow-2xl">
      <header className="flex items-start justify-between gap-4 border-b border-gold-600/20 p-5">
        <div>
          <div className="font-ui text-xs uppercase tracking-widest text-gold-500">Source [{cite.n}]</div>
          <h2 className="font-serif text-2xl text-gold-300">{cite.label}</h2>
          {cite.grades && <div className="mt-1 font-ui text-xs text-parchment/60">Grade: {cite.grades}</div>}
          <div className="mt-1 font-ui text-xs"><Badges c={cite} /></div>
          {cite.book_reader_url && (
            <a href={cite.book_reader_url} target="_blank" rel="noreferrer"
              className="mt-2 inline-block font-ui text-xs text-gold-400 underline hover:text-gold-300">Open in Book Reader ↗</a>
          )}
        </div>
        <button onClick={onClose} className="font-ui text-parchment/60 hover:text-gold-300" aria-label="Close">✕</button>
      </header>
      <div className="flex-1 overflow-y-auto p-6 font-body text-lg leading-relaxed text-parchment/90 whitespace-pre-wrap">
        {err ? <span className="text-red-300">{err}</span> : chunk ? chunk.text.replace(/^(## |> )/gm, "") : "Loading…"}
      </div>
      <footer className="border-t border-gold-600/20 p-3 font-ui text-[0.7rem] text-parchment/40">{cite.id}</footer>
    </aside>
  );
}

export default function App() {
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [cite, setCite] = useState(null);
  const [conversation, setConversation] = useState(null);
  const end = useRef(null);

  useEffect(() => {
    // The API can still be starting when the page loads: retry for ~30 s.
    let tries = 0, timer;
    const load = () => api("models")
      .then((d) => { setModels(d.models); setModel(d.default); })
      .catch(() => { if (++tries < 15) timer = setTimeout(load, 2000); });
    load();
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  // Shareable links: ?q=<question> asks it on load; &cite=<n> also opens that source.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const q = p.get("q");
    if (!q) return;
    ask(q).then((d) => {
      const n = Number(p.get("cite"));
      const c = d?.citations?.find((x) => x.n === n);
      if (c) setCite(c);
    });
  }, []);

  async function send(e) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    await ask(q);
  }

  async function ask(q) {
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: q }]);
    try {
      const d = await api("ask", { question: q, model: model || undefined, conversation_id: conversation });
      setConversation(d.conversation_id);
      setMessages((m) => [...m, { role: "assistant", ...d }]);
      return d;
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", error: err.message }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex h-full flex-col bg-ink-950 bg-[radial-gradient(ellipse_at_top,rgba(201,162,76,0.08),transparent_60%)]">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gold-600/20 px-6 py-4">
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-3xl font-semibold tracking-wide text-gold-400">Noor</h1>
          <span className="font-ui text-xs text-parchment/50">answers from your library, with sources</span>
        </div>
        <div className="flex items-center gap-3">
          <a href="/api/notes/export" download="noor-notebook.md"
            className="font-ui text-xs text-parchment/60 hover:text-gold-300">Export notebook</a>
          <button onClick={() => { setMessages([]); setConversation(null); }}
            className="font-ui text-xs text-parchment/60 hover:text-gold-300">New chat</button>
          <label className="font-ui text-xs text-parchment/60">
            Model{" "}
            <select value={model} onChange={(e) => setModel(e.target.value)}
              className="ml-1 rounded border border-gold-600/40 bg-ink-800 px-2 py-1 text-parchment">
              {models.map((m) => (
                <option key={m.id} value={m.id} disabled={!m.available}>
                  {m.label}{m.available ? "" : " (needs key)"}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <div role="note" className="border-b border-gold-600/10 bg-gold-500/5 px-6 py-2 text-center font-ui text-xs text-gold-300/80">
        {DISCLAIMER}
      </div>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
          {messages.length === 0 && (
            <div className="pt-16 text-center">
              <p className="font-serif text-2xl text-parchment/70">Ask what your books say.</p>
              <p className="mt-2 font-ui text-sm text-parchment/40">e.g. "What does the Quran say about patience?"</p>
            </div>
          )}
          {messages.map((m, i) => <Message key={i} m={m} question={messages[i - 1]?.text} onCite={setCite} />)}
          {busy && <div className="font-ui text-sm text-gold-500/70 animate-pulse">Searching your library…</div>}
          <div ref={end} />
        </div>
      </main>

      <form onSubmit={send} className="border-t border-gold-600/20 bg-ink-900/80 px-6 py-4">
        <div className="mx-auto flex max-w-3xl gap-3">
          <input value={input} onChange={(e) => setInput(e.target.value)} aria-label="Your question"
            placeholder={conversation ? "Ask a follow-up…" : "Ask a question…"}
            className="flex-1 rounded-lg border border-gold-600/40 bg-ink-800 px-4 py-3 font-body text-lg text-parchment placeholder:text-parchment/30 focus:border-gold-400 focus:outline-none" />
          <button disabled={busy || !input.trim()}
            className="rounded-lg bg-gold-500 px-5 font-ui text-sm font-medium text-ink-950 hover:bg-gold-400 disabled:opacity-40">
            Ask
          </button>
        </div>
      </form>
      <Drawer cite={cite} onClose={() => setCite(null)} />
    </div>
  );
}
