import type { ComponentType, ReactNode } from "react";

/** 业务视图只描述“前往哪里”，具体路由实现由 apps/web 注入。 */
export interface ViewLinkProps {
  children: ReactNode;
  className?: string;
  to: string;
}

export type ViewLinkComponent = ComponentType<ViewLinkProps>;
