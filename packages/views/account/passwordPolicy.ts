/**
 * 前端用相同规则提前提示用户；最终安全校验仍由 users 后端模块负责。
 */
export const strongPasswordPattern =
  "(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9\\s])\\S{10,128}";

export const passwordRequirement =
  "10～128 位，包含大写英文字母、小写英文字母、数字和特殊字符，不能包含空格";
