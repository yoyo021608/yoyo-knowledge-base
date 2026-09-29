import { buildApiUrl } from "./client";

/** 后端返回的公开账户身份，任何密码字段都不能进入 core。 */
export interface UserProfile {
  id: string;
  email: string;
}

export interface AuthSession {
  accessToken: string;
  expiresAt: string;
  user: UserProfile;
}

export interface PasswordResetRequestResult {
  message: string;
  developmentResetToken: string | null;
}

interface LoginWireResponse {
  access_token: string;
  expires_at: string;
  user: UserProfile;
}

interface ResetWireResponse {
  message: string;
  development_reset_token: string | null;
}

interface ErrorWireResponse {
  detail?: string;
}

/** 携带 HTTP 状态码的请求错误，供视图选择用户提示。 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  baseUrl: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(buildApiUrl(baseUrl, path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = `请求失败：HTTP ${response.status}`;
    try {
      const body = (await response.json()) as ErrorWireResponse;
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // 网关返回非 JSON 内容时，保留上面根据状态码生成的提示。
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** 注册账户，但不隐式创建登录会话。 */
export function registerAccount(
  baseUrl: string,
  email: string,
  password: string,
): Promise<UserProfile> {
  return request(baseUrl, "/api/users/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

/** 校验登录信息并返回绑定持久化会话的访问令牌。 */
export async function loginAccount(
  baseUrl: string,
  email: string,
  password: string,
): Promise<AuthSession> {
  const result = await request<LoginWireResponse>(baseUrl, "/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return {
    accessToken: result.access_token,
    expiresAt: result.expires_at,
    user: result.user,
  };
}

/** 获取当前身份；具体资源权限仍由所属业务模块判断。 */
export function fetchCurrentUser(
  baseUrl: string,
  accessToken: string,
): Promise<UserProfile> {
  return request(baseUrl, "/api/users/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

/** 只撤销传入令牌代表的当前登录会话。 */
export function logoutAccount(baseUrl: string, accessToken: string): Promise<void> {
  return request(baseUrl, "/api/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

/** 修改密码；后端会撤销该用户已有的全部登录会话。 */
export function changeAccountPassword(
  baseUrl: string,
  accessToken: string,
  oldPassword: string,
  newPassword: string,
): Promise<void> {
  return request(baseUrl, "/api/users/change-password", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}

/** 申请密码重置，同时隐藏提交的邮箱是否存在。 */
export async function requestPasswordReset(
  baseUrl: string,
  email: string,
): Promise<PasswordResetRequestResult> {
  const result = await request<ResetWireResponse>(
    baseUrl,
    "/api/auth/password-reset/request",
    { method: "POST", body: JSON.stringify({ email }) },
  );
  return {
    message: result.message,
    developmentResetToken: result.development_reset_token,
  };
}

/** 消费一次性重置凭证并设置新密码。 */
export function confirmPasswordReset(
  baseUrl: string,
  token: string,
  newPassword: string,
): Promise<void> {
  return request(baseUrl, "/api/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}
