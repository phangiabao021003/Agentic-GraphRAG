import type { InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string };

export function Input({ label, className = "", ...rest }: Props) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-600 mb-1">{label}</span>
      <input
        className={`w-full px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-sm ${className}`}
        {...rest}
      />
    </label>
  );
}
