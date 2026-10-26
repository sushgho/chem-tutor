/** Sentence-by-sentence text-to-speech so the teacher starts talking while the
 *  answer is still streaming. Uses the browser's speechSynthesis; swap `speak`
 *  for a cloud TTS (ElevenLabs, Azure, Cartesia...) to get better voices and
 *  real viseme data for lip-sync. */

export function cleanForSpeech(s: string): string {
  return s
    .replace(/\$\$[\s\S]*?\$\$/g, " the equation shown ")
    .replace(/\$[^$]*\$/g, " the formula shown ")
    .replace(/\[\d+\]/g, "")
    .replace(/[*_#`>]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export class Speaker {
  private buffer = "";
  private pending = 0;
  muted = false;

  constructor(private onSpeaking: (speaking: boolean) => void) {}

  feed(chunk: string) {
    this.buffer += chunk;
    const parts = this.buffer.split(/(?<=[.!?])\s+/);
    this.buffer = parts.pop() ?? "";
    parts.forEach((p) => this.speak(p));
  }

  flush() {
    if (this.buffer.trim()) this.speak(this.buffer);
    this.buffer = "";
  }

  stop() {
    this.buffer = "";
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
