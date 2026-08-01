import type { StrategyProjection, TypedPlanEvent } from "./types";

export interface PlanOverlayNode {
  id: string;
  kind: "scope" | "event";
  label: string;
  slot: number;
  detail?: string;
}

export interface PlanOverlay {
  plan_id: string | null;
  revision: number | null;
  status: string | null;
  nodes: PlanOverlayNode[];
  event_count: number;
}

const MAX_EVENT_SLOTS = 12;

export function projectPlanOverlay(
  strategy: StrategyProjection | null,
  events: TypedPlanEvent[],
): PlanOverlay {
  const plan = strategy?.active_plan ?? null;
  const nodes: PlanOverlayNode[] = [];
  if (plan) {
    nodes.push({
      id: `scope:${plan.scope_kind}:${plan.scope_key}`,
      kind: "scope",
      label: plan.scope_key,
      slot: 0,
      detail: plan.status,
    });
  }
  events.slice(-MAX_EVENT_SLOTS).forEach((event, index) => {
    nodes.push({
      id: event.event_id,
      kind: "event",
      label: event.event_type,
      slot: index + 1,
      detail: event.created_at,
    });
  });
  return {
    plan_id: plan?.plan_id ?? null,
    revision: plan?.revision ?? null,
    status: plan?.status ?? null,
    nodes,
    event_count: events.length,
  };
}
