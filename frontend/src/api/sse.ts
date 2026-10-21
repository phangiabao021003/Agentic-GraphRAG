// SSE over fetch (EventSource cannot POST). Pure logic — no React imports.
import { API_URL, getAccessToken, refreshTokens, ApiError, errorDetail, notifyApiError, NETWORK_ERROR_MESSAGE } from "./client";
import type { ChatRequest, SSEEvent } from "./types";

/**
 * Pure parser: consumes a text buffer, returns completed events and the
 * unconsumed tail. Frames are separated by a blank line; lines are
 * `event: <name>` / `data: <json>`; `:`-prefixed lines are comments (pings).
 *
 * Line endings may be CRLF, LF or CR (SSE spec). sse-starlette >= 3 sends CRLF,
 * so splitting on "\n\n" alone never finds a frame. A trailing lone CR is held
 * back in `rest`: it may be the first half of a CRLF split across chunks.
 */
export function parseSSEChunk(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = [];
  const trailingCR = buffer.endsWith("\r");
  const normalized = (trailingCR ? buffer.slice(0, -1) : buffer).replace(/\r\n?/g, "\n");
  const parts = normalized.split("\n\n");
  // last piece is incomplete (or empty)
  const rest = (parts.pop() ?? "") + (trailingCR ? "\r" : "");

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

  let resp: Response;
  try {
    resp = await call();
    if (resp.status === 401 && (await refreshTokens())) {
      resp = await call();
    }
  } catch {
    notifyApiError(0, NETWORK_ERROR_MESSAGE);
    throw new ApiError(0, NETWORK_ERROR_MESSAGE);
  }
  if (!resp.ok || !resp.body) {
    const detail = resp.ok ? `Chat request failed (HTTP ${resp.status})` : await errorDetail(resp);
    if (resp.status !== 401) notifyApiError(resp.status, detail);
    throw new ApiError(resp.status, detail);
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
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    notifyApiError(0, NETWORK_ERROR_MESSAGE);
    throw new ApiError(0, NETWORK_ERROR_MESSAGE);
  } finally {
    reader.releaseLock();
  }
}
