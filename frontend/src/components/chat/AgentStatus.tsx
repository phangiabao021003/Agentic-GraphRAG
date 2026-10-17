import { Spinner } from "../common/Spinner";

export function AgentStatus({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500 px-2">
      <Spinner />
      <span>{text}</span>
    </div>
  );
}
