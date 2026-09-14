import { useState } from "react";

import { buildApiUrl, fetchHealth } from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface HomeViewProps {
  apiBaseUrl: string;
}

/** 首页视图：把 core 的接口能力和 ui 的展示组件组合成页面；接口地址由平台层注入。 */
export function HomeView({ apiBaseUrl }: HomeViewProps) {
  const [status, setStatus] = useState("未检查");

  async function handleCheck(): Promise<void> {
    try {
      const result = await fetchHealth(apiBaseUrl);
      setStatus(result.status);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "检查失败");
    }
  }

  return (
    <main>
      <h1>yoyo-knowledge-base</h1>
      <Card>
        <p>后端地址：{buildApiUrl(apiBaseUrl, "/health")}</p>
        <p>后端状态：{status}</p>
        <Button onClick={() => void handleCheck()}>检查后端</Button>
      </Card>
    </main>
  );
}
