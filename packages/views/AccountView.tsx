import { AuthenticatedAccountView } from "./account/AuthenticatedAccountView";
import type { UserProfile } from "@yoyo/core";

interface AccountViewProps {
  apiBaseUrl: string;
  accessToken: string;
  onSignedOut: () => void;
  onRetryProfile: () => void;
  profile: UserProfile | null;
  profileError: string;
}

/** 账户页只承载登录后的身份与安全设置，登录入口由独立 LoginView 负责。 */
export function AccountView({
  apiBaseUrl,
  accessToken,
  onSignedOut,
  onRetryProfile,
  profile,
  profileError,
}: AccountViewProps) {
  return (
    <AuthenticatedAccountView
      apiBaseUrl={apiBaseUrl}
      accessToken={accessToken}
      onSignedOut={onSignedOut}
      onRetryProfile={onRetryProfile}
      profile={profile}
      profileError={profileError}
    />
  );
}
