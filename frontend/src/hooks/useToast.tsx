import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type ToastKind = "success" | "error" | "info";
type Toast = { id: number; text: string; kind: ToastKind };

const ToastContext = createContext<(text: string, kind?: ToastKind) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

const KIND_STYLES: Record<ToastKind, string> = {
  success: "bg-emerald-600",
  error: "bg-rose-600",
  info: "bg-slate-700",
};

const TOAST_MS = 4500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((current) => {
      // One outage can fail several requests at once; show the message once.
      if (current.some((t) => t.text === text)) return current;
      setTimeout(() => setToasts((later) => later.filter((t) => t.id !== id)), TOAST_MS);
      return [...current, { id, text, kind }];
    });
  }, []);

  // Failed HTTP requests report here from api/client.ts and api/sse.ts.
  useEffect(() => {
    const onApiError = (e: Event) => {
      const { message } = (e as CustomEvent<{ status: number; message: string }>).detail;
      push(message, "error");
    };
    window.addEventListener("api-error", onApiError);
    return () => window.removeEventListener("api-error", onApiError);
  }, [push]);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            data-toast
            className={`${KIND_STYLES[t.kind]} text-white text-sm px-4 py-2 rounded-lg shadow-lg max-w-sm`}
          >
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
