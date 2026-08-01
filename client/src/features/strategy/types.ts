export interface StrategySettings {
  enabled: boolean;
  mode: string;
  preset: string;
}

export interface ActivePlanSummary {
  plan_id: string;
  revision: number;
  status: string;
  scope_kind: string;
  scope_key: string;
}

export interface StrategyProjection {
  schema: string;
  settings: StrategySettings;
  active_plan: ActivePlanSummary | null;
  rolling_horizon: unknown;
}

export interface TypedPlanEvent {
  event_id: string;
  event_type: string;
  plan_id: string;
  revision?: number;
  created_at?: string;
  scope_key?: string;
}
