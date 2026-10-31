// Default "/api" is proxied to the backend by next.config.js, so the browser only
// ever talks to the frontend's own port (works locally and in GitHub Codespaces).
export const API = process.env.NEXT_PUBLIC_API_URL || "/api";

export type Source = { n: number; source: string; page: number | null; topic: string | null };

async function errorMessage(res: Response): Promise<string> {
  const body = await res.text();
  if (!body) return `${res.status} ${res.statusText}`;
  try {
    const parsed: unknown = JSON.parse(body);
    if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
      const detail = parsed.detail;
      if (typeof detail === "string") return detail;
    }
  } catch {
    return body;
  }
  return body;
}

export async function getJSON<T>(path: string, headers?: HeadersInit): Promise<T> {
  const res = await fetch(API + path, { headers });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function uploadFile<T>(
  path: string,
  body: FormData,
  headers?: HeadersInit,
): Promise<T> {
  const res = await fetch(API + path, { method: "POST", body, headers });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function deleteJSON<T>(path: string, headers?: HeadersInit): Promise<T> {
  const res = await fetch(API + path, { method: "DELETE", headers });
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
  headers?: HeadersInit,
) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...Object.fromEntries(new Headers(headers).entries()) },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(await errorMessage(res));
  const hdr = res.headers.get("X-Sources");
  if (hdr && onSources) onSources(JSON.parse(decodeURIComponent(hdr)));
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let receivedText = false;
  for (;;) {
    const { done, value } = await reader.read();
    const text = done ? dec.decode() : dec.decode(value, { stream: true });
    if (text) {
      receivedText = true;
      onText(text);
    }
    if (done) break;
  }
  if (!receivedText) throw new Error("DIVA returned an empty response. Please try again.");
}
