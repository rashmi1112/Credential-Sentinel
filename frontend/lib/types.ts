// Response/event shapes shared with the FastAPI backend.

export type Routing = "DEFER" | "OWN_UNMANAGED" | "OWN_STALE" | "UNKNOWN";

export interface RunEvent {
  type:
    | "node_update"
    | "reconciliation_item"
    | "assessment_item"
    | "urgency_item"
    | "plan_drafted"
    | "gate_reached"
    | "staging_attempt"
    | "staging_result"
    | "escalation"
    | "cutover_step"
    | "cutover_result"
    | "drift_summary"
    | "report_ready"
    | "run_completed"
    | "error";
  seq?: number;
  ts?: number;
  // node_update
  node?: string;
  message?: string;
  // reconciliation_item / assessment_item / urgency_item
  cred_id?: string;
  label?: string;
  routing?: Routing;
  // assessment_item
  days_to_expiry?: number;
  not_after?: string;
  expired?: boolean;
  consumers?: string[];
  consumer_count?: number;
  safe_to_rotate?: boolean;
  blocked_reason?: string | null;
  expiry_source?: string; // "real_tls" | "simulated" | "unknown"
  kind?: string;
  // urgency_item
  score?: number;
  band?: UrgencyBand;
  breakdown?: UrgencyBreakdown;
  // plan_drafted
  source?: string;
  impact_summary?: string;
  steps?: string[];
  // gate_reached
  gate?: GateName;
  payload?: GatePayload;
  // staging_attempt / staging_result / cutover_step
  status?: string;
  step?: string;
  attempt?: number;
  attempts?: number;
  // escalation
  stage?: string;
  reason?: string;
  // drift_summary
  prior_run_id?: string | null;
  first_run?: boolean;
  new?: DriftNew[];
  changed?: DriftChanged[];
  stuck?: DriftStuck[];
  // report_ready
  headline?: string;
  narrative?: string;
  counts?: Record<string, number>;
}

export interface DriftNew {
  cred_id: string;
  label: string;
  routing: Routing;
}
export interface DriftChanged {
  cred_id: string;
  label: string;
  from: Routing;
  to: Routing;
}
export interface DriftStuck {
  cred_id: string;
  label: string;
  disposition: string;
}

export type UrgencyBand = "critical" | "high" | "medium" | "low";

export interface UrgencyBreakdown {
  expiry: number;
  blast_radius: number;
  difficulty: number;
}

export interface Urgency {
  score: number;
  band: UrgencyBand;
  breakdown: UrgencyBreakdown;
}

export interface RotationPlan {
  steps: string[];
  impact_summary: string;
  risk: string;
  source: string; // "nebius" | "fallback" | "fallback_error"
  model?: string | null;
}

export type GateName = "staging" | "cutover";

export interface GateItem {
  cred_id: string;
  label: string;
  proposed_action: string;
  // Enriched at Gate 1 (staging) by assess/prioritize/plan:
  kind?: string;
  days_to_expiry?: number;
  not_after?: string;
  expired?: boolean;
  expiry_source?: string; // "real_tls" | "simulated" | "unknown"
  consumers?: string[];
  consumer_count?: number;
  urgency?: Urgency;
  plan?: RotationPlan;
}

export interface GatePayload {
  gate: GateName;
  items: GateItem[];
}

export type DecisionAction = "approve" | "reject";

export interface Decision {
  cred_id: string;
  action: DecisionAction;
  edits?: Record<string, unknown>;
}

export interface RunSnapshot {
  run_id: string;
  status: string;
  live_inventory: { id: string; kind: string; label: string }[];
  managed_inventory: { id: string; store: string; rotating: boolean }[];
  reconciliation: Record<string, Routing>;
  queue: string[];
  staging_results: Record<string, { status: string }>;
  pending_gate: GatePayload | null;
  next: string[];
}

export interface RunListItem {
  run_id: string;
  started_at: number;
  updated_at: number;
  event_count: number;
  last_event_type: string | null;
}
