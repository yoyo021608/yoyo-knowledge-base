import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";

interface NavigationEntry {
  description: string;
  icon: string;
  label: string;
  shortcut: string;
  to: string;
}

interface AppNavigationProps {
  collapsed: boolean;
  isAuthenticated: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

const primaryNavigationEntries: NavigationEntry[] = [
  { label: "首页", icon: "⌂", description: "了解项目定位和核心能力", shortcut: "H", to: "/" },
  { label: "工作台", icon: "◇", description: "进入知识与研究工作区", shortcut: "W", to: "/workspace" },
  { label: "知识库", icon: "▤", description: "收录、整理、检索和追溯资料", shortcut: "D", to: "/documents" },
  { label: "知识问答", icon: "✦", description: "创建可恢复、带引用的研究会话", shortcut: "A", to: "/sessions" },
];

/** 应用导航只处理路由入口和全局命令，不读取任何业务模块数据。 */
export function AppNavigation({
  collapsed,
  isAuthenticated,
  onCollapsedChange,
}: AppNavigationProps) {
  const [commandOpen, setCommandOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchInput = useRef<HTMLInputElement>(null);
  const commandButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent): void {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((open) => {
          if (open) window.requestAnimationFrame(() => commandButton.current?.focus());
          return !open;
        });
      } else if (event.key === "Escape") {
        setCommandOpen(false);
        window.requestAnimationFrame(() => commandButton.current?.focus());
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  useEffect(() => {
    if (commandOpen) {
      searchInput.current?.focus();
    } else {
      setQuery("");
    }
  }, [commandOpen]);

  useEffect(() => {
    if (!commandOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [commandOpen]);

  function closeCommand(): void {
    setCommandOpen(false);
    window.requestAnimationFrame(() => commandButton.current?.focus());
  }

  const identityEntry: NavigationEntry = isAuthenticated
    ? { label: "账户", icon: "◎", description: "管理账户与登录安全", shortcut: "U", to: "/account" }
    : { label: "登录", icon: "◎", description: "登录、注册或找回密码", shortcut: "L", to: "/login" };
  const navigationEntries = [...primaryNavigationEntries, identityEntry];

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleEntries = navigationEntries.filter((entry) =>
    `${entry.label} ${entry.description}`.toLocaleLowerCase().includes(normalizedQuery),
  );

  return (
    <>
      <aside className={`app-header${collapsed ? " is-collapsed" : ""}`}>
        <div className="app-header-inner">
          <button
            aria-label={collapsed ? "展开工作区导航" : "收起工作区导航"}
            className="sidebar-toggle"
            onClick={() => onCollapsedChange(!collapsed)}
            title={collapsed ? "展开导航" : "收起导航"}
            type="button"
          >
            <span aria-hidden="true">{collapsed ? "›" : "‹"}</span>
          </button>
          <Link className="app-brand" to="/" aria-label="个人知识空间首页">
            <span className="app-brand-mark" aria-hidden="true">知</span>
            <span className="app-brand-copy">
              <strong>个人知识空间</strong>
              <small>让知识连接 让思考生长</small>
            </span>
          </Link>
          <button
            aria-expanded={commandOpen}
            aria-haspopup="dialog"
            className="command-trigger"
            onClick={() => setCommandOpen(true)}
            ref={commandButton}
            type="button"
            title="搜索页面与功能"
          >
            <span aria-hidden="true">⌕</span>
            <span>搜索与跳转</span>
            <kbd>Ctrl K</kbd>
          </button>
          <p className="app-nav-label">工作区</p>
          <nav className="app-nav" aria-label="主导航">
            {navigationEntries.map((entry) => (
              <NavLink
                className={({ isActive }) => isActive ? "active" : ""}
                end={entry.to === "/"}
                key={entry.to}
                title={entry.label}
                to={entry.to}
              >
                <span className="app-nav-icon" aria-hidden="true">{entry.icon}</span>
                <span>{entry.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="app-sidebar-note">
            <span aria-hidden="true">✦</span>
            <p><strong>让知识连接，让思考生长</strong><small>清晰来处 · 自然延续</small></p>
          </div>
        </div>
      </aside>

      {commandOpen && (
        <div
          className="command-backdrop"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) closeCommand();
          }}
        >
          <section
            aria-label="快速前往"
            aria-modal="true"
            className="command-dialog"
            role="dialog"
          >
            <label className="command-search">
              <span aria-hidden="true">⌕</span>
              <input
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索页面或功能"
                ref={searchInput}
                value={query}
              />
              <kbd>ESC</kbd>
            </label>
            <div className="command-results" role="list">
              <p>页面</p>
              {visibleEntries.map((entry) => (
                <Link key={entry.to} onClick={closeCommand} role="listitem" to={entry.to}>
                  <span>
                    <strong>{entry.label}</strong>
                    <small>{entry.description}</small>
                  </span>
                  <kbd>{entry.shortcut}</kbd>
                </Link>
              ))}
              {visibleEntries.length === 0 && (
                <p className="command-empty">没有匹配的页面</p>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  );
}
