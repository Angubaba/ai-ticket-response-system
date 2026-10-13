import type { FieldDef, Health, Ticket, TicketInput, TicketList } from "./types";

export class ApiError extends Error {
  fieldErrors: Record<string, string>;
  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.fieldErrors = fieldErrors;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError("Cannot reach the backend. Is it running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const d = body?.detail;
    if (d && typeof d === "object" && !Array.isArray(d)) throw new ApiError(d.message ?? "Request failed", d.errors ?? {});
    if (Array.isArray(d)) throw new ApiError(d.map((e: { loc: string[]; msg: string }) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; "));
    throw new ApiError(typeof d === "string" ? d : `Request failed (${res.status})`);
  }
  return body as T;
}

export const api = {
  health: () => req<Health>("/api/health"),
  fields: () => req<FieldDef[]>("/api/fields"),
  createField: (f: Pick<FieldDef, "key" | "label" | "field_type" | "required" | "options">) =>
    req<FieldDef>("/api/fields", { method: "POST", body: JSON.stringify(f) }),
  removeField: (id: number) => req<void>(`/api/fields/${id}`, { method: "DELETE" }),

  tickets: (params: Record<string, string>) => req<TicketList>(`/api/tickets?${new URLSearchParams(params)}`),
  ticket: (id: number) => req<Ticket>(`/api/tickets/${id}`),
  create: (t: TicketInput) => req<Ticket>("/api/tickets", { method: "POST", body: JSON.stringify(t) }),
  update: (id: number, t: Partial<TicketInput>) => req<Ticket>(`/api/tickets/${id}`, { method: "PATCH", body: JSON.stringify(t) }),
  remove: (id: number) => req<void>(`/api/tickets/${id}`, { method: "DELETE" }),
  saveResponse: (id: number, final_response: string) =>
    req<Ticket>(`/api/tickets/${id}/response`, { method: "PUT", body: JSON.stringify({ final_response }) }),
  regenerate: (id: number, repredict = false) =>
    req<Ticket>(`/api/tickets/${id}/regenerate?repredict=${repredict}`, { method: "POST" }),
};
