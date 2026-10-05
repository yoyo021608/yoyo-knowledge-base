import type { AgentRun, AgentRunEvent, QuestionResult } from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

import { canCancelRun, canContinueRun } from "./runState";

interface Props {
  run: AgentRun | null;
  events: AgentRunEvent[];
  result: QuestionResult | null;
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

const EVIDENCE_LABELS: Record<QuestionResult["answer"]["evidenceStatus"], string> = {
  sufficient: "证据充分",
  insufficient: "证据不足",
  failed: "证据检索失败",
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

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function ModeResult({ run, result }: { run: AgentRun; result: QuestionResult }) {
  const value = result.modeResult;
  if (!value) return null;
  if (run.mode === "research") {
    const subquestions = stringList(value.subquestions);
    const unresolved = stringList(value.unresolved_questions);
    return (
      <details>
        <summary>研究过程</summary>
        {subquestions.length > 0 && <ol>{subquestions.map((item) => <li key={item}>{item}</li>)}</ol>}
        {unresolved.length > 0 && <p>仍缺少证据：{unresolved.join("；")}</p>}
      </details>
    );
  }
  if (run.mode === "comparison") {
    return <p>已对齐 {Number(value.compared_scope_count ?? 0)} 个文档版本的证据。</p>;
  }
  if (run.mode === "study") {
    const exercise = typeof value.exercise === "string" ? value.exercise : null;
    const verdict = typeof value.verdict === "string" ? value.verdict : null;
    const score = typeof value.automatic_score === "number" ? value.automatic_score : null;
    return (
      <div>
        {exercise && <p><strong>练习：</strong>{exercise}</p>}
        {verdict && <p><strong>判定：</strong>{verdict}{score === null ? "" : `（得分 ${(score * 100).toFixed(0)}%）`}</p>}
      </div>
    );
  }
  return null;
}

/** 展示后端 Run 与持久化事件，不把事件当作最终消息数据。 */
export function RunActivity({
  run,
  events,
  result,
  pending,
  error,
  onCancel,
  onResume,
  onRefresh,
}: Props) {
  if (!run && !error && !result) return null;
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
      {result && (
        <div className="run-result">
          <p><strong>证据状态：</strong>{EVIDENCE_LABELS[result.answer.evidenceStatus]}</p>
          <p>{result.answer.text}</p>
          <p>
            命中 {result.evaluation.hitCount} 条证据，引用覆盖率
            {` ${(result.evaluation.citationCoverage * 100).toFixed(0)}%`}
          </p>
          {result.answer.citations.length > 0 && (
            <details>
              <summary>本次引用（{result.answer.citations.length}）</summary>
              <ul>
                {result.answer.citations.map((citation) => (
                  <li key={`${citation.documentVersionId}:${citation.chunkId}`}>
                    <strong>{citation.titleSnapshot}</strong>：{citation.quote}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {run && <ModeResult run={run} result={result} />}
        </div>
      )}
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
