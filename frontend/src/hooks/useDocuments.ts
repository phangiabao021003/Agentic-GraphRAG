import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../api/client";
import type { DocumentList } from "../api/types";

export function useDocuments() {
  const [docIds, setDocIds] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [uploading, setUploading] = useState(false);

  const reload = useCallback(async () => {
    const data = await apiJson<DocumentList>("/documents");
    setDocIds(data.doc_ids);
  }, []);

  useEffect(() => {
    reload().catch(() => {});
  }, [reload]);

  const toggle = useCallback((id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const upload = useCallback(
    async (file: File): Promise<{ status: string; message: string }> => {
      const form = new FormData();
      form.append("file", file);
      setUploading(true);
      try {
        const result = await apiJson<{ status: string; message: string }>("/documents", {
          method: "POST",
          body: form,
        });
        await reload();
        return result;
      } finally {
        setUploading(false);
      }
    },
    [reload],
  );

  return { docIds, selected, toggle, upload, uploading };
}
