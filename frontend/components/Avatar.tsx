"use client";
import { useEffect, useRef, useState } from "react";

/**
 * Placeholder animated teacher (SVG): blinks, and moves the mouth while `speaking`.
 * The mouth is driven by a simple oscillator because browser TTS exposes no audio
 * stream. To upgrade, keep this component's props and replace the body with:
 *   - a hosted streaming avatar (HeyGen / D-ID / Simli / Tavus), or
 *   - a three.js VRM model driven by visemes from a cloud TTS.
 */
export default function Avatar({ speaking, listening }: { speaking: boolean; listening: boolean }) {
  const [open, setOpen] = useState(0); // mouth openness 0..1
  const [blink, setBlink] = useState(false);
  const raf = useRef<number>(0);

  useEffect(() => {
    let t0 = performance.now();
    const tick = (t: number) => {
      const s = (t - t0) / 1000;
      if (speaking) {
        const v = Math.abs(Math.sin(s * 11)) * (0.55 + 0.45 * Math.sin(s * 3.3));
        setOpen(v);
      } else {
        setOpen((o) => o * 0.8);
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [speaking]);

  useEffect(() => {
    const id = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 130);
    }, 3200);
    return () => clearInterval(id);
  }, []);

  const mouthH = 3 + open * 16;
  const eyeH = blink ? 0.8 : 6;
  const lean = listening ? -2 : 0;

  return (
    <svg viewBox="0 0 200 220" className="avatar" role="img" aria-label="Teacher avatar">
      {/* hair back */}
      <path d="M38 105 C30 40 80 14 100 14 C122 14 172 40 162 105 C162 150 150 160 150 160 L50 160 C50 160 38 150 38 105Z" fill="#2b1d17" />
      {/* shoulders / blouse */}
      <path d="M20 220 C24 176 60 164 100 164 C140 164 176 176 180 220Z" fill="#3b6ea5" />
      <path d="M84 164 L100 188 L116 164Z" fill="#f2f2f2" />
      {/* neck */}
      <rect x="86" y="140" width="28" height="30" rx="10" fill="#e0b08c" />
      {/* face */}
      <g transform={`rotate(${lean} 100 100)`}>
        <ellipse cx="100" cy="98" rx="52" ry="60" fill="#efc4a0" />
        {/* fringe */}
        <path d="M48 90 C50 42 92 30 108 34 C138 40 156 62 152 94 C140 70 112 58 84 62 C66 66 54 78 48 90Z" fill="#2b1d17" />
        {/* brows */}
        <path d="M70 84 Q80 78 90 84" stroke="#2b1d17" strokeWidth="3" fill="none" strokeLinecap="round" />
        <path d="M110 84 Q120 78 130 84" stroke="#2b1d17" strokeWidth="3" fill="none" strokeLinecap="round" />
        {/* eyes */}
        <ellipse cx="80" cy="100" rx="8" ry={eyeH} fill="#fff" />
        <ellipse cx="120" cy="100" rx="8" ry={eyeH} fill="#fff" />
        {!blink && (
          <>
            <circle cx="80" cy="100" r="3.6" fill="#3a2a20" />
            <circle cx="120" cy="100" r="3.6" fill="#3a2a20" />
          </>
        )}
        {/* glasses */}
        <circle cx="80" cy="100" r="14" fill="none" stroke="#444" strokeWidth="2" />
        <circle cx="120" cy="100" r="14" fill="none" stroke="#444" strokeWidth="2" />
        <path d="M94 100 L106 100" stroke="#444" strokeWidth="2" />
        {/* nose */}
        <path d="M100 106 Q96 124 102 126" stroke="#c99674" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        {/* mouth */}
        <ellipse cx="100" cy="142" rx={13 - open * 3} ry={mouthH} fill={open > 0.08 ? "#7a2e2e" : "#b05a58"} />
        {open <= 0.08 && (
          <path d="M88 142 Q100 150 112 142" stroke="#7a2e2e" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        )}
      </g>
    </svg>
  );
}
