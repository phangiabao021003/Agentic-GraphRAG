import type { Conversation } from "../../api/types";

type Props = {
  conversation: Conversation;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
};

export function ConversationItem({ conversation, active, onSelect, onDelete }: Props) {
  return (
    <div
      className={`group flex items-center justify-between rounded-lg px-3 py-2 cursor-pointer text-sm ${
        active ? "bg-emerald-100 text-emerald-900" : "hover:bg-slate-100 text-slate-700"
      }`}
      onClick={onSelect}
    >
      <span className="truncate">{conversation.title}</span>
      <button
        className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 ml-2 shrink-0"
        title="Xóa cuộc trò chuyện"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        ✕
      </button>
    </div>
  );
}
