export interface ThroughputUsage {
  input_tokens: number;
  non_cached_input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  cost_usd: number;
}

export interface ThroughputContextMetric {
  mode: "" | "off" | "shadow" | "bounded";
  requested_mode: "" | "off" | "shadow" | "bounded";
  task_kind: string;
  risk_level: string;
  contract_status: string;
  rollout_reason: string;
  rollout_policy_digest: string;
  target_inline_characters: number;
  enforced_inline_characters: number;
  first_turn_visible_characters: number;
  exact_on_demand_characters: number;
  excluded_characters: number;
  authorized_characters: number;
  mandatory_characters: number;
  included_file_count: number;
  on_demand_file_count: number;
  excluded_file_count: number;
  budget_overage_count: number;
  budget_overage_characters: number;
  digest: string;
}

export interface ThroughputStageSummary {
  sample_count: number;
  total_seconds: number;
  average_seconds: number;
  max_seconds: number;
}

export interface ThroughputTaskMetric {
  task_id: string;
  route: string;
  scene_id: string;
  role: string;
  runtime_role: string;
  provider: string;
  model: string;
  model_identity: string;
  context_digest: string;
  model_turns: number;
  repairs: number;
  retries: number;
  first_validation_passed: boolean | null;
  usage: ThroughputUsage;
  context: ThroughputContextMetric;
  stage_seconds: Record<string, number>;
}

export interface ThroughputAttribution {
  key: string;
  task_count: number;
  model_turns: number;
  repairs: number;
  retries: number;
  usage: ThroughputUsage;
}

export interface ThroughputProjection {
  schema: "arcvellum/throughput-projection/v1";
  mode: "measure-only";
  event_count: number;
  task_count: number;
  bundle_count: number;
  model_turns: number;
  repairs: number;
  retries: number;
  first_validation: {
    evaluated_tasks: number;
    passed_first_attempt: number;
    failed_first_attempt: number;
    pass_rate: number | null;
  };
  usage: ThroughputUsage;
  context: {
    reported_tasks: number;
    first_turn_visible_characters: number;
    median_first_turn_visible_characters: number;
    exact_on_demand_characters: number;
    median_exact_on_demand_characters: number;
    excluded_characters: number;
    authorized_characters: number;
    budget_overage_count: number;
    budget_overage_characters: number;
  };
  attribution: {
    by_scene: ThroughputAttribution[];
    by_role: ThroughputAttribution[];
    by_runtime_role: ThroughputAttribution[];
    by_model: ThroughputAttribution[];
    by_context_digest: ThroughputAttribution[];
  };
  stages: Record<string, ThroughputStageSummary>;
  coverage: {
    event_ledger: boolean;
    bundle_events: boolean;
    cache_tokens: boolean;
    scene_attribution: boolean;
    context_budget: boolean;
    provider_model_attribution: boolean;
  };
  tasks: ThroughputTaskMetric[];
  tasks_truncated: boolean;
  revision: string;
}
