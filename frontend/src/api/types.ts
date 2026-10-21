export type TokenPair = {
  access_token: string;
  refresh_token: string;
};

export type User = {
  id: string;
  email: string;
};

export type Conversation = {
  id: string;
  title: string;
  updated_at: string;
};

type ToolCallRecord = {
  tool: string;
  args: Record<string, unknown>;
  result: string | null;
};

export type Message = {
  role: "user" | "assistant";
  content: string;
  tool_calls: ToolCallRecord[] | null;
  created_at: string;
};

export type ChatRequest = {
  conversation_id?: string;
  message: string;
  doc_ids?: string[];
};

// Wire events from POST /chat (SSE)
export type SSEEvent = {
  event: string;
  data: any;
};

// `event: error` data from POST /chat (backend app/agent/errors.py)
export type ErrorEvent = {
  code: string;
  message: string;
  tool: string | null;
  severity: "error" | "warning";
};

export type DocumentList = {
  doc_ids: string[];
};
