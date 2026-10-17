import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
};

const STYLES = {
  primary: "bg-emerald-600 hover:bg-emerald-700 text-white",
  ghost: "bg-transparent hover:bg-slate-200 text-slate-600",
  danger: "bg-rose-600 hover:bg-rose-700 text-white",
};

export function Button({ variant = "primary", className = "", ...rest }: Props) {
  return (
    <button
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${STYLES[variant]} ${className}`}
      {...rest}
    />
  );
}
