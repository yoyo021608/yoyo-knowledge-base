import { useCallback, useState } from "react";

const STORAGE_KEY = "yoyo.access-token";

/** 平台层负责保存登录凭证，views 和 core 不直接访问 localStorage。 */
export function useAuthSession() {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    window.localStorage.getItem(STORAGE_KEY),
  );

  const authenticate = useCallback((token: string) => {
    window.localStorage.setItem(STORAGE_KEY, token);
    setAccessToken(token);
  }, []);

  const clear = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setAccessToken(null);
  }, []);

  return { accessToken, authenticate, clear };
}
