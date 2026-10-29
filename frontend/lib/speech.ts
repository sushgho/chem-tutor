/** Sentence-by-sentence text-to-speech so the teacher starts talking while the
 *  answer is still streaming. Uses the browser's speechSynthesis; swap `speak`
 *  for a cloud TTS (ElevenLabs, Azure, Cartesia...) to get better voices and
 *  real viseme data for lip-sync. */

export function cleanForSpeech(s: string): string {
  return s
    .replace(/```mermaid[\s\S]*?```/gi, " ")
    .replace(/```[\s\S]*?```/g, " code example omitted ")
    .replace(/\$\$[\s\S]*?\$\$/g, " the equation shown ")
    .replace(/\$[^$]*\$/g, " the formula shown ")
    .replace(/\[\d+\]/g, "")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_#`>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export class Speaker {
  private buffer = "";
  private lineBuffer = "";
  private pending = 0;
  private inMermaidDiagram = false;
  muted = false;

  constructor(private onSpeaking: (speaking: boolean) => void) {}

  feed(chunk: string) {
    this.lineBuffer += chunk;
    const lines = this.lineBuffer.split("\n");
    this.lineBuffer = lines.pop() ?? "";
    lines.forEach((line) => this.processLine(line));
  }

  flush() {
    if (this.lineBuffer) this.processLine(this.lineBuffer);
    this.lineBuffer = "";
    if (this.buffer.trim()) this.speak(this.buffer);
    this.buffer = "";
  }

  speakNow(text: string): boolean {
    if (typeof window === "undefined" || !window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") {
      return false;
    }

    this.stop();
    const clean = cleanForSpeech(text);
    if (!clean || this.muted) return false;

    window.speechSynthesis.resume();
    const parts = clean.match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [clean];
    parts.forEach((part) => this.speak(part));
    return true;
  }

  stop() {
    this.buffer = "";
    this.lineBuffer = "";
    this.inMermaidDiagram = false;
    this.pending = 0;
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    this.onSpeaking(false);
  }

  private speak(text: string) {
    const clean = cleanForSpeech(text);
    if (this.muted || !clean || typeof window === "undefined" || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(clean);
    u.rate = 1;
    u.onstart = () => this.onSpeaking(true);
    const done = () => {
      this.pending = Math.max(0, this.pending - 1);
      if (this.pending === 0) this.onSpeaking(false);
    };
    u.onend = done;
    u.onerror = done;
    this.pending += 1;
    window.speechSynthesis.speak(u);
  }

  private processLine(line: string) {
    const fence = line.match(/^\s*```(.*)$/);
    if (fence) {
      const language = fence[1].trim().toLowerCase();
      if (this.inMermaidDiagram) {
        this.inMermaidDiagram = false;
      } else if (language === "mermaid") {
        this.inMermaidDiagram = true;
      } else {
        this.buffer += `${line}\n`;
      }
      return;
    }
    if (!this.inMermaidDiagram) {
      this.buffer += `${line}\n`;
      const parts = this.buffer.split(/(?<=[.!?])\s+/);
      this.buffer = parts.pop() ?? "";
      parts.forEach((part) => this.speak(part));
    }
  }
}

/** Voice input via the Web Speech API (Chrome/Edge/Safari). */
export function listenOnce(onResult: (text: string) => void, onEnd: () => void) {
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!SR) {
    alert("Voice input isn't supported in this browser. Try Chrome or Edge.");
    onEnd();
    return null;
  }
  const rec = new SR();
  rec.lang = "en-IN";
  rec.interimResults = false;
  rec.onresult = (e: any) => onResult(e.results[0][0].transcript);
  rec.onend = onEnd;
  rec.onerror = onEnd;
  rec.start();
  return rec;
}
