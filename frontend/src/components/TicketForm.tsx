import { useState } from "react";
import { api, ApiError } from "../api";
import type { CustomValue, FieldDef, Priority, Ticket } from "../types";
import DynamicFields from "./DynamicFields";

interface Props {
  defs: FieldDef[];
  initial?: Ticket;
  onSaved: (t: Ticket) => void;
  onCancel: () => void;
}

const PRIORITIES: Priority[] = ["low", "medium", "high", "urgent"];

export default function TicketForm({ defs, initial, onSaved, onCancel }: Props) {
  const [customer, setCustomer] = useState(initial?.customer_name ?? "");
  const [subject, setSubject] = useState(initial?.subject ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [priority, setPriority] = useState<Priority>(initial?.priority ?? "medium");
  const [custom, setCustom] = useState<Record<string, CustomValue>>(initial?.custom_fields ?? {});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setErrors({});
    // checkboxes that were never touched are sent as false
    const cf = { ...custom };
    for (const d of defs) if (d.field_type === "checkbox" && cf[d.key] === undefined) cf[d.key] = false;
    try {
      const body = { customer_name: customer, subject, description, priority, custom_fields: cf };
      const t = initial ? await api.update(initial.id, body) : await api.create(body);
      onSaved(t);
    } catch (err) {
      const ae = err as ApiError;
      setError(ae.message);
      setErrors(ae.fieldErrors ?? {});
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-5">
      <h2 className="text-lg font-semibold">{initial ? `Edit ticket #${initial.id}` : "New ticket"}</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="customer">Customer name</label>
          <input id="customer" className="input" value={customer} onChange={(e) => setCustomer(e.target.value)} required />
        </div>
        <div>
          <label className="label" htmlFor="priority">Priority</label>
          <select id="priority" className="input" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
            {PRIORITIES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="label" htmlFor="subject">Subject</label>
        <input id="subject" className="input" value={subject} onChange={(e) => setSubject(e.target.value)} required minLength={3} />
      </div>
      <div>
        <label className="label" htmlFor="description">Description</label>
        <textarea id="description" className="input min-h-28" value={description} onChange={(e) => setDescription(e.target.value)} required minLength={5} />
      </div>

      {defs.length > 0 && (
        <div className="space-y-3 border-t border-slate-100 pt-4">
          <h3 className="text-sm font-semibold text-slate-700">Additional details</h3>
          <DynamicFields defs={defs} values={custom} errors={errors} onChange={(k, v) => setCustom((c) => ({ ...c, [k]: v }))} />
        </div>
      )}

      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : initial ? "Save changes" : "Create & analyse"}
        </button>
      </div>
    </form>
  );
}
