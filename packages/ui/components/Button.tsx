import type { ReactNode } from "react";

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
}

/** 通用按钮：只负责展示和点击回调，不包含任何业务规则。 */
export function Button({ children, onClick, type = "button", disabled = false }: ButtonProps) {
  return (
    <button className="ui-button" type={type} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}
