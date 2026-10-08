import type { ViewLinkProps } from "@yoyo/views";
import { Link } from "react-router-dom";

/** 将 React Router 限制在应用装配层，业务视图不感知具体路由库。 */
export function RouteLink(props: ViewLinkProps) {
  return <Link {...props} />;
}
