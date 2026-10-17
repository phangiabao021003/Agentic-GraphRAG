import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-emerald-50 to-slate-100 px-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-emerald-700 mb-1">🌱 Nutrition Assistant</h1>
        <p className="text-sm text-slate-500 mb-6">Trợ lý dinh dưỡng & lịch trình cá nhân</p>
        {children}
      </div>
    </div>
  );
}
