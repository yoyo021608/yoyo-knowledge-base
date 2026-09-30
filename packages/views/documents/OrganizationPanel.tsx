import { type FormEvent, useState } from "react";

import {
  createTag,
  createTopic,
  deleteTag,
  deleteTopic,
  renameTag,
  updateTopic,
  type Tag,
  type Topic,
} from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  apiBaseUrl: string;
  accessToken: string;
  topics: Topic[];
  tags: Tag[];
  onChanged: () => Promise<void>;
  onMessage: (message: string) => void;
}

/** 专题和标签的独立管理区；删除只解除组织关系，不删除文档。 */
export function OrganizationPanel({ apiBaseUrl, accessToken, topics, tags, onChanged, onMessage }: Props) {
  const [topicName, setTopicName] = useState("");
  const [topicDescription, setTopicDescription] = useState("");
  const [tagName, setTagName] = useState("");

  async function addTopic(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await createTopic(apiBaseUrl, accessToken, topicName, topicDescription);
      setTopicName("");
      setTopicDescription("");
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "创建专题失败");
    }
  }

  async function addTag(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    try {
      await createTag(apiBaseUrl, accessToken, tagName);
      setTagName("");
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "创建标签失败");
    }
  }

  async function editTopic(topic: Topic): Promise<void> {
    const name = window.prompt("专题名称", topic.name);
    if (!name) return;
    const description = window.prompt("专题说明", topic.description);
    if (description === null) return;
    try {
      await updateTopic(apiBaseUrl, accessToken, topic.id, name, description);
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "修改专题失败");
    }
  }

  async function editTag(tag: Tag): Promise<void> {
    const name = window.prompt("标签名称", tag.name);
    if (!name) return;
    try {
      await renameTag(apiBaseUrl, accessToken, tag.id, name);
      await onChanged();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : "修改标签失败");
    }
  }

  return (
    <Card>
      <h2>知识组织</h2>
      <form className="inline-form" onSubmit={(event) => void addTopic(event)}>
        <input required placeholder="专题名称" value={topicName} onChange={(event) => setTopicName(event.target.value)} />
        <input placeholder="专题说明" value={topicDescription} onChange={(event) => setTopicDescription(event.target.value)} />
        <Button type="submit">新建专题</Button>
      </form>
      <ul className="compact-list">{topics.map((topic) => <li key={topic.id}><span><strong>{topic.name}</strong> {topic.description}</span><span><button onClick={() => void editTopic(topic)}>修改</button><button onClick={() => void deleteTopic(apiBaseUrl, accessToken, topic.id).then(onChanged).catch((error: unknown) => onMessage(error instanceof Error ? error.message : "删除失败"))}>删除</button></span></li>)}</ul>
      <form className="inline-form" onSubmit={(event) => void addTag(event)}>
        <input required placeholder="标签名称" value={tagName} onChange={(event) => setTagName(event.target.value)} />
        <Button type="submit">新建标签</Button>
      </form>
      <ul className="tag-list">{tags.map((tag) => <li key={tag.id}>{tag.name}<button aria-label={`修改 ${tag.name}`} onClick={() => void editTag(tag)}>✎</button><button aria-label={`删除 ${tag.name}`} onClick={() => void deleteTag(apiBaseUrl, accessToken, tag.id).then(onChanged).catch((error: unknown) => onMessage(error instanceof Error ? error.message : "删除失败"))}>×</button></li>)}</ul>
    </Card>
  );
}
