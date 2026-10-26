// Default "/api" is proxied to the backend by next.config.js, so the browser only
// ever talks to the frontend's own port (works locally and in GitHub Codespaces).
export const API = process.env.NEXT_PUBLIC_API_URL || "/api";

export type Source = { n: number; source: string; page: number | null; topic: string | null };

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/** POST and read the text/plain streaming response chunk by chunk. */
export async function streamPost(
  path: string,
  body: unknown,
  onText: (chunk: string) => void,
  onSources?: (s: Source[]) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await res.text());
  const hdr = res.headers.get("X-Sources");
  if (hdr && onSources) onSources(JSON.parse(decodeURIComponent(hdr)));
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onText(dec.decode(value, { stream: true }));
  }
}
