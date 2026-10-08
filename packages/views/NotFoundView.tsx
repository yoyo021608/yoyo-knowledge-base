import type { ViewLinkComponent } from "./navigation";

interface NotFoundViewProps {
  LinkComponent: ViewLinkComponent;
}

/** 未知地址只提供清晰的返回路径，不猜测用户原本想访问的业务资源。 */
export function NotFoundView({ LinkComponent: Link }: NotFoundViewProps) {
  return (
    <main className="not-found-shell">
      <section>
        <p className="page-eyebrow">A PATH YET TO BE FOUND</p>
        <span className="not-found-code">404</span>
        <h1>这里还没有留下知识的足迹</h1>
        <p>回到熟悉的入口，让探索从清晰的位置重新开始</p>
        <div className="project-actions">
          <Link className="project-primary" to="/">返回首页 <span aria-hidden="true">→</span></Link>
          <Link className="project-secondary" to="/workspace">进入知识工作台</Link>
        </div>
      </section>
    </main>
  );
}
