import { buildApiUrl } from "./client";

export interface HealthResponse {
  status: string;
}

/**
 * 读取后端健康状态。
 * 这里只使用 fetch，不碰 window、document 等浏览器专有对象；
 * baseUrl 由调用方注入，core 不读取环境变量。
 */
export async function fetchHealth(baseUrl: string): Promise<HealthResponse> {
  const response = await fetch(buildApiUrl(baseUrl, "/health"));

  if (!response.ok) {
    throw new Error(`健康检查失败：HTTP ${response.status}`);
  }

  return (await response.json()) as HealthResponse;
}
