import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { AiBadge, HealthBar, PriorityBadge, StatusBadge } from "./components/Badges";
import FieldAdmin from "./components/FieldAdmin";
import TicketDetail from "./components/TicketDetail";
import TicketForm from "./components/TicketForm";
import type { FieldDef, Health, Ticket } from "./types";

type View = { name: "list" } | { name: "new" } | { name: "fields" } | { name: "detail"; id: number };

export default function App() {
  const [view, setView] = useState<View>({ name: "list" });
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [error, setError] = useState("");

  const loadDefs = useCallback(() => api.fields().then(setDefs).catch(() => {}), []);
  const loadTickets = useCallback(async () => {
    const params: Record<string, string> = {};
    if (q) params.q = q;
    if (status) params.status = status;
    if (showInactive) params.include_inactive = "true";
    try {
      const r = await api.tickets(params);
      setTickets(r.items);
      setTotal(r.total);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [q, status, showInactive]);

  useEffect(() => {
    loadDefs();
  }, [loadDefs]);
  useEffect(() => {
    const h = setTimeout(loadTickets, 200);
    return () => clearTimeout(h);
  }, [loadTickets]);
  useEffect(() => {
    const tick = () => api.health().then(setHealth).catch(() => setHealth(null));
    tick();
    const h = setInterval(tick, 10000);
    return () => clearInterval(h);
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button onClick={() => setView({ name: "list" })} className="text-left">
            <h1 className="text-2xl font-bold tracking-tight">AI Ticket Desk</h1>
            <p className="text-xs text-slate-500">Local ML + RAG + LLM · nothing leaves your machine</p>
          </button>
          <nav className="flex gap-2">
            <button className="btn-ghost" onClick={() => setView({ name: "fields" })}>Custom fields</button>
            <button className="btn-primary" onClick={() => setView({ name: "new" })}>+ New ticket</button>
          </nav>
        </div>
        <HealthBar h={health} />
        {health && !health.ollama && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Ollama isn't reachable. Tickets and ML predictions still work, but AI drafts will fail until you run <code>ollama serve</code>.
          </p>
        )}
        {health && health.ollama && !health.ollama_model_available && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Ollama is running but the configured model isn't pulled yet. Run <code>ollama pull llama3.2:3b</code>.
          </p>
        )}
      </header>

      {view.name === "new" && (
        <TicketForm
          defs={defs}
          onCancel={() => setView({ name: "list" })}
          onSaved={(t) => {
            loadTickets();
            setView({ name: "detail", id: t.id });
          }}
        />
      )}

      {view.name === "fields" && <FieldAdmin defs={defs} onChanged={loadDefs} />}

      {view.name === "detail" && (
        <TicketDetail id={view.id} defs={defs} onBack={() => setView({ name: "list" })} onChanged={loadTickets} />
      )}

      {view.name === "list" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <input className="input !w-64" placeholder="Search subject, customer, text…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
              <option value="">All statuses</option>
              <option value="open">open</option>
              <option value="in_progress">in progress</option>
              <option value="resolved">resolved</option>
              <option value="closed">closed</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
              Show deactivated
            </label>
            <span className="ml-auto text-xs text-slate-500">{total} ticket{total === 1 ? "" : "s"}</span>
          </div>

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <div className="card !p-0 overflow-hidden">
            {tickets.length === 0 ? (
              <p className="p-8 text-center text-sm text-slate-500">No tickets yet. Create one to see the ML and RAG pipeline run.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {tickets.map((t) => (
                  <li key={t.id}>
                    <button className={`flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-slate-50 ${t.is_active ? "" : "opacity-50"}`} onClick={() => setView({ name: "detail", id: t.id })}>
                      <span className="w-10 text-xs text-slate-400">#{t.id}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{t.subject}</span>
                        <span className="block truncate text-xs text-slate-500">
                          {t.customer_name}
                          {t.predicted_solution ? ` · ${t.predicted_solution}` : ""}
                        </span>
                      </span>
                      <span className="hidden items-center gap-2 sm:flex">
                        <AiBadge s={t.ai_status} />
                        <PriorityBadge p={t.priority} />
                        <StatusBadge s={t.status} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
