type UnauthorizedListener = () => void;

const unauthorizedListeners = new Set<UnauthorizedListener>();

/** core 只上报身份已经失效，不读取浏览器存储，也不决定页面跳转。 */
export function reportUnauthorized(): void {
  for (const listener of unauthorizedListeners) listener();
}

/** 平台层订阅身份失效事件，返回清理函数以避免重复监听。 */
export function subscribeUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
}
