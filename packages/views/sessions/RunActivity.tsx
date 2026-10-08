import type { AgentRun, AgentRunEvent } from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

import { canCancelRun, canContinueRun } from "./runState";

interface Props {
  run: AgentRun | null;
  events: AgentRunEvent[];
  pending: boolean;
  error: string;
  onCancel: () => Promise<void>;
  onResume: () => Promise<void>;
  onRefresh: () => Promise<void>;
}

const STATUS_LABELS: Record<AgentRun["status"], string> = {
  queued: "等待执行",
  running: "执行中",
  paused: "已暂停",
  finalizing: "正在保存最终结果",
  cancelled: "已取消",
  completed: "已完成",
  failed: "失败",
};

const STEP_LABELS: Record<AgentRun["step"], string> = {
  rewrite: "理解问题",
  retrieve: "检索证据",
  generate: "生成回答",
  persist_answer: "保存回答",
};

const EVENT_LABELS: Record<string, string> = {
  "run.created": "已创建运行",
  "run.started": "已开始执行",
  "rewrite.completed": "问题理解完成",
  "retrieval.completed": "证据检索完成",
  "generation.completed": "回答生成完成",
  "answer.ready": "回答等待保存",
  "run.finalizing": "正在保存最终结果",
  "run.completed": "运行完成",
  "run.paused": "运行已暂停",
  "run.continued": "运行已继续",
  "run.cancelled": "运行已取消",
  "run.failed": "运行失败",
  "generation.interrupted": "上次生成被中断，准备重新生成",
};

/** 展示后端 Run 与持久化事件，不把事件当作最终消息数据。 */
export function RunActivity({
  run,
  events,
  pending,
  error,
  onCancel,
  onResume,
  onRefresh,
}: Props) {
  if (!run && !error) return null;
  return (
    <Card>
      <h2>本次运行</h2>
      {run && (
        <>
          <p><strong>状态：</strong>{STATUS_LABELS[run.status]} · {STEP_LABELS[run.step]}</p>
          {run.failureReason && <p role="alert">{run.failureReason}</p>}
          <div className="account-actions">
            <Button disabled={pending} onClick={() => void onRefresh()}>刷新状态</Button>
            {canCancelRun(run.status) && <Button disabled={pending} onClick={() => void onCancel()}>取消</Button>}
            {canContinueRun(run.status) && <Button disabled={pending} onClick={() => void onResume()}>继续</Button>}
          </div>
        </>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
      {events.length > 0 && (
        <details>
          <summary>过程事件（{events.length}）</summary>
          <ol className="run-events">
            {events.map((event) => (
              <li key={event.id}><code>#{event.eventSeq}</code> {EVENT_LABELS[event.eventType] ?? event.eventType}</li>
            ))}
          </ol>
        </details>
      )}
    </Card>
  );
}
