export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export type FitLabel = "strong" | "partial" | "non_fit";

export type TenderSummary = {
  id: number;
  external_id: string;
  title: string;
  agency: string;
  source: string;
  status: string;
  status_detail: string | null;
  published_date: string | null;
  closing_date: string | null;
  days_to_close: number | null;
  estimated_value_pkr: number | null;
  fit_score: number | null;
  fit_label: FitLabel | null;
  fit_reason: string | null;
};

export type Check = {
  id: number;
  requirement: string;
  type: string;
  threshold: string | null;
  mandatory: boolean;
  status: "pass" | "fail" | "unclear";
  reason: string;
  source_quote: string;
  method: string;
};

export type BidPack = {
  status: string;
  files: string[];
  generation_ms: number | null;
  error: string | null;
};

export type TenderDetail = TenderSummary & {
  document_url: string | null;
  scope_summary: string | null;
  bid_security: string | null;
  score_breakdown: { capability?: number; eligibility?: number; value_fit?: number; capped?: boolean };
  checks: Check[];
  bid_pack: BidPack | null;
};

export type Kpis = {
  tenders_scanned: number;
  tenders_total: number;
  strong_fits: number;
  total_fit_value_pkr: number;
  nearest_deadline: { tender_id: number; title: string; closing_date: string; days_to_close: number } | null;
  avg_bidpack_ms: number | null;
  demo_mode: boolean;
};

export type Registrations = {
  ntn: string | null;
  atl_status: string | null;
  pec_category: string | null;
  secp: string | null;
  pseb: string | null;
};

export type PastProject = { title: string; client: string; value_pkr: number; year: number };

export type Profile = {
  name: string;
  city: string;
  team_size: number;
  annual_turnover_pkr: number;
  years_in_business: number;
  capabilities: string[];
  registrations: Registrations;
  past_projects: PastProject[];
};

export type RunStep = {
  id: number;
  step: number;
  scope: "orchestrator" | "analyst" | "bidpack";
  tool: string;
  tender_id: number | null;
  thought_summary: string;
  status: "running" | "done" | "error";
  duration_ms: number;
  input_summary: string;
  output_summary: string;
  tokens: number;
};

export type Run = {
  id: number;
  goal: string;
  status: "queued" | "running" | "completed" | "failed";
  demo_mode: boolean;
  final_answer: string | null;
  error: string | null;
  best_tender_id: number | null;
  tokens: number;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error(`Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return res.json();
}

export function formatPkr(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Not stated";
  if (value >= 1e9) return `PKR ${+(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `PKR ${+(value / 1e6).toFixed(1)}M`;
  return `PKR ${value.toLocaleString("en-PK")}`;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "–";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
