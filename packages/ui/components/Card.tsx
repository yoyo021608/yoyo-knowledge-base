import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
}

/** 通用卡片容器：只负责布局和外观，不知道页面在展示什么业务。 */
export function Card({ children }: CardProps) {
  return <section className="ui-card">{children}</section>;
}
