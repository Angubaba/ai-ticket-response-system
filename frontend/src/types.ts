export type FieldType = "text" | "dropdown" | "number" | "date" | "checkbox";
export type Status = "open" | "in_progress" | "resolved" | "closed";
export type Priority = "low" | "medium" | "high" | "urgent";
export type AiStatus = "pending" | "generating" | "done" | "failed" | "skipped";

export interface FieldDef {
  id: number;
  key: string;
  label: string;
  field_type: FieldType;
  required: boolean;
  options: string[] | null;
  sort_order: number;
  is_active: boolean;
}

export type CustomValue = string | number | boolean | null;

export interface Source {
  text: string;
  source: string;
  title: string;
  score: number;
}

export interface Ticket {
  id: number;
  customer_name: string;
  subject: string;
  description: string;
  category: string | null;
  priority: Priority;
  status: Status;
  predicted_solution: string | null;
  ml_confidence: number | null;
  ai_response: string | null;
  final_response: string | null;
  ai_sources: Source[] | null;
  ai_status: AiStatus;
  ai_error: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  custom_fields: Record<string, CustomValue>;
}

export interface TicketList {
  items: Ticket[];
  total: number;
}

export interface Health {
  api: string;
  database: boolean;
  ml_model: boolean;
  ollama: boolean;
  ollama_model_available: boolean;
  knowledge_base_chunks: number;
}

export interface TicketInput {
  customer_name: string;
  subject: string;
  description: string;
  category?: string | null;
  priority: Priority;
  status?: Status;
  custom_fields: Record<string, CustomValue>;
}
