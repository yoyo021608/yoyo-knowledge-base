import { type FormEvent, useState } from "react";

import { searchDocuments, type SearchHit, type SearchMode } from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  apiBaseUrl: string;
  accessToken: string;
  onSelect: (documentId: string) => void;
  onMessage: (message: string) => void;
}

/** 展示四种查询模式返回的候选片段，不在前端伪造答案。 */
export function DocumentSearchPanel({ apiBaseUrl, accessToken, onSelect, onMessage }: Props) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [hits, setHits] = useState<SearchHit[]>([]);

  async function search(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      setHits(await searchDocuments(apiBaseUrl, accessToken, text, mode));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "检索失败");
    }
  }

  return (
    <Card>
      <h2>检索知识</h2>
      <form className="search-row" onSubmit={(event) => void search(event)}>
        <input required value={text} onChange={(event) => setText(event.target.value)} placeholder="输入要查找的知识" />
        <select value={mode} onChange={(event) => setMode(event.target.value as SearchMode)}>
          <option value="hybrid">混合检索</option>
          <option value="keyword">关键词</option>
          <option value="full_text">全文</option>
          <option value="vector">向量近似</option>
        </select>
        <Button type="submit">检索</Button>
      </form>
      <div className="search-results">
        {hits.map((hit) => (
          <button className="search-hit" key={hit.chunkId} onClick={() => onSelect(hit.documentId)}>
            <strong>{hit.title}</strong>
            <span>{hit.contentSnippet}</span>
            <small>相关度 {hit.score.toFixed(3)} · 版本 {hit.versionId.slice(0, 8)}</small>
          </button>
        ))}
      </div>
    </Card>
  );
}
