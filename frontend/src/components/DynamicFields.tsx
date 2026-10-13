import type { CustomValue, FieldDef } from "../types";

interface Props {
  defs: FieldDef[];
  values: Record<string, CustomValue>;
  errors: Record<string, string>;
  onChange: (key: string, v: CustomValue) => void;
}

/** Renders any set of field definitions. No field is hardcoded here. */
export default function DynamicFields({ defs, values, errors, onChange }: Props) {
  if (defs.length === 0) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {defs.map((d) => {
        const v = values[d.key];
        const err = errors[d.key];
        const common = { id: `cf-${d.key}`, className: `input ${err ? "border-red-400" : ""}` };
        let control: JSX.Element;
        switch (d.field_type) {
          case "dropdown":
            control = (
              <select {...common} value={(v as string) ?? ""} onChange={(e) => onChange(d.key, e.target.value || null)}>
                <option value="">Select…</option>
                {(d.options ?? []).map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            );
            break;
          case "number":
            control = (
              <input {...common} type="number" value={(v as number | string | null) ?? ""} onChange={(e) => onChange(d.key, e.target.value === "" ? null : Number(e.target.value))} />
            );
            break;
          case "date":
            control = <input {...common} type="date" value={(v as string) ?? ""} onChange={(e) => onChange(d.key, e.target.value || null)} />;
            break;
          case "checkbox":
            control = (
              <label className="flex items-center gap-2 py-2 text-sm">
                <input id={common.id} type="checkbox" className="h-4 w-4 rounded border-slate-300 text-indigo-600" checked={Boolean(v)} onChange={(e) => onChange(d.key, e.target.checked)} />
                Yes
              </label>
            );
            break;
          default:
            control = <input {...common} type="text" value={(v as string) ?? ""} onChange={(e) => onChange(d.key, e.target.value)} />;
        }
        return (
          <div key={d.key}>
            <label htmlFor={`cf-${d.key}`} className="label">
              {d.label}
              {d.required && <span className="text-red-500"> *</span>}
            </label>
            {control}
            {err && <p className="mt-1 text-xs text-red-600">{err}</p>}
          </div>
        );
      })}
    </div>
  );
}
