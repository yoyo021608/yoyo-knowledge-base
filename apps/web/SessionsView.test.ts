import { describe, expect, it } from "vitest";

import type { AgentRunEvent } from "@yoyo/core";

import {
  canCancelRun,
  canContinueRun,
  isTerminalRun,
  latestEventSequence,
  mergeRunEvents,
} from "../../packages/views/sessions/runState";

function event(sequence: number): AgentRunEvent {
  return {
    id: `event-${sequence}`,
    runId: "run-1",
    eventSeq: sequence,
    eventType: "run.progress",
    payload: {},
    createdAt: "2026-10-04T10:00:00Z",
  };
}

describe("Run 视图状态", () => {
  it("只把后端定义的三个状态判断为终态", () => {
    expect(isTerminalRun("completed")).toBe(true);
    expect(isTerminalRun("cancelled")).toBe(true);
    expect(isTerminalRun("failed")).toBe(true);
    expect(isTerminalRun("finalizing")).toBe(false);
  });

  it("只允许暂停运行继续，并禁止最终保存阶段取消", () => {
    expect(canContinueRun("paused")).toBe(true);
    expect(canContinueRun("running")).toBe(false);
    expect(canCancelRun("running")).toBe(true);
    expect(canCancelRun("finalizing")).toBe(false);
  });

  it("重连事件按序号合并并去重", () => {
    const merged = mergeRunEvents([event(1), event(3)], [event(2), event(3)]);
    expect(merged.map((value) => value.eventSeq)).toEqual([1, 2, 3]);
    expect(latestEventSequence(merged)).toBe(3);
  });
});
