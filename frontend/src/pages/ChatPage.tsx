import { useCallback, useEffect, useState } from "react";
import type { User } from "../api/types";
import { Composer } from "../components/chat/Composer";
import { MessageList } from "../components/chat/MessageList";
import { Button } from "../components/common/Button";
import { ConversationList } from "../components/sidebar/ConversationList";
import { DocumentPanel } from "../components/sidebar/DocumentPanel";
import { GoogleConnect } from "../components/sidebar/GoogleConnect";
import { useChat } from "../hooks/useChat";
import { useConversations } from "../hooks/useConversations";
import { useDocuments } from "../hooks/useDocuments";
import { useToast } from "../hooks/useToast";
import { MainLayout } from "../layouts/MainLayout";

type Props = { user: User; onLogout: () => void };

export function ChatPage({ user, onLogout }: Props) {
  const toast = useToast();
  const [activeId, setActiveId] = useState<string | null>(null);
  const { conversations, reload, remove } = useConversations();
  const { docIds, selected, toggle, upload, uploading } = useDocuments();

  const onConversationCreated = useCallback((id: string) => {
    setActiveId(id);
  }, []);
  const { messages, sending, status, send, loadConversation } = useChat(onConversationCreated, reload);

  // Google OAuth callback lands on ?google=connected
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") === "connected") {
      toast("Đã kết nối Google Calendar thành công", "success");
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [toast]);

  const selectConversation = useCallback(
    (id: string | null) => {
      setActiveId(id);
      loadConversation(id).catch(() => toast("Không tải được lịch sử hội thoại", "error"));
    },
    [loadConversation, toast],
  );

  const handleSend = useCallback(
    (text: string) => {
      send(activeId, text, [...selected]).catch(() => toast("Gửi tin nhắn thất bại — thử lại nhé", "error"));
    },
    [send, activeId, selected, toast],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await remove(id);
        if (id === activeId) selectConversation(null);
      } catch {
        toast("Xóa hội thoại thất bại", "error");
      }
    },
    [remove, activeId, selectConversation, toast],
  );

  const handleUpload = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        toast("Chỉ nhận file PDF", "error");
        return;
      }
      try {
        const result = await upload(file);
        toast(result.message, result.status === "success" ? "success" : "info");
      } catch {
        toast("Tải tài liệu thất bại", "error");
      }
    },
    [upload, toast],
  );

  const sidebar = (
    <>
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="font-semibold text-emerald-700">🌱 Nutrition VA</p>
          <p className="text-xs text-slate-400 truncate" title={user.email}>{user.email}</p>
        </div>
        <Button variant="ghost" className="text-xs shrink-0" onClick={onLogout}>Thoát</Button>
      </div>
      <ConversationList
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onDelete={handleDelete}
      />
      <DocumentPanel docIds={docIds} selected={selected} onToggle={toggle}
                     uploading={uploading} onUpload={handleUpload} />
      <GoogleConnect />
    </>
  );

  return (
    <MainLayout sidebar={sidebar}>
      <MessageList messages={messages} status={status} />
      <Composer disabled={sending} onSend={handleSend} />
    </MainLayout>
  );
}
