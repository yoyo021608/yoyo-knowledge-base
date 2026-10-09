import type { ViewLinkComponent } from "./navigation";

interface HomeViewProps {
  isAuthenticated?: boolean;
  LinkComponent: ViewLinkComponent;
}

const modules = [
  {
    number: "01",
    name: "KNOWLEDGE LIBRARY",
    title: "让资料在连接中成为知识",
    description: "把文档、笔记与网页汇入同一个空间，让重要内容彼此关联，随时可用",
    to: "/documents",
  },
  {
    number: "02",
    name: "AI RESEARCH",
    title: "让问题在探索中获得答案",
    description: "从已有知识中寻找线索、比较观点、核对依据，让理解一步步变得清晰",
    to: "/workspace",
  },
  {
    number: "03",
    name: "CONTINUOUS MEMORY",
    title: "让每一次思考自然延续",
    description: "保留讨论脉络、阅读依据与阶段成果，回来时仍能从熟悉的位置继续",
    to: "/sessions",
  },
  {
    number: "04",
    name: "TRACEABLE ANSWERS",
    title: "让每一个结论都循迹而归",
    description: "让回答始终连接具体版本与原文片段，即使内容后来变化，也能看见理解从何而来",
    to: "/sessions",
  },
];

/** 项目首页只解释产品定位、模块协作和核心价值，不承载具体业务操作。 */
export function HomeView({ isAuthenticated = false, LinkComponent: Link }: HomeViewProps) {
  return (
    <main className="project-home">
      <section className="project-hero" aria-labelledby="project-title">
        <div className="project-hero-copy">
          <p className="project-kicker"><span aria-hidden="true" /> A SPACE FOR CONNECTED KNOWLEDGE</p>
          <h1 id="project-title">一个空间<span>让知识连接</span><span>让思考生长</span></h1>
          <p className="project-lead">
            收拢散落的内容 连接每一份积累<br />
            让答案有来处 让探索有延续
          </p>
          <div className="project-actions">
            <Link className="project-primary" to="/workspace">{isAuthenticated ? "进入知识工作台" : "开始建立知识空间"} <span aria-hidden="true">→</span></Link>
            <Link className="project-secondary" to="/documents">{isAuthenticated ? "查看知识库" : "从第一份资料开始"}</Link>
          </div>
          <div className="project-traits" aria-label="产品特点">
            <span>知识彼此连接</span><span>答案有迹可循</span><span>思考持续生长</span>
          </div>
        </div>

        <div className="project-proof" aria-label="可信回答流程示意">
          <div className="proof-header">
            <p><span aria-hidden="true">✦</span><strong>让知识回应新的问题</strong></p>
            <span>FROM KNOWLEDGE TO INSIGHT</span>
          </div>
          <div className="proof-question">当新的问题出现，已有知识会如何回应</div>
          <div className="proof-flow">
            <span><b>01</b>理解此刻的问题<small>找到真正需要回答的内容</small></span>
            <i aria-hidden="true">→</i>
            <span><b>02</b>唤醒相关知识<small>让过去的积累重新相遇</small></span>
            <i aria-hidden="true">→</i>
            <span><b>03</b>形成新的理解<small>让观点与原文彼此照应</small></span>
          </div>
          <div className="proof-answer">
            <span className="proof-citation">1</span>
            <p><strong>观点与出处始终同行</strong>每一次理解都能回到当时使用的原始内容</p>
          </div>
          <div className="proof-footer">
            <span><i /> 思考进度已保留</span>
            <span><b>相关内容已连接</b></span>
          </div>
        </div>
      </section>

      <section className="project-section" aria-labelledby="capability-title">
        <div className="project-section-heading">
          <div><p className="page-eyebrow">A LIVING KNOWLEDGE SPACE</p><h2 id="capability-title">一个空间 <span>承载知识从积累到生长</span></h2></div>
          <p>让散落的信息逐渐形成联系，在真正需要时转化为新的理解</p>
        </div>
        <div className="module-showcase">
          {modules.map((module) => (
            <Link key={module.name} to={module.to}>
              <span className="module-number">{module.number}</span>
              <p>{module.name}</p>
              <h3>{module.title}</h3>
              <small>{module.description}</small>
              <b aria-hidden="true">↗</b>
            </Link>
          ))}
        </div>
      </section>

      <section className="project-flow-section" aria-labelledby="data-flow-title">
        <div className="project-section-heading">
          <div><p className="page-eyebrow">KNOWLEDGE JOURNEY</p><h2 id="data-flow-title">知识从被保存 到真正派上用场</h2></div>
          <p>内容在使用中获得结构，也在新的问题里生长出新的意义</p>
        </div>
        <div className="project-data-flow">
          <article><span>CAPTURE</span><b>收下值得保留的内容</b><p>让不同来源在同一个空间相遇</p></article>
          <i aria-hidden="true">→</i>
          <article><span>CONNECT</span><b>发现内容之间的联系</b><p>看见主题、概念与资料如何彼此照应</p></article>
          <i aria-hidden="true">→</i>
          <article><span>EXPLORE</span><b>围绕问题唤醒知识</b><p>让真正相关的内容参与此刻的思考</p></article>
          <i aria-hidden="true">→</i>
          <article><span>GROW</span><b>留住答案与探索的脉络</b><p>让出处与过程成为下一次思考的上下文</p></article>
        </div>
      </section>

      <section className="project-innovation" aria-labelledby="innovation-title">
        <div>
          <p className="page-eyebrow">DESIGNED FOR CONTINUITY</p>
          <h2 id="innovation-title">让思考拥有延续的空间</h2>
          <p>知识会不断变化，好的工具应该让每一次探索都成为下一次的起点</p>
        </div>
        <div className="innovation-list">
          <article><span>01</span><p><strong>离开之后，思考仍然留在原处</strong><small>问题、进度与阶段成果自然保留，回来时无需重新开始</small></p></article>
          <article><span>02</span><p><strong>重要的内容在需要时重新出现</strong><small>从大量资料中找到真正相关的部分，让每一次阅读都可能产生新的价值</small></p></article>
          <article><span>03</span><p><strong>新的理解始终连接着它的来处</strong><small>观点与当时使用的内容保持关联，让过去与现在都能被准确理解</small></p></article>
        </div>
      </section>
    </main>
  );
}
