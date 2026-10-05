import type { AgentRunEvent, RunStatus } from "@yoyo/core";

const TERMINAL_STATUSES = new Set<RunStatus>(["completed", "cancelled", "failed"]);

/** 终态只能以后端 Run 状态为准，不能根据本地事件名称推断。 */
export function isTerminalRun(status: RunStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

export function canCancelRun(status: RunStatus): boolean {
  return !isTerminalRun(status) && status !== "finalizing";
}

export function canContinueRun(status: RunStatus): boolean {
  return status === "paused";
}

/** 合并断线前后的事件，按 eventSeq 去重并保持回放顺序。 */
export function mergeRunEvents(
  current: AgentRunEvent[],
  incoming: AgentRunEvent[],
): AgentRunEvent[] {
  const bySequence = new Map<number, AgentRunEvent>();
  for (const event of [...current, ...incoming]) bySequence.set(event.eventSeq, event);
  return [...bySequence.values()].sort((left, right) => left.eventSeq - right.eventSeq);
}

export function latestEventSequence(events: AgentRunEvent[]): number {
  return events.reduce((latest, event) => Math.max(latest, event.eventSeq), 0);
}
