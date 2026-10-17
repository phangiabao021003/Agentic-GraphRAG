import { useCallback, useState } from "react";
import { apiJson } from "../api/client";
import { streamChat } from "../api/sse";
import type { ChatRequest, Message } from "../api/types";

export type UiMessage = { role: "user" | "assistant"; content: string };

function statusFor(tool: string): string {
  if (tool === "rag_search") return "🔍 Đang tìm trong tài liệu...";
  if (tool === "web_search") return "🌐 Đang tìm trên web...";
  if (tool.startsWith("calendar_")) return "📅 Đang thao tác lịch...";
  return "⚙️ Đang xử lý...";
}

export function useChat(
  onConversationCreated: (id: string) => void,
  onTurnDone: () => void,
) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const loadConversation = useCallback(async (id: string | null) => {
    if (!id) {
      setMessages([]);
      return;
    }
    const history = await apiJson<Message[]>(`/conversations/${id}/messages`);
    setMessages(history.map((m) => ({ role: m.role, content: m.content })));
  }, []);

  const send = useCallback(
    async (conversationId: string | null, text: string, docIds: string[]) => {
      setMessages((current) => [...current, { role: "user", content: text }]);
      setSending(true);
      setStatus(null);
      try {
        const body: ChatRequest = { message: text };
        if (conversationId) body.conversation_id = conversationId;
        if (docIds.length > 0) body.doc_ids = docIds;

        for await (const ev of streamChat(body)) {
          if (ev.event === "conversation") {
            onConversationCreated(ev.data.conversation_id);
          } else if (ev.event === "tool_call") {
            setStatus(statusFor(ev.data.tool));
          } else if (ev.event === "tool_result") {
            setStatus(null);
          } else if (ev.event === "answer") {
            setMessages((current) => [...current, { role: "assistant", content: ev.data.content }]);
          }
        }
        onTurnDone();
      } finally {
        setSending(false);
        setStatus(null);
      }
    },
    [onConversationCreated, onTurnDone],
  );

  return { messages, sending, status, send, loadConversation };
}
