"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import Markdown from "@/components/Markdown";
import { deleteJSON, getJSON, postJSON, streamPost, uploadFile, type Source } from "@/lib/api";
import { listenOnce, Speaker } from "@/lib/speech";
import styles from "./mobile-teacher-app.module.css";

type Subject = "maths" | "physics" | "chemistry" | "biology";
type StudyMode = "chat" | "lesson" | "check" | "summary" | "important_questions" | "neet" | "jee";
type StudyDocument = { id: number; filename: string; created_at: string };
type Topic = { id: string; title: string };
type Unit = { unit_no: number; title: string; periods: number; topics: Topic[] };
type ChapterChoice = { chapter_no: number; title: string };
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
  const [subject, setSubject] = useState<Subject>("chemistry");
  const [grade, setGrade] = useState("XI");
  const [unitNo, setUnitNo] = useState<number | null>(null);
  const [topic, setTopic] = useState<{ id: string; title: string; unit: string } | null>(null);
  const [chapterTopic, setChapterTopic] = useState("");
  const [chapterChoices, setChapterChoices] = useState<ChapterChoice[]>([]);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [libraryKey, setLibraryKey] = useState("");
  const [prog, setProg] = useState<Prog | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [muted, setMuted] = useState(false);
  const [quiz, setQuiz] = useState<QuizState | null>(null);
  const [documents, setDocuments] = useState<StudyDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const speaker = useRef<Speaker | null>(null);
  const abort = useRef<AbortController | null>(null);
  const chatEnd = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const units = tree[grade] || [];
  const selectedUnit = units.find((unit) => unit.unit_no === unitNo) ?? null;
  const selectedTopic = selectedUnit?.topics.find((item) => item.id === topic?.id) ?? null;
  const subjectName = subject === "maths" ? "Maths" : subject[0].toUpperCase() + subject.slice(1);
  const activeTopicTitle = subject === "chemistry" ? topic?.title ?? "" : chapterTopic.trim();

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
        const key = localStorage.getItem("studyLibraryKey") || crypto.randomUUID();
        localStorage.setItem("studyLibraryKey", key);
        setLibraryKey(key);
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

  const refreshDocuments = useCallback(async (isActive: () => boolean = () => true) => {
    if (!studentId) return;
    try {
      const { documents: items } = await getJSON<{ documents: StudyDocument[] }>(
        `/students/${studentId}/documents?subject=${subject}`,
        { "X-Study-Library-Key": libraryKey },
      );
      if (isActive()) setDocuments(items);
    } catch (e) {
      if (isActive()) {
        setError(e instanceof Error ? e.message : "Couldn't load your uploaded study materials.");
      }
    }
  }, [studentId, subject, libraryKey]);

  useEffect(() => {
    let active = true;
    setDocuments([]);
    void refreshDocuments(() => active);
    return () => {
      active = false;
    };
  }, [refreshDocuments]);

  useEffect(() => {
    let active = true;
    setChapterChoices([]);
    setChapterTopic("");
    if (subject === "chemistry") return () => { active = false; };
    void getJSON<{ chapters: ChapterChoice[] }>(
      `/study/chapters?subject=${subject}&grade=${grade}`,
    ).then(({ chapters }) => {
      if (active) setChapterChoices(chapters);
    }).catch((e: unknown) => {
      if (active) setError(e instanceof Error ? e.message : "Couldn't load the chapter list.");
    });
    return () => { active = false; };
  }, [subject, grade]);

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

  function chooseSubject(nextSubject: Subject) {
    abort.current?.abort();
    speaker.current?.stop();
    setSubject(nextSubject);
    setTopic(null);
    setChapterTopic("");
    setMsgs([]);
    setQuiz(null);
    setBusy(false);
    setError("");
  }

  async function run(path: string, body: unknown, studyKey?: string) {
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
        studyKey ? { "X-Study-Library-Key": studyKey } : undefined,
      );
      speaker.current?.flush();
    } catch (e) {
      if (!(e instanceof Error && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : "The tutor couldn't complete that request.");
        setMsgs((current) => {
          const last = current[current.length - 1];
          return last?.role === "assistant" && !last.content ? current.slice(0, -1) : current;
        });
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
    if (!studentId || busy) return;
    if (subject === "chemistry" && topic) {
      setMsgs([]);
      setQuiz(null);
      void run("/lesson", { student_id: studentId, topic_id: topic.id });
      return;
    }
    if (!activeTopicTitle) {
      setError("Choose or enter a chapter or topic for DIVA to teach.");
      return;
    }
    ask(
      `Teach me the chapter or topic "${activeTopicTitle}" with a clear explanation and an example, then ask me one question and wait for my answer.`,
      "lesson",
      activeTopicTitle,
    );
  }

  function startStudyCheck() {
    if (!studentId || busy) return;
    if (subject === "chemistry" && topic) {
      void startQuiz();
      return;
    }
    if (!activeTopicTitle) {
      setError("Choose or enter a chapter or topic for DIVA to check.");
      return;
    }
    ask(`Ask me one short question about "${activeTopicTitle}" without giving me the answer.`, "check", activeTopicTitle);
  }

  function ask(question: string, mode: StudyMode = "chat", topicTitle = activeTopicTitle) {
    if (!studentId || !question.trim() || busy) return;
    const history = msgs.filter((message) => message.content).slice(-12)
      .map(({ role, content }) => ({ role, content }));
    setQuiz(null);
    setMsgs((current) => [...current, { role: "user", content: question.trim() }]);
    setInput("");
    void run("/study/chat", {
      student_id: studentId,
      subject,
      grade,
      topic_id: subject === "chemistry" ? topic?.id ?? null : null,
      topic_title: topicTitle || null,
      question: question.trim(),
      mode,
      history,
    }, libraryKey);
  }

  function runStudyMode(mode: Exclude<StudyMode, "chat">, prompt: string) {
    ask(prompt, mode);
  }

  async function uploadStudyFile(file?: File) {
    if (!file || !studentId || uploading) return;
    if (file.size > 12 * 1024 * 1024) {
      setError("Files must be 12 MB or smaller.");
      if (fileInput.current) fileInput.current.value = "";
      return;
    }
    setUploading(true);
    setError("");
    const form = new FormData();
    form.append("subject", subject);
    form.append("file", file);
    try {
      const saved = await uploadFile<StudyDocument & { chunks: number }>(
        `/students/${studentId}/documents`,
        form,
        { "X-Study-Library-Key": libraryKey },
      );
      setDocuments((current) => [saved, ...current]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't process this document.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeStudyFile(documentId: number) {
    if (!studentId) return;
    try {
      await deleteJSON(
        `/students/${studentId}/documents/${documentId}`,
        { "X-Study-Library-Key": libraryKey },
      );
      setDocuments((current) => current.filter((item) => item.id !== documentId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't delete this study document.");
    }
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
    if (!studentId || busy || listening) return;
    speaker.current?.stop();
    setListening(true);
    listenOnce(ask, () => setListening(false));
  }

  function speakMessage(text: string) {
    if (muted && speaker.current) {
      speaker.current.muted = false;
      setMuted(false);
    }
    if (!speaker.current?.speakNow(text)) {
      setError("Voice playback isn't available in this browser. Try Chrome, Edge, or Safari.");
    }
  }

  return (
    <main className={styles.app}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>DIVA · MULTI-SUBJECT TUTOR</p>
          <h1>Mobile Teacher App</h1>
        </div>
        <button className={styles.soundButton} onClick={() => setMuted((value) => !value)} aria-label={muted ? "Turn voice on" : "Mute voice"}>
          {muted ? "Sound off" : "Sound on"}
        </button>
      </header>

      <section className={styles.subjectSection} aria-label="Choose a subject">
        <div className={styles.subjectTabs} role="group" aria-label="Subjects">
          {([
            ["maths", "Maths"],
            ["physics", "Physics"],
            ["chemistry", "Chemistry"],
            ["biology", "Biology"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              className={subject === id ? styles.activeSubject : ""}
              aria-pressed={subject === id}
              disabled={uploading}
              onClick={() => chooseSubject(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className={styles.gradeTabs} role="group" aria-label="Choose class">
          {Object.keys(tree).map((className) => (
            <button
              key={className}
              className={grade === className ? styles.activeTab : ""}
              aria-pressed={grade === className}
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
      </section>

      {subject === "chemistry" && (
        <section className={styles.controls} aria-label="Choose a chemistry topic">
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
            <span>Topic (optional)</span>
            <select
              value={selectedTopic?.id ?? ""}
              onChange={(event) => chooseTopic(selectedUnit?.topics.find((item) => item.id === event.target.value))}
              disabled={!selectedUnit}
            >
              <option value="">Ask across Chemistry</option>
              {selectedUnit?.topics.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
        </section>
      )}
      {subject !== "chemistry" && (
        <section className={styles.topicEntry} aria-label={`Choose a ${subjectName} chapter or topic`}>
          <label>
            <span>Chapter</span>
            <select
              value={chapterChoices.some((item) => item.title === chapterTopic) ? chapterTopic : ""}
              onChange={(event) => setChapterTopic(event.target.value)}
              aria-label={`${subjectName} chapter`}
            >
              <option value="">
                {chapterChoices.length ? "Choose a chapter" : "No shared chapters indexed for this class"}
              </option>
              {chapterChoices.map((item) => (
                <option key={`${item.chapter_no}-${item.title}`} value={item.title}>
                  {item.chapter_no}. {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Or enter another topic</span>
            <input
              value={chapterChoices.some((item) => item.title === chapterTopic) ? "" : chapterTopic}
              onChange={(event) => setChapterTopic(event.target.value)}
              placeholder={
                subject === "maths" ? "e.g., Quadratic equations" :
                  subject === "physics" ? "e.g., Laws of motion" : "e.g., Cell structure"
              }
              maxLength={160}
              aria-label={`${subjectName} chapter or topic`}
            />
          </label>
        </section>
      )}

      {subject === "chemistry" && (
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
      )}

      <section className={styles.teacherCard}>
        <Image
          className={styles.teacherPortrait}
          src="/images/teacher-asha.png"
          alt="DIVA, your science teacher, in a classroom"
          width={160}
          height={160}
          priority
        />
        <div className={styles.teacherInfo}>
          <p className={styles.eyebrow}>{listening ? "LISTENING…" : speaking ? "SPEAKING…" : `${subjectName.toUpperCase()} TUTOR`}</p>
          <h2>{topic?.title ?? (chapterTopic.trim() || `Ready to study ${subjectName}`)}</h2>
          <p>{topic?.unit ?? (chapterTopic.trim() ? "Chapter or topic" : "Ask a question, upload notes, or practise for NEET/JEE.")}</p>
        </div>
      </section>

      <div className={styles.studyTools} aria-label="Study tools">
        <button onClick={() => runStudyMode("summary", "Summarize my uploaded study materials.")} disabled={!studentId || busy}>Summarize notes</button>
        <button onClick={() => runStudyMode("important_questions", "Give me the most important revision questions and answers.")} disabled={!studentId || busy}>Important questions</button>
        {subject !== "maths" && (
          <button onClick={() => runStudyMode("neet", "Create a practice set for my selected subject.")} disabled={!studentId || busy}>NEET practice</button>
        )}
        {subject !== "biology" && (
          <button onClick={() => runStudyMode("jee", "Create a practice set for my selected subject.")} disabled={!studentId || busy}>JEE practice</button>
        )}
        {subject === "chemistry" && (
          <>
            <button className={styles.primary} onClick={teach} disabled={!topic || !studentId || busy}>Teach topic</button>
            <button onClick={startStudyCheck} disabled={!topic || busy}>Quick check</button>
            <button onClick={() => void mark("mastered")} disabled={!topic || !studentId}>I understood</button>
            <button onClick={() => void mark("needs_revision")} disabled={!topic || !studentId}>Review later</button>
          </>
        )}
        {subject !== "chemistry" && (
          <>
            <button className={styles.primary} onClick={teach} disabled={!activeTopicTitle || !studentId || busy}>Teach topic</button>
            <button onClick={startStudyCheck} disabled={!activeTopicTitle || !studentId || busy}>Quick check</button>
          </>
        )}
        {speaking && <button onClick={() => speaker.current?.stop()}>Stop voice</button>}
      </div>

      <section className={styles.uploadPanel} aria-label={`${subjectName} study materials`}>
        <div className={styles.uploadHeader}>
          <div>
            <strong>Your {subjectName} materials</strong>
            <span>PDF or TXT · saved with this browser profile</span>
          </div>
          <input
            ref={fileInput}
            className={styles.fileInput}
            type="file"
            accept=".pdf,.txt,application/pdf,text/plain"
            onChange={(event) => void uploadStudyFile(event.target.files?.[0])}
            aria-label={`Upload ${subjectName} study document`}
          />
          <button type="button" onClick={() => fileInput.current?.click()} disabled={!studentId || uploading}>
            {uploading ? "Reading…" : "Upload"}
          </button>
        </div>
        {documents.length > 0 && (
          <ul className={styles.documentList}>
            {documents.map((document) => (
              <li key={document.id}>
                <span title={document.filename}>{document.filename}</span>
                <button type="button" onClick={() => void removeStudyFile(document.id)} aria-label={`Delete ${document.filename}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className={styles.uploadNote}>DIVA searches these materials and cites them when available. Upload past papers for exact questions; generated exam practice is clearly labeled. Scanned PDFs need OCR. Clearing browser data removes access to saved files.</p>
      </section>

      <section className={styles.conversation} aria-label="Tutor conversation" aria-live="polite">
        {error && <div className={styles.error} role="alert">{error}</div>}
        {!msgs.length && !quiz && (
          <p className={styles.empty}>
            {subject === "chemistry"
              ? `Choose a chapter topic to start a lesson, or ask DIVA anything about ${subjectName}.`
              : `Enter a chapter or topic, then choose Teach topic or Quick check. You can also ask DIVA anything about ${subjectName}.`}
            {" Upload notes for material-specific explanations and citations."}
          </p>
        )}
        {msgs.map((message, index) => (
          <article key={index} className={`${styles.message} ${message.role === "user" ? styles.userMessage : ""}`}>
            <span className={styles.messageRole}>{message.role === "user" ? "You" : "DIVA"}</span>
            {message.role === "assistant" && message.content && !busy && (
              <button className={styles.listenButton} type="button" onClick={() => speakMessage(message.content)}>
                Listen
              </button>
            )}
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
        <button type="button" onClick={startListening} disabled={!studentId || busy} aria-label="Ask by voice">
          {listening ? "Listening…" : "🎤"}
        </button>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={`Ask about ${subjectName}…`}
          aria-label="Your question"
          disabled={!studentId || busy}
        />
        <button className={styles.primary} disabled={!studentId || !input.trim() || busy}>Send</button>
      </form>
    </main>
  );
}
