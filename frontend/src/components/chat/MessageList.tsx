import { useEffect, useRef } from "react";
import type { UiMessage } from "../../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { AgentStatus } from "./AgentStatus";

type Props = { messages: UiMessage[]; status: string | null };

export function MessageList({ messages, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, status]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-3">
      {messages.length === 0 && !status && (
        <p className="text-center text-slate-400 text-sm mt-12">
          Hỏi tôi về dinh dưỡng, hoặc nhờ tôi quản lý lịch của bạn 🌱
        </p>
      )}
      {messages.map((m, i) => (
        <MessageBubble key={i} message={m} />
      ))}
      {status && <AgentStatus text={status} />}
      <div ref={bottomRef} />
    </div>
  );
}
