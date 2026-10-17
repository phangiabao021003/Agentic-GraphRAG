export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block w-4 h-4 border-2 border-slate-300 border-t-emerald-600 rounded-full animate-spin ${className}`}
      role="status"
      aria-label="Đang tải"
    />
  );
}
