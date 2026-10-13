import type { AiStatus, Health, Priority, Status } from "../types";

const prio: Record<Priority, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-sky-100 text-sky-800",
  high: "bg-amber-100 text-amber-800",
  urgent: "bg-red-100 text-red-800",
};
const stat: Record<Status, string> = {
  open: "bg-indigo-100 text-indigo-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-emerald-100 text-emerald-800",
  closed: "bg-slate-200 text-slate-700",
};
const ai: Record<AiStatus, [string, string]> = {
  pending: ["Queued", "bg-slate-100 text-slate-700"],
  generating: ["Drafting…", "bg-indigo-100 text-indigo-800 animate-pulse"],
  done: ["Draft ready", "bg-emerald-100 text-emerald-800"],
  failed: ["AI failed", "bg-red-100 text-red-800"],
  skipped: ["Manual", "bg-amber-100 text-amber-800"],
};

const pill = "inline-block rounded-full px-2 py-0.5 text-xs font-medium";

export const PriorityBadge = ({ p }: { p: Priority }) => <span className={`${pill} ${prio[p]}`}>{p}</span>;
export const StatusBadge = ({ s }: { s: Status }) => <span className={`${pill} ${stat[s]}`}>{s.replace("_", " ")}</span>;
export const AiBadge = ({ s }: { s: AiStatus }) => <span className={`${pill} ${ai[s][1]}`}>{ai[s][0]}</span>;

export function HealthBar({ h }: { h: Health | null }) {
  const dot = (ok: boolean) => <span className={`mr-1 inline-block h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />;
  if (!h) return <span className="text-xs text-red-600">Backend offline</span>;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
      <span>{dot(h.database)}DB</span>
      <span>{dot(h.ml_model)}ML model</span>
      <span title={h.ollama ? (h.ollama_model_available ? "" : "Model not pulled") : "Ollama not reachable"}>
        {dot(h.ollama && h.ollama_model_available)}Local LLM
      </span>
      <span>{dot(h.knowledge_base_chunks > 0)}KB ({h.knowledge_base_chunks} chunks)</span>
    </div>
  );
}
