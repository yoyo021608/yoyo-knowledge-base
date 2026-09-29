import { AccountAccessView } from "./account/AccountAccessView";
import { AuthenticatedAccountView } from "./account/AuthenticatedAccountView";

interface AccountViewProps {
  apiBaseUrl: string;
  accessToken: string | null;
  onAuthenticated: (accessToken: string) => void;
  onSignedOut: () => void;
}

/** 只根据登录状态选择账户视图，不在这里实现具体业务流程。 */
export function AccountView({
  apiBaseUrl,
  accessToken,
  onAuthenticated,
  onSignedOut,
}: AccountViewProps) {
  if (accessToken === null) {
    return (
      <AccountAccessView
        apiBaseUrl={apiBaseUrl}
        onAuthenticated={onAuthenticated}
      />
    );
  }
  return (
    <AuthenticatedAccountView
      apiBaseUrl={apiBaseUrl}
      accessToken={accessToken}
      onSignedOut={onSignedOut}
    />
  );
}
