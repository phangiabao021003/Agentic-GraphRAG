import type { ReactNode } from "react";

type Props = { sidebar: ReactNode; children: ReactNode };

export function MainLayout({ sidebar, children }: Props) {
  return (
    <div className="h-screen flex bg-slate-50">
      <aside className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col gap-6 p-4 overflow-y-auto">
        {sidebar}
      </aside>
      <main className="flex-1 flex flex-col min-w-0">{children}</main>
    </div>
  );
}
