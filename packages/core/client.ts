/** 后端接口的统一前缀；接口版本变化时只改这里。 */
export const API_PATH_PREFIX = "";

/**
 * 把调用方注入的 baseUrl 和接口路径拼成完整地址。
 * core 不读取环境变量，baseUrl 一律由上层传入。
 */
export function buildApiUrl(baseUrl: string, path: string): string {
  const normalizedBase = baseUrl.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${API_PATH_PREFIX}${normalizedPath}`;
}
