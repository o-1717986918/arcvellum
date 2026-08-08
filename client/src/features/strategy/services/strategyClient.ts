import {
  api,
  connectEventStream,
  query,
  type EventStreamConnection,
} from "@/services/api";
import type { StrategyProjection, TypedPlanEvent } from "../types";

export function fetchStrategy(projectRoot: string): Promise<StrategyProjection> {
  return api<{ ok: boolean; strategy: StrategyProjection }>(
    `/project/strategy?${query({ project_root: projectRoot })}`,
  ).then((response) => response.strategy);
}

export function observeStrategyEvents(
  projectRoot: string,
  onEvent: (event: TypedPlanEvent) => void,
): EventStreamConnection {
  return connectEventStream(
    `/project/strategy/events?${query({ project_root: projectRoot, follow: "true" })}`,
    (eventName, data) => {
      if (eventName === "plan-event") {
        onEvent(parseTypedPlanEvent(data));
      }
    },
  );
}

export function parseTypedPlanEvent(
  data: Record<string, unknown>,
): TypedPlanEvent {
  const eventId = typeof data.event_id === "string" ? data.event_id : "";
  const eventType =
    typeof data.event_type === "string"
      ? data.event_type
      : typeof data.type === "string"
        ? data.type
        : "";
  if (!eventId || !eventType) {
    throw new Error("invalid typed plan event");
  }
  return {
    event_id: eventId,
    event_type: eventType,
    plan_id: typeof data.plan_id === "string" ? data.plan_id : "",
    revision: typeof data.revision === "number" ? data.revision : undefined,
    created_at:
      typeof data.created_at === "string" ? data.created_at : undefined,
    scope_key: typeof data.scope_key === "string" ? data.scope_key : undefined,
  };
}
