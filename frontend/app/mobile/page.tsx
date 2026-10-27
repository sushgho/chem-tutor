"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Avatar from "@/components/Avatar";
import Markdown from "@/components/Markdown";
import { getJSON, postJSON, streamPost, type Source } from "@/lib/api";
import { listenOnce, Speaker } from "@/lib/speech";
import styles from "./mobile-teacher-app.module.css";

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
type QuizState = { items: QuizItem[]; picks: (number | null)[]; done: boolean };

export default function MobileTeacherApp() {
  const [tree, setTree] = useState<Tree>({});
  const [grade, setGrade] = useState("XI");
  const [unitNo, setUnitNo] = useState<number | null>(null);
  const [topic, setTopic] = useState<{ id: string; title: string; unit: string } | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [prog, setProg] = useState<Prog | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [quiz, setQuiz] = useState<QuizState | null>(null);
  const [error, setError] = useState("");
  const speaker = useRef<Speaker | null>(null);
  const abort = useRef<AbortController | null>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  const units = tree[grade] || [];
  const selectedUnit = units.find((unit) => unit.unit_no === unitNo) ?? null;
  const selectedTopic = selectedUnit?.topics.find((item) => item.id === topic?.id) ?? null;

  useEffect(() => {
    const activeSpeaker = new Speaker(setSpeaking);
    speaker.current = activeSpeaker;
    return () => {
      activeSpeaker.stop();
      abort.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (speaker.current) speaker.current.muted = muted;
    if (muted) speaker.current?.stop();
  }, [muted]);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const curriculum = await getJSON<Tree>("/curriculum");
        if (!active) return;
        setTree(curriculum);
        const storedId = Number(localStorage.getItem("studentId") || 0);
        const id =
          Number.isInteger(storedId) && storedId > 0
            ? storedId
            : (await postJSON<{ id: number }>("/students", { name: "Student" })).id;
        if (!active) return;
        localStorage.setItem("studentId", String(id));
        setStudentId(id);
      } catch {
        if (active) setError("Can't reach the tutor service. Check your internet connection and try again.");
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const refreshProgress = useCallback(async () => {
    if (!studentId) return;
    try {
      setProg(await getJSON<Prog>(`/students/${studentId}/progress`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load your learning progress.");
    }
  }, [studentId]);

  useEffect(() => {
    void refreshProgress();
  }, [refreshProgress]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, quiz]);

  useEffect(() => {
    if (!units.length) {
      setUnitNo(null);
      return;
    }
    if (unitNo === null || !units.some((unit) => unit.unit_no === unitNo)) {
      setUnitNo(units[0].unit_no);
    }
  }, [units, unitNo]);

  const progress = useMemo(() => {
    const summary = prog?.summary?.[grade];
    return {
      mastered: summary?.mastered ?? 0,
      total: summary?.total ?? 0,
      percent: summary?.total ? Math.round((100 * summary.mastered) / summary.total) : 0,
      due: prog?.due_for_revision?.length ?? 0,
    };
  }, [grade, prog]);

  function chooseTopic(item: Topic | undefined) {
    abort.current?.abort();
    speaker.current?.stop();
    setTopic(item && selectedUnit ? { id: item.id, title: item.title, unit: selectedUnit.title } : null);
    setMsgs([]);
    setQuiz(null);
    setBusy(false);
    setError("");
  }

  async function run(path: string, body: unknown) {
    setBusy(true);
    setError("");
    speaker.current?.stop();
    const controller = new AbortController();
    abort.current = controller;
    setMsgs((current) => [...current, { role: "assistant", content: "" }]);
    try {
      await streamPost(
        path,
        body,
        (chunk) => {
          speaker.current?.feed(chunk);
          setMsgs((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + chunk };
            return next;
          });
        },
        (sources) => {
          setMsgs((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, sources };
            return next;
          });
        },
        controller.signal,
      );
      speaker.current?.flush();
    } catch (e) {
      if (!(e instanceof Error && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : "The tutor couldn't complete that request.");
      }
    } finally {
      if (abort.current === controller) {
        abort.current = null;
        setBusy(false);
        void refreshProgress();
      }
    }
  }

  function teach() {
    if (!topic || !studentId || busy) return;
    setMsgs([]);
    setQuiz(null);
    void run("/lesson", { student_id: studentId, topic_id: topic.id });
  }

  function ask(question: string) {
    if (!topic || !studentId || !question.trim() || busy) return;
    const history = msgs.filter((message) => message.content).map(({ role, content }) => ({ role, content }));
    setMsgs((current) => [...current, { role: "user", content: question.trim() }]);
    setInput("");
    void run("/ask", { student_id: studentId, topic_id: topic.id, question: question.trim(), history });
  }

  async function startQuiz() {
    if (!topic || busy) return;
    setBusy(true);
    setError("");
    try {
      const { items } = await postJSON<{ items: QuizItem[] }>("/quiz", { topic_id: topic.id, n: 3 });
      setQuiz({ items, picks: items.map(() => null), done: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't create a quick check for this topic.");
    } finally {
      setBusy(false);
    }
  }

  async function submitQuiz() {
    if (!quiz || !topic || !studentId) return;
    const score = quiz.items.filter((item, index) => quiz.picks[index] === item.answer).length;
    try {
      await postJSON("/quiz/submit", {
        student_id: studentId,
        topic_id: topic.id,
        score,
        total: quiz.items.length,
      });
      setQuiz({ ...quiz, done: true });
      await refreshProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save your quiz result.");
    }
  }

  async function mark(status: "mastered" | "needs_revision") {
    if (!topic || !studentId) return;
    try {
      await postJSON(`/students/${studentId}/status`, { topic_id: topic.id, status });
      await refreshProgress();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't update your topic progress.");
    }
  }

  function startListening() {
    if (!topic || busy || listening) return;
    speaker.current?.stop();
    setListening(true);
    listenOnce(ask, () => setListening(false));
  }

  return (
    <main className={styles.app}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>DR. ASHA · CLASS XI–XII</p>
          <h1>Mobile Teacher App</h1>
        </div>
        <button className={styles.soundButton} onClick={() => setMuted((value) => !value)} aria-label={muted ? "Turn voice on" : "Mute voice"}>
          {muted ? "Sound off" : "Sound on"}
        </button>
      </header>

      <section className={styles.controls} aria-label="Choose a chemistry topic">
        <div className={styles.gradeTabs} role="group" aria-label="Choose class">
          {Object.keys(tree).map((className) => (
            <button
              key={className}
              className={grade === className ? styles.activeTab : ""}
              onClick={() => {
                setGrade(className);
                setUnitNo(null);
                chooseTopic(undefined);
              }}
            >
              Class {className}
            </button>
          ))}
        </div>
        <label>
          <span>Unit</span>
          <select
            value={unitNo ?? ""}
            onChange={(event) => {
              setUnitNo(Number(event.target.value));
              chooseTopic(undefined);
            }}
            disabled={!units.length}
          >
            {!units.length && <option value="">Loading units…</option>}
            {units.map((unit) => (
              <option key={unit.unit_no} value={unit.unit_no}>
                {unit.unit_no}. {unit.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Topic</span>
          <select
            value={selectedTopic?.id ?? ""}
            onChange={(event) => chooseTopic(selectedUnit?.topics.find((item) => item.id === event.target.value))}
            disabled={!selectedUnit}
          >
            <option value="">Choose a topic</option>
            {selectedUnit?.topics.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className={styles.progress} aria-label="Learning progress">
        <div className={styles.progressText}>
          <span>Class {grade} progress</span>
          <strong>{progress.mastered}/{progress.total} topics · {progress.percent}%</strong>
        </div>
        <div className={styles.progressTrack}>
          <div style={{ width: `${progress.percent}%` }} />
        </div>
        {progress.due > 0 && <p>{progress.due} topic(s) due for revision</p>}
      </section>

      <section className={styles.teacherCard}>
        <Avatar speaking={speaking} listening={listening} />
        <div className={styles.teacherInfo}>
          <p className={styles.eyebrow}>{listening ? "LISTENING…" : speaking ? "SPEAKING…" : "YOUR CHEMISTRY TEACHER"}</p>
          <h2>{topic?.title ?? "Choose a topic to begin"}</h2>
          <p>{topic?.unit ?? "Learn a lesson, ask a doubt, or take a quick check."}</p>
        </div>
      </section>

      <div className={styles.actions}>
        <button className={styles.primary} onClick={teach} disabled={!topic || !studentId || busy}>Teach me</button>
        <button onClick={() => void startQuiz()} disabled={!topic || busy}>Quick check</button>
        <button onClick={() => void mark("mastered")} disabled={!topic || !studentId}>I understood</button>
        <button onClick={() => void mark("needs_revision")} disabled={!topic || !studentId}>Review later</button>
        {speaking && <button onClick={() => speaker.current?.stop()}>Stop voice</button>}
      </div>

      <section className={styles.conversation} aria-label="Tutor conversation" aria-live="polite">
        {error && <div className={styles.error} role="alert">{error}</div>}
        {!msgs.length && !quiz && (
          <p className={styles.empty}>Choose a topic, then tap <strong>Teach me</strong> or ask your first question.</p>
        )}
        {msgs.map((message, index) => (
          <article key={index} className={`${styles.message} ${message.role === "user" ? styles.userMessage : ""}`}>
            <span className={styles.messageRole}>{message.role === "user" ? "You" : "Dr. Asha"}</span>
            <Markdown>{message.content || "…"}</Markdown>
            {message.sources && message.sources.length > 0 && (
              <p className={styles.sources}>
                Sources: {message.sources.map((source) => `[${source.n}] ${source.source}${source.page ? ` p.${source.page}` : ""}`).join(" · ")}
              </p>
            )}
          </article>
        ))}
        {quiz && (
          <section className={styles.quiz} aria-label="Quick check quiz">
            <h3>Quick check</h3>
            {quiz.items.map((item, questionIndex) => (
              <fieldset key={questionIndex} className={styles.question}>
                <legend><Markdown>{`${questionIndex + 1}. ${item.q}`}</Markdown></legend>
                {item.options.map((option, optionIndex) => {
                  const correct = quiz.done && optionIndex === item.answer;
                  const incorrect = quiz.done && quiz.picks[questionIndex] === optionIndex && !correct;
                  return (
                    <label key={optionIndex} className={correct ? styles.correct : incorrect ? styles.incorrect : ""}>
                      <input
                        type="radio"
                        name={`mobile-question-${questionIndex}`}
                        checked={quiz.picks[questionIndex] === optionIndex}
                        disabled={quiz.done}
                        onChange={() =>
                          setQuiz({
                            ...quiz,
                            picks: quiz.picks.map((pick, index) => index === questionIndex ? optionIndex : pick),
                          })
                        }
                      />
                      {option}
                    </label>
                  );
                })}
                {quiz.done && <div className={styles.explanation}><Markdown>{item.explanation}</Markdown></div>}
              </fieldset>
            ))}
            {!quiz.done ? (
              <button
                className={styles.primary}
                disabled={quiz.picks.some((pick) => pick === null)}
                onClick={() => void submitQuiz()}
              >
                Submit answers
              </button>
            ) : (
              <strong>Score: {quiz.items.filter((item, index) => quiz.picks[index] === item.answer).length} / {quiz.items.length}</strong>
            )}
          </section>
        )}
        <div ref={chatEnd} />
      </section>

      <form className={styles.composer} onSubmit={(event) => { event.preventDefault(); ask(input); }}>
        <button type="button" onClick={startListening} disabled={!topic || busy} aria-label="Ask by voice">
          {listening ? "Listening…" : "🎤"}
        </button>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={topic ? "Ask a question…" : "Choose a topic first"}
          aria-label="Your question"
          disabled={!topic || busy}
        />
        <button className={styles.primary} disabled={!topic || !input.trim() || busy}>Send</button>
      </form>
    </main>
  );
}
