import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, clearTokens, setTokens } from "./client";
import { parseSSEChunk, streamChat } from "./sse";

const NL = "\n";
const SEP = "\n\n";

describe("parseSSEChunk", () => {
  it("parses one complete frame", () => {
    const { events, rest } = parseSSEChunk(`event: answer${NL}data: {"content": "hi"}${SEP}`);
    expect(events).toEqual([{ event: "answer", data: { content: "hi" } }]);
    expect(rest).toBe("");
  });

  it("keeps an incomplete frame in rest", () => {
    const input = `event: answer${NL}data: {"con`;
    const { events, rest } = parseSSEChunk(input);
    expect(events).toEqual([]);
    expect(rest).toBe(input);
  });

  it("parses a frame completed across two calls", () => {
    const first = parseSSEChunk(`event: rewrite${NL}data: {"standalone`);
    const second = parseSSEChunk(first.rest + `_query": "q?"}${SEP}`);
    expect(second.events).toEqual([{ event: "rewrite", data: { standalone_query: "q?" } }]);
  });

  it("parses multiple frames in one chunk", () => {
    const { events } = parseSSEChunk(
      `event: tool_call${NL}data: {"tool": "rag_search", "args": {}}${SEP}` +
      `event: tool_result${NL}data: {"tool": "rag_search", "result": "ctx"}${SEP}`
    );
    expect(events.map((e) => e.event)).toEqual(["tool_call", "tool_result"]);
  });

  it("preserves Vietnamese UTF-8 content", () => {
    const { events } = parseSSEChunk(
      `event: answer${NL}data: {"content": "Chào bạn, vitamin C giúp tăng đề kháng"}${SEP}`
    );
    expect(events[0].data.content).toContain("tăng đề kháng");
  });

  it("ignores comment/ping lines", () => {
    const { events } = parseSSEChunk(`: ping${SEP}event: answer${NL}data: {"num": 1}${SEP}`);
    expect(events).toEqual([{ event: "answer", data: { num: 1 } }]);
  });

  // sse-starlette >= 3 terminates lines with CRLF; the SSE spec allows CRLF, LF or CR.
  const CRLF = "\r\n";

  it("parses CRLF-terminated frames (sse-starlette default)", () => {
    const { events, rest } = parseSSEChunk(
      `event: conversation${CRLF}data: {"conversation_id": "c1"}${CRLF}${CRLF}` +
      `event: answer${CRLF}data: {"content": "Xin chào!"}${CRLF}${CRLF}`
    );
    expect(events).toEqual([
      { event: "conversation", data: { conversation_id: "c1" } },
      { event: "answer", data: { content: "Xin chào!" } },
    ]);
    expect(rest).toBe("");
  });

  it("parses a CRLF frame whose chunk boundary splits CR from LF", () => {
    const first = parseSSEChunk(`event: answer${CRLF}data: {"content": "hi"}${CRLF}\r`);
    expect(first.events).toEqual([]);
    const second = parseSSEChunk(first.rest + "\n");
    expect(second.events).toEqual([{ event: "answer", data: { content: "hi" } }]);
    expect(second.rest).toBe("");
  });

  it("does not create a spurious frame when a chunk ends with a lone CR", () => {
    const first = parseSSEChunk("event: answer\r");
    const second = parseSSEChunk(first.rest + `\ndata: {"n": 1}${CRLF}${CRLF}`);
    expect([...first.events, ...second.events]).toEqual([{ event: "answer", data: { n: 1 } }]);
  });

  it("parses an error frame", () => {
    const { events } = parseSSEChunk(
      `event: error${CRLF}data: {"code": "tool_failed", "message": "Công cụ web_search gặp lỗi, kết quả có thể thiếu.", "tool": "web_search", "severity": "error"}${CRLF}${CRLF}`
    );
    expect(events).toEqual([
      {
        event: "error",
        data: { code: "tool_failed", message: "Công cụ web_search gặp lỗi, kết quả có thể thiếu.", tool: "web_search", severity: "error" },
      },
    ]);
  });
});

describe("streamChat", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    clearTokens();
  });

  it("reports a mid-stream read failure as a network ApiError and api-error event", async () => {
    setTokens("a", "r");
    const frame = new TextEncoder().encode("event: answer\ndata: {\"content\":\"hi\"}\n\n");
    let sent = false;
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (!sent) {
          sent = true;
          controller.enqueue(frame);
        } else {
          controller.error(new TypeError("network"));
        }
      },
    });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 200 })));
    const seen: any[] = [];
    const listener = (e: Event) => seen.push((e as CustomEvent).detail);
    window.addEventListener("api-error", listener);
    try {
      const gen = streamChat({ message: "q" } as any);
      const first = await gen.next();
      expect(first.value).toEqual({ event: "answer", data: { content: "hi" } });
      const err = await gen.next().catch((e) => e);
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(0);
      expect(seen).toEqual([{ status: 0, message: "Không kết nối được tới máy chủ" }]);
    } finally {
      window.removeEventListener("api-error", listener);
    }
  });
});
