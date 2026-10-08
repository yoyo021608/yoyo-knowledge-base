import { useState } from "react";

import { buildApiUrl, fetchHealth, type AgentMode } from "@yoyo/core";
import { Button } from "@yoyo/ui";

import type { ViewLinkComponent } from "./navigation";

interface WorkspaceViewProps {
  apiBaseUrl: string;
  LinkComponent: ViewLinkComponent;
  onStartResearch: (draft: WorkspaceQuestionDraft) => void;
}

export interface WorkspaceQuestionDraft {
  mode: AgentMode;
  question: string;
}

const researchModes = [
  { value: "research", label: "深度研究" },
  { value: "quick", label: "快速问答" },
  { value: "comparison", label: "文档对比" },
  { value: "study", label: "学习模式" },
] as const satisfies ReadonlyArray<{ value: AgentMode; label: string }>;

const promptSuggestions: Record<AgentMode, string[]> = {
  research: ["梳理一个主题的主要观点", "从多份资料形成研究结论"],
  quick: ["解释资料中的核心概念", "定位某个结论的出处"],
  comparison: ["比较两份文档的观点差异", "找出版本更新带来的变化"],
  study: ["根据资料生成学习路径", "把知识点转换成练习题"],
};

/** 首页只装配真实模块入口和服务状态，不越过业务模块读取内部数据。 */
export function WorkspaceView({ apiBaseUrl, LinkComponent: Link, onStartResearch }: WorkspaceViewProps) {
  const [status, setStatus] = useState("未检查");
  const [mode, setMode] = useState<AgentMode>("research");
  const [prompt, setPrompt] = useState("");
  const activeMode = researchModes.find((item) => item.value === mode) ?? researchModes[0];

  function startResearch(): void {
    const question = prompt.trim();
    if (!question) return;
    onStartResearch({ mode, question });
  }

  async function handleCheck(): Promise<void> {
    try {
      const result = await fetchHealth(apiBaseUrl);
      setStatus(result.status);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "检查失败");
    }
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-heading">
        <div>
          <p className="page-eyebrow">YOUR KNOWLEDGE AT WORK</p>
          <h1>知识工作台</h1>
          <p>让积累的知识重新进入此刻的问题，让阅读、探索与思考在这里继续生长</p>
        </div>
        <Link className="dashboard-primary-action" to="/sessions">
          <span aria-hidden="true">＋</span> 新建研究
        </Link>
      </header>

      <section className="dashboard-grid" aria-label="知识工作台概览">
        <article className="dashboard-panel source-overview">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon">◎</span><h2>知识来源</h2></div>
            <Link to="/documents">管理资料 <span aria-hidden="true">→</span></Link>
          </div>
          <strong className="source-overview-title">把文档、网页和笔记汇入同一个空间，让它们彼此连接，随时可用</strong>
          <ul className="source-capabilities">
            <li><span>文</span><p><strong>原始资料</strong><small>保留内容与最初的来处</small></p><b>有出处</b></li>
            <li><span>版</span><p><strong>时间脉络</strong><small>看见内容如何随时间变化</small></p><b>可回看</b></li>
            <li><span>联</span><p><strong>知识连接</strong><small>让主题、概念与资料彼此照应</small></p><b>有联系</b></li>
          </ul>
          <Link className="panel-secondary-action" to="/documents">进入知识库</Link>
        </article>

        <article className="dashboard-panel research-composer">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon primary">✦</span><h2>开始研究</h2></div>
            <span className="composer-hint">让已有知识回应新的问题</span>
          </div>
          <div className="research-mode-tabs" role="tablist" aria-label="研究模式">
            {researchModes.map((item) => (
              <button
                aria-selected={mode === item.value}
                className={mode === item.value ? "active" : ""}
                key={item.value}
                onClick={() => setMode(item.value)}
                role="tab"
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="research-input">
            <span className="sr-only">研究问题</span>
            <textarea
              onChange={(event) => setPrompt(event.target.value)}
              placeholder={`写下你想通过${activeMode.label}了解的问题，或先选择一个示例…`}
              value={prompt}
            />
          </label>
          <div className="prompt-suggestions">
            {promptSuggestions[mode].map((suggestion) => (
              <button key={suggestion} onClick={() => setPrompt(suggestion)} type="button">
                <span aria-hidden="true">↗</span>{suggestion}
              </button>
            ))}
          </div>
          <footer className="composer-footer">
            <p><span aria-hidden="true">⌘</span> 问题、过程与参考内容会自然保留</p>
            <button disabled={!prompt.trim()} onClick={startResearch} type="button">
              进入研究空间 <span aria-hidden="true">→</span>
            </button>
          </footer>
        </article>

        <article className="dashboard-panel run-overview">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon">↻</span><h2>思考进展</h2></div>
            <Link to="/sessions">查看会话</Link>
          </div>
          <ol className="run-stages">
            <li><span>01</span><p><strong>理解此刻的问题</strong><small>看清真正需要探索的内容</small></p></li>
            <li><span>02</span><p><strong>唤醒相关知识</strong><small>让过去的积累重新参与思考</small></p></li>
            <li><span>03</span><p><strong>核对观点与来处</strong><small>确认每个判断都有内容支撑</small></p></li>
            <li><span>04</span><p><strong>整理新的理解</strong><small>让答案与参考内容一起留下</small></p></li>
          </ol>
          <p className="run-empty">探索开始后，新的线索会在这里逐步展开，离开之后也能继续</p>
        </article>

        <article className="dashboard-panel document-entry">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon">▤</span><h2>汇入知识</h2></div>
            <Link to="/documents">添加内容</Link>
          </div>
          <div className="source-type-grid">
            <span><b>NOTE</b>随手记录</span>
            <span><b>FILE</b>文档资料</span>
            <span><b>WEB</b>网页内容</span>
            <span><b>VERSION</b>内容演变</span>
          </div>
          <p>内容变化时，过去的版本与已有联系仍会完整保留</p>
        </article>

        <article className="dashboard-panel knowledge-map-card">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon">⌘</span><h2>知识之间</h2></div>
            <span className="panel-status">发现隐藏的联系</span>
          </div>
          <div className="knowledge-map" aria-label="知识关系示意图">
            <span className="map-line line-one" aria-hidden="true" />
            <span className="map-line line-two" aria-hidden="true" />
            <span className="map-line line-three" aria-hidden="true" />
            <span className="map-node node-center">知识</span>
            <span className="map-node node-document">文档</span>
            <span className="map-node node-entity">实体</span>
            <span className="map-node node-topic">主题</span>
          </div>
          <p>把文档、主题与概念连接起来，让熟悉的内容显现新的线索</p>
        </article>

        <article className="dashboard-panel evidence-card">
          <div className="dashboard-panel-heading">
            <div><span className="panel-icon">✓</span><h2>有来处的答案</h2></div>
            <span className="panel-status">观点与原文相连</span>
          </div>
          <div className="evidence-ring" aria-hidden="true"><span>引</span></div>
          <div className="evidence-copy">
            <strong>每个重要观点都连接着参考内容</strong>
            <p>沿着答案回到原文，看见理解如何一步步形成</p>
          </div>
          <div className="service-check">
            <p><small>后端服务</small><strong>{status}</strong><span>{buildApiUrl(apiBaseUrl, "/health")}</span></p>
            <Button onClick={() => void handleCheck()}>检查连接</Button>
          </div>
        </article>
      </section>
    </main>
  );
}
