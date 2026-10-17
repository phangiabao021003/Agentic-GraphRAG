import ReactMarkdown from "react-markdown";
import type { UiMessage } from "../../hooks/useChat";

export function MessageBubble({ message }: { message: UiMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-emerald-600 text-white rounded-2xl rounded-br-sm px-4 py-2 max-w-[75%] text-sm whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm px-4 py-2 max-w-[75%] text-sm prose prose-sm prose-slate">
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </div>
    </div>
  );
}
