// SSE over fetch (EventSource cannot POST). Pure logic — no React imports.
import { API_URL, getAccessToken, refreshTokens, ApiError } from "./client";
import type { ChatRequest, SSEEvent } from "./types";

/**
 * Pure parser: consumes a text buffer, returns completed events and the
 * unconsumed tail. Frames are separated by a blank line; lines are
 * `event: <name>` / `data: <json>`; `:`-prefixed lines are comments (pings).
 */
export function parseSSEChunk(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? ""; // last piece is incomplete (or empty)

  for (const frame of parts) {
    let eventName = "";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith(":")) continue; // comment / keep-alive ping
      if (line.startsWith("event: ")) eventName = line.slice(7).trim();
      else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    }
    if (!eventName) continue;
    let data: any = null;
    if (dataLines.length > 0) {
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {
        data = dataLines.join("\n"); // tolerate non-JSON data
      }
    }
    events.push({ event: eventName, data });
  }
  return { events, rest };
}

/** POST /chat and yield SSE events as they arrive. */
export async function* streamChat(body: ChatRequest): AsyncGenerator<SSEEvent> {
  const call = () =>
    fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getAccessToken()}`,
      },
      body: JSON.stringify(body),
    });

  let resp = await call();
  if (resp.status === 401 && (await refreshTokens())) {
    resp = await call();
  }
  if (!resp.ok || !resp.body) {
    throw new ApiError(resp.status, `Chat request failed (HTTP ${resp.status})`);
  }

  const reader = resp.body.getReader();
  // stream:true — Vietnamese UTF-8 characters can be split across chunks.
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSSEChunk(buffer);
      buffer = rest;
      for (const event of events) yield event;
    }
  } finally {
    reader.releaseLock();
  }
}
