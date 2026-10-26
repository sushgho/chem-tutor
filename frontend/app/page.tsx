"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Avatar from "@/components/Avatar";
import Markdown from "@/components/Markdown";
import { getJSON, postJSON, streamPost, Source } from "@/lib/api";
import { Speaker, listenOnce } from "@/lib/speech";

type Topic = { id: string; title: string };
type Unit = { unit_no: number; title: string; periods: number; topics: Topic[] };
type Tree = Record<string, Unit[]>;
type Prog = {
  topics: Record<string, { status: string; mastery: number; doubts_count: number; due: boolean }>;
  summary: Record<string, { total: number; mastered: number }>;
  due_for_revision: string[];
};
type Msg = { role: "user" | "assistant"; content: string; sources?: Source[] };
type QuizItem = { q: string; options: string[]; answer: number; explanation: string };

export default function Home() {
  const [tree, setTree] = useState<Tree>({});
  const [grade, setGrade] = useState("XI");
  const [topic, setTopic] = useState<{ id: string; title: string; unit: string } | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [prog, setProg] = useState<Prog | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [quiz, setQuiz] = useState<{ items: QuizItem[]; picks: (number | null)[]; done: boolean } | null>(null);
  const [error, setError] = useState("");
  const speaker = useRef<Speaker | null>(null);
  const abort = useRef<AbortController | null>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    speaker.current = new Speaker(setSpeaking);
  }, []);
  useEffect(() => {
    if (speaker.current) speaker.current.muted = muted;
    if (muted) speaker.current?.stop();
  }, [muted]);

  // bootstrap: curriculum + student
  useEffect(() => {
    (async () => {
      try {
        setTree(await getJSON<Tree>("/curriculum"));
        let id = Number(localStorage.getItem("studentId") || 0);
        if (!id) {
          id = (await postJSON<{ id: number }>("/students", { name: "Student" })).id;
          localStorage.setItem("studentId", String(id));
        }
        setStudentId(id);
      } catch {
        setError("Can't reach the backend. Is it running on the URL in NEXT_PUBLIC_API_URL?");
      }
    })();
  }, []);

  const refreshProgress = useCallback(async () => {
    if (studentId) setProg(await getJSON<Prog>(`/students/${studentId}/progress`));
  }, [studentId]);
  useEffect(() => { refreshProgress(); }, [refreshProgress]);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, quiz]);

  const pct = useMemo(() => {
    const s = prog?.summary?.[grade];
    return s && s.total ? Math.round((100 * s.mastered) / s.total) : 0;
  }, [prog, grade]);

  function pickTopic(t: Topic, unit: string) {
    abort.current?.abort();
    speaker.current?.stop();
    setTopic({ id: t.id, title: t.title, unit });
    setMsgs([]);
    setQuiz(null);
    setBusy(false);
  }

  /** Stream an assistant reply into the chat while the avatar speaks it. */
  async function run(path: string, body: unknown) {
    setBusy(true);
    setError("");
    speaker.current?.stop();
    abort.current = new AbortController();
    setMsgs((m) => [...m, { role: "assistant", content: "" }]);
    try {
      await streamPost(
        path,
        body,
        (chunk) => {
          speaker.current?.feed(chunk);
          setMsgs((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, content: last.content + chunk };
            return copy;
          });
        },
        (sources) =>
          setMsgs((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { ...copy[copy.length - 1], sources };
            return copy;
          }),
        abort.current.signal,
      );
      speaker.current?.flush();
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(String(e.message || e));
    } finally {
      setBusy(false);
      refreshProgress();
    }
  }

  function teach() {
    if (!topic || !studentId) return;
    setMsgs([]);
    setQuiz(null);
    run("/lesson", { student_id: studentId, topic_id: topic.id });
  }

  function ask(question: string) {
    if (!topic || !studentId || !question.trim() || busy) return;
    const history = msgs.filter((m) => m.content).map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: question }]);
    setInput("");
    run("/ask", { student_id: studentId, topic_id: topic.id, question, history });
  }

  async function startQuiz() {
    if (!topic) return;
    setBusy(true);
    setError("");
    try {
      const { items } = await postJSON<{ items: QuizItem[] }>("/quiz", { topic_id: topic.id, n: 3 });
      setQuiz({ items, picks: items.map(() => null), done: false });
    } catch (e: any) {
      setError("Couldn't build a quick check yet. Has course material been ingested for this topic?");
    } finally {
      setBusy(false);
    }
  }

  async function submitQuiz() {
    if (!quiz || !topic || !studentId) return;
    const score = quiz.items.filter((it, i) => quiz.picks[i] === it.answer).length;
    setQuiz({ ...quiz, done: true });
    await postJSON("/quiz/submit", { student_id: studentId, topic_id: topic.id, score, total: quiz.items.length });
    refreshProgress();
  }

  async function mark(status: string) {
    if (!topic || !studentId) return;
    await postJSON(`/students/${studentId}/status`, { topic_id: topic.id, status });
    refreshProgress();
  }

  function mic() {
    if (listening) return;
    speaker.current?.stop();
    setListening(true);
    listenOnce((text) => ask(text), () => setListening(false));
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Chemistry Tutor</h1>
        <div className="tabs">
          {Object.keys(tree).map((g) => (
            <button key={g} className={g === grade ? "active" : ""} onClick={() => setGrade(g)}>
              Class {g}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>
          Mastered {prog?.summary?.[grade]?.mastered ?? 0} / {prog?.summary?.[grade]?.total ?? 0} topics ({pct}%)
        </div>
        <div className="bar"><i style={{ width: `${pct}%` }} /></div>
        {(prog?.due_for_revision?.length ?? 0) > 0 && (
          <div style={{ fontSize: 13, marginBottom: 10, color: "var(--warn)" }}>
            {prog!.due_for_revision.length} topic(s) due for revision
          </div>
        )}
        {(tree[grade] || []).map((u) => (
          <details key={u.unit_no}>
            <summary>{u.unit_no}. {u.title}</summary>
            {u.topics.map((t) => {
              const p = prog?.topics?.[t.id];
              return (
                <div key={t.id} className={`topic ${topic?.id === t.id ? "sel" : ""}`} onClick={() => pickTopic(t, u.title)}>
                  <span className={`dot ${p?.status ?? ""}`} />
                  <span>{t.title}{p?.due ? " ↻" : ""}</span>
                </div>
              );
            })}
          </details>
        ))}
      </aside>

      <main className="main">
        <div className="stage">
          <Avatar speaking={speaking} listening={listening} />
          <div style={{ flex: 1 }}>
            <h2>{topic ? topic.title : "Pick a topic to begin"}</h2>
            <div className="sub">{topic ? topic.unit : "Dr. Asha will teach it and answer your doubts."}</div>
            <div className="actions">
              <button className="primary" disabled={!topic || busy} onClick={teach}>Teach me this</button>
              <button disabled={!topic || busy} onClick={startQuiz}>Quick check</button>
              <button disabled={!topic} onClick={() => mark("mastered")}>I understood this</button>
              <button disabled={!topic} onClick={() => mark("needs_revision")}>Needs revision</button>
              <button onClick={() => setMuted((m) => !m)}>{muted ? "Unmute" : "Mute"}</button>
              {speaking && <button onClick={() => speaker.current?.stop()}>Stop talking</button>}
            </div>
          </div>
        </div>

        <div className="chat">
          {error && <div className="msg" style={{ borderColor: "var(--bad)" }}>{error}</div>}
          {!msgs.length && !quiz && <div className="empty">Choose "Teach me this" or type a doubt below.</div>}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <Markdown>{m.content || "…"}</Markdown>
              {m.sources && m.sources.length > 0 && (
                <div className="sources">
                  Sources: {m.sources.map((s) => `[${s.n}] ${s.source}${s.page ? ` p.${s.page}` : ""}`).join("  ·  ")}
                </div>
              )}
            </div>
          ))}
          {quiz && (
            <div className="quiz">
              <strong>Quick check</strong>
              {quiz.items.map((it, qi) => (
                <div key={qi} style={{ marginTop: 12 }}>
                  <Markdown>{`${qi + 1}. ${it.q}`}</Markdown>
                  {it.options.map((o, oi) => {
                    const cls = quiz.done ? (oi === it.answer ? "right" : quiz.picks[qi] === oi ? "wrong" : "") : "";
                    return (
                      <label key={oi} className={cls}>
                        <input type="radio" name={`q${qi}`} disabled={quiz.done} checked={quiz.picks[qi] === oi}
                          onChange={() => setQuiz({ ...quiz, picks: quiz.picks.map((p, i) => (i === qi ? oi : p)) })} />{" "}
                        {o}
                      </label>
                    );
                  })}
                  {quiz.done && <div className="sources"><Markdown>{it.explanation}</Markdown></div>}
                </div>
              ))}
              {!quiz.done && (
                <button className="primary" style={{ marginTop: 12 }} disabled={quiz.picks.some((p) => p === null)} onClick={submitQuiz}>
                  Submit
                </button>
              )}
              {quiz.done && (
                <div style={{ marginTop: 10 }}>
                  Score: {quiz.items.filter((it, i) => quiz.picks[i] === it.answer).length} / {quiz.items.length}
                </div>
              )}
            </div>
          )}
          <div ref={chatEnd} />
        </div>

        <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
          <button type="button" onClick={mic} disabled={!topic || busy} title="Ask by voice">
            {listening ? "Listening…" : "🎤"}
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={topic ? "Ask a doubt about this topic…" : "Pick a topic first"}
            disabled={!topic}
          />
          <button className="primary" disabled={!topic || busy || !input.trim()}>Ask</button>
        </form>
      </main>
    </div>
  );
}
