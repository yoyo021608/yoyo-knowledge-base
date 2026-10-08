import {
  ApiError,
  fetchCurrentUser,
  subscribeUnauthorized,
  type AuthSession,
  type UserProfile,
} from "@yoyo/core";
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "yoyo.access-token";
export type AuthStatus = "checking" | "authenticated" | "anonymous" | "unavailable";

function readStoredToken(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** 平台层负责保存登录凭证，views 和 core 不直接访问 localStorage。 */
export function useAuthSession(apiBaseUrl: string) {
  const [accessToken, setAccessToken] = useState<string | null>(readStoredToken);
  const [status, setStatus] = useState<AuthStatus>(() =>
    readStoredToken() ? "checking" : "anonymous",
  );
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileError, setProfileError] = useState("");
  const [notice, setNotice] = useState("");

  const authenticate = useCallback((session: AuthSession) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, session.accessToken);
    } catch {
      // 存储被浏览器禁用时仍允许当前页面维持登录状态。
    }
    setAccessToken(session.accessToken);
    setProfile(session.user);
    setStatus("authenticated");
    setProfileError("");
    setNotice("");
  }, []);

  const clear = useCallback(() => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // 清理存储失败不能阻止当前页面退出登录。
    }
    setAccessToken(null);
    setProfile(null);
    setStatus("anonymous");
    setProfileError("");
    setNotice("");
  }, []);

  useEffect(
    () => subscribeUnauthorized(() => {
      if (accessToken === null) return;
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // 浏览器存储异常不能阻止当前页面清除失效身份。
      }
      setAccessToken(null);
      setProfile(null);
      setStatus("anonymous");
      setProfileError("");
      setNotice("登录状态已失效，请重新登录");
    }),
    [accessToken],
  );

  const refreshProfile = useCallback(async (): Promise<void> => {
    if (accessToken === null) {
      setStatus("anonymous");
      return;
    }
    setStatus("checking");
    setProfileError("");
    try {
      setProfile(await fetchCurrentUser(apiBaseUrl, accessToken));
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return;
      setProfileError(error instanceof Error ? error.message : "暂时无法读取当前身份");
      setStatus("unavailable");
    }
  }, [accessToken, apiBaseUrl]);

  useEffect(() => {
    if (accessToken === null || profile !== null) return;
    // 页面刷新后用持久化令牌恢复当前身份；401 会走上面的统一失效流程。
    void refreshProfile();
  }, [accessToken, profile, refreshProfile]);

  return { accessToken, authenticate, clear, notice, profile, profileError, refreshProfile, status };
}
