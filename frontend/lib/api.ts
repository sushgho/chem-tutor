import { supabase } from "@/lib/supabase";

// Default "/api" is proxied to the backend by next.config.js, so the browser only
// ever talks to the frontend's own port (works locally and in GitHub Codespaces).
export const API = process.env.NEXT_PUBLIC_API_URL || "/api";
export const REQUIRE_SIGN_IN = process.env.NEXT_PUBLIC_REQUIRE_SIGN_IN === "true";

export type Source = {
  n: number;
  source: string;
  page: number | null;
  topic: string | null;
  image_url?: string;
};

export async function createGuestSession(): Promise<{ id: number; library_key: string }> {
  const guestToken = localStorage.getItem("guestSessionToken");
  const headers = new Headers();
  if (guestToken) headers.set("X-Guest-Session", guestToken);

  const res = await fetch(API + "/guest/session", { method: "POST", headers });
  if (!res.ok) throw new Error(await errorMessage(res));

  const session: { id: number; library_key: string; guest_session: string } = await res.json();
  localStorage.setItem("guestSessionToken", session.guest_session);
  localStorage.setItem("studentId", String(session.id));
  localStorage.setItem("studyLibraryKey", session.library_key);
  return session;
}

async function authenticatedHeaders(headers?: HeadersInit): Promise<Headers> {
  const result = new Headers(headers);
  if (REQUIRE_SIGN_IN && supabase) {
    const { data, error } = await supabase.auth.getSession();
    if (error) throw error;
    if (data.session?.access_token) {
      result.set("Authorization", `Bearer ${data.session.access_token}`);
    }
  } else {
    const guestToken = localStorage.getItem("guestSessionToken");
    if (guestToken) result.set("X-Guest-Session", guestToken);
  }
  return result;
}

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
  const res = await fetch(API + path, { headers: await authenticatedHeaders(headers) });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const headers = await authenticatedHeaders({ "Content-Type": "application/json" });
  const res = await fetch(API + path, {
    method: "POST",
    headers,
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
  const res = await fetch(API + path, {
    method: "POST",
    body,
    headers: await authenticatedHeaders(headers),
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function deleteJSON<T>(path: string, headers?: HeadersInit): Promise<T> {
  const res = await fetch(API + path, {
    method: "DELETE",
    headers: await authenticatedHeaders(headers),
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
  headers?: HeadersInit,
) {
  const requestHeaders = await authenticatedHeaders(headers);
  requestHeaders.set("Content-Type", "application/json");
  const res = await fetch(API + path, {
    method: "POST",
    headers: requestHeaders,
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
