import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../api/client";
import type { Conversation } from "../api/types";

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);

  const reload = useCallback(async () => {
    setConversations(await apiJson<Conversation[]>("/conversations"));
  }, []);

  useEffect(() => {
    reload().catch(() => {});
  }, [reload]);

  const remove = useCallback(
    async (id: string) => {
      await apiJson(`/conversations/${id}`, { method: "DELETE" });
      await reload();
    },
    [reload],
  );

  return { conversations, reload, remove };
}
