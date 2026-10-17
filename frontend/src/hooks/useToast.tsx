import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

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

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((text: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, text, kind }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`${KIND_STYLES[t.kind]} text-white text-sm px-4 py-2 rounded-lg shadow-lg max-w-sm`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
