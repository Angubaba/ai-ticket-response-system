import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { FieldDef, Status, Ticket } from "../types";
import { AiBadge, PriorityBadge, StatusBadge } from "./Badges";
import TicketForm from "./TicketForm";

interface Props {
  id: number;
  defs: FieldDef[];
  onBack: () => void;
  onChanged: () => void;
}

const STATUSES: Status[] = ["open", "in_progress", "resolved", "closed"];

export default function TicketDetail({ id, defs, onBack, onChanged }: Props) {
  const [t, setT] = useState<Ticket | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const x = await api.ticket(id);
      setT(x);
      return x;
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // seed the editor from final_response, else the AI draft, unless the agent is mid-edit
  useEffect(() => {
    if (t && !dirty) setDraft(t.final_response ?? t.ai_response ?? "");
  }, [t, dirty]);

  // poll while the background AI job is running
  const working = t?.ai_status === "pending" || t?.ai_status === "generating";
  useEffect(() => {
    if (!working) return;
    const h = setInterval(load, 1500);
    return () => clearInterval(h);
  }, [working, load]);

  if (!t) return <p className="text-sm text-slate-500">{error || "Loading…"}</p>;

  if (editing)
    return (
      <TicketForm
        defs={defs}
        initial={t}
        onCancel={() => setEditing(false)}
        onSaved={(x) => {
          setT(x);
          setEditing(false);
          onChanged();
        }}
      />
    );

  async function run<T>(fn: () => Promise<T>) {
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setStatus(s: Status) {
    const x = await run(() => api.update(id, { status: s }));
    if (x) {
      setT(x);
      onChanged();
    }
  }

  async function saveResponse() {
    const x = await run(() => api.saveResponse(id, draft));
    if (x) {
      setT(x);
      setDirty(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onChanged();
    }
  }

  async function regenerate(repredict: boolean) {
    const x = await run(() => api.regenerate(id, repredict));
    if (x) {
      setT(x);
      setDirty(false);
    }
  }

  async function del() {
    if (!confirm("Deactivate this ticket? It will be hidden from the list.")) return;
    if ((await run(() => api.remove(id))) !== undefined || true) {
      onChanged();
      onBack();
    }
  }

  const conf = t.ml_confidence != null ? Math.round(t.ml_confidence * 100) : null;
  const custom = defs.filter((d) => t.custom_fields[d.key] !== undefined && t.custom_fields[d.key] !== null);

  return (
    <div className="space-y-5">
      <button className="text-sm text-indigo-600 hover:underline" onClick={onBack}>← All tickets</button>

      <div className="card space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs text-slate-500">#{t.id} · {t.customer_name} · {new Date(t.created_at).toLocaleString()}</p>
            <h2 className="text-xl font-semibold">{t.subject}</h2>
          </div>
          <div className="flex items-center gap-2">
            <PriorityBadge p={t.priority} />
            <StatusBadge s={t.status} />
            {!t.is_active && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs">inactive</span>}
          </div>
        </div>
        <p className="whitespace-pre-wrap text-sm text-slate-700">{t.description}</p>

        {custom.length > 0 && (
          <dl className="grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-3">
            {custom.map((d) => (
              <div key={d.key}>
                <dt className="label">{d.label}</dt>
                <dd className="text-sm">{d.field_type === "checkbox" ? (t.custom_fields[d.key] ? "Yes" : "No") : String(t.custom_fields[d.key])}</dd>
              </div>
            ))}
          </dl>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          <select className="input !w-auto" value={t.status} onChange={(e) => setStatus(e.target.value as Status)} aria-label="Status">
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s.replace("_", " ")}</option>
            ))}
          </select>
          <button className="btn-ghost" onClick={() => setEditing(true)}>Edit</button>
          {t.is_active && <button className="btn-danger" onClick={del}>Deactivate</button>}
        </div>
      </div>

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="card space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">1 · ML predicted solution</h3>
          {conf !== null && <span className="text-xs text-slate-500">confidence {conf}%</span>}
        </div>
        {t.predicted_solution ? (
          <p className="rounded-md bg-slate-50 px-3 py-2 text-sm">{t.predicted_solution}</p>
        ) : (
          <p className="text-sm text-slate-500">No prediction available.</p>
        )}
        {conf !== null && (
          <div className="h-1.5 w-full overflow-hidden rounded bg-slate-100">
            <div className={`h-full ${conf >= 60 ? "bg-emerald-500" : conf >= 35 ? "bg-amber-500" : "bg-red-400"}`} style={{ width: `${conf}%` }} />
          </div>
        )}
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">2 · Customer response (RAG + local LLM)</h3>
          <AiBadge s={t.ai_status} />
        </div>

        {t.ai_error && (
          <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
            {t.ai_error}
          </div>
        )}

        <textarea
          className="input min-h-48"
          value={draft}
          placeholder={working ? "Generating a draft from the knowledge base…" : "No AI draft yet. You can write the response manually."}
          onChange={(e) => {
            setDraft(e.target.value);
            setDirty(true);
          }}
        />

        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" onClick={saveResponse} disabled={!draft.trim()}>Save response</button>
          <button className="btn-ghost" disabled={working || !t.predicted_solution} onClick={() => regenerate(false)}>
            {t.ai_status === "failed" ? "Retry draft" : "Regenerate draft"}
          </button>
          <button className="btn-ghost" disabled={working} onClick={() => regenerate(true)}>Re-run ML + draft</button>
          {saved && <span className="text-sm text-emerald-600">Saved ✓</span>}
          {t.final_response && !dirty && <span className="text-xs text-slate-500">Approved version saved</span>}
          {t.final_response && t.ai_response && t.final_response !== t.ai_response && !dirty && (
            <button className="text-xs text-indigo-600 hover:underline" onClick={() => { setDraft(t.ai_response!); setDirty(true); }}>
              Restore original AI draft
            </button>
          )}
        </div>

        {t.ai_sources && t.ai_sources.length > 0 && (
          <details className="rounded-md border border-slate-200 text-sm">
            <summary className="cursor-pointer px-3 py-2 font-medium text-slate-700">
              Knowledge-base sources used ({t.ai_sources.length})
            </summary>
            <ul className="divide-y divide-slate-100">
              {t.ai_sources.map((s, i) => (
                <li key={i} className="space-y-1 px-3 py-2">
                  <p className="text-xs text-slate-500">
                    {s.source} · {s.title} · relevance {s.score.toFixed(2)}
                  </p>
                  <p className="whitespace-pre-wrap text-slate-700">{s.text}</p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
