import { useState } from "react";
import type { Conversation } from "../../api/types";
import { Button } from "../common/Button";
import { Modal } from "../common/Modal";
import { ConversationItem } from "./ConversationItem";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
  onDelete: (id: string) => void;
};

export function ConversationList({ conversations, activeId, onSelect, onDelete }: Props) {
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null);

  return (
    <div className="flex flex-col gap-1">
      <Button variant="ghost" className="mb-1 text-left border border-dashed border-slate-300" onClick={() => onSelect(null)}>
        + Cuộc trò chuyện mới
      </Button>
      {conversations.map((c) => (
        <ConversationItem
          key={c.id}
          conversation={c}
          active={c.id === activeId}
          onSelect={() => onSelect(c.id)}
          onDelete={() => setPendingDelete(c)}
        />
      ))}
      {pendingDelete && (
        <Modal
          title="Xóa cuộc trò chuyện?"
          confirmLabel="Xóa"
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => {
            onDelete(pendingDelete.id);
            setPendingDelete(null);
          }}
        >
          “{pendingDelete.title}” sẽ bị xóa vĩnh viễn.
        </Modal>
      )}
    </div>
  );
}
