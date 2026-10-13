import { useState } from "react";
import { api } from "../api";
import type { FieldDef, FieldType } from "../types";

const TYPES: FieldType[] = ["text", "dropdown", "number", "date", "checkbox"];

export default function FieldAdmin({ defs, onChanged }: { defs: FieldDef[]; onChanged: () => void }) {
  const [key, setKey] = useState("");
  const [label, setLabel] = useState("");
  const [type, setType] = useState<FieldType>("text");
  const [required, setRequired] = useState(false);
  const [options, setOptions] = useState("");
  const [error, setError] = useState("");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createField({
        key,
        label,
        field_type: type,
        required,
        options: type === "dropdown" ? options.split(",").map((s) => s.trim()).filter(Boolean) : null,
      });
      setKey("");
      setLabel("");
      setOptions("");
      setRequired(false);
      onChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="space-y-5">
      <div className="card">
        <h2 className="mb-1 text-lg font-semibold">Custom fields</h2>
        <p className="mb-4 text-sm text-slate-600">
          Fields are stored as rows, not columns. Adding one here changes the ticket form immediately, with no code change or migration.
        </p>
        <ul className="divide-y divide-slate-100">
          {defs.map((d) => (
            <li key={d.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                <span className="font-medium">{d.label}</span>{" "}
                <span className="text-slate-500">
                  ({d.key} · {d.field_type}
                  {d.required ? " · required" : ""}
                  {d.options ? ` · ${d.options.join(", ")}` : ""})
                </span>
              </span>
              <button
                className="text-xs text-red-600 hover:underline"
                onClick={async () => {
                  await api.removeField(d.id);
                  onChanged();
                }}
              >
                Deactivate
              </button>
            </li>
          ))}
          {defs.length === 0 && <li className="py-2 text-sm text-slate-500">No custom fields defined.</li>}
        </ul>
      </div>

      <form onSubmit={add} className="card space-y-4">
        <h3 className="font-semibold">Add a field</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label" htmlFor="f-label">Label</label>
            <input id="f-label" className="input" value={label} onChange={(e) => { setLabel(e.target.value); if (!key) setKey(""); }} onBlur={() => !key && setKey(label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 59))} required />
          </div>
          <div>
            <label className="label" htmlFor="f-key">Key</label>
            <input id="f-key" className="input" value={key} onChange={(e) => setKey(e.target.value)} pattern="^[a-z][a-z0-9_]{0,59}$" title="lowercase snake_case" required />
          </div>
          <div>
            <label className="label" htmlFor="f-type">Type</label>
            <select id="f-type" className="input" value={type} onChange={(e) => setType(e.target.value as FieldType)}>
              {TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
        {type === "dropdown" && (
          <div>
            <label className="label" htmlFor="f-opts">Options (comma separated)</label>
            <input id="f-opts" className="input" value={options} onChange={(e) => setOptions(e.target.value)} required />
          </div>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
          Required
        </label>
        {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button className="btn-primary">Add field</button>
      </form>
    </div>
  );
}
