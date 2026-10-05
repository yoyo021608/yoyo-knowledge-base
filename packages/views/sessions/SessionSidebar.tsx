import { type FormEvent, useEffect, useState } from "react";

import type { ConversationSession } from "@yoyo/core";
import { Button, Card } from "@yoyo/ui";

interface Props {
  sessions: ConversationSession[];
  selectedId: string | null;
  pending: boolean;
  onSelect: (sessionId: string) => void;
  onCreate: (name: string) => Promise<void>;
  onRename: (name: string) => Promise<void>;
  onDelete: () => Promise<void>;
}

/** 会话自身的创建、选择、改名和删除入口，不处理消息或 Agent Run。 */
export function SessionSidebar({
  sessions,
  selectedId,
  pending,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: Props) {
  const selected = sessions.find((session) => session.id === selectedId) ?? null;
  const [newName, setNewName] = useState("新会话");
  const [renameValue, setRenameValue] = useState("");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    setRenameValue(selected?.name ?? "");
    setConfirmingDelete(false);
  }, [selected?.id, selected?.name]);

  async function create(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await onCreate(newName);
    setNewName("新会话");
  }

  async function rename(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await onRename(renameValue);
  }

  return (
    <aside className="session-sidebar">
      <Card>
        <h2>会话</h2>
        <form className="session-create" onSubmit={(event) => void create(event)}>
          <input
            required
            maxLength={120}
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            aria-label="新会话名称"
          />
          <Button type="submit" disabled={pending}>创建</Button>
        </form>
        <ul className="session-list">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                className={session.id === selectedId ? "selected" : ""}
                onClick={() => onSelect(session.id)}
              >
                <strong>{session.name}</strong>
                <small>
                  {session.status === "deleting" ? "删除中" : session.activeRunId ? "运行中" : "可提问"}
                </small>
              </button>
            </li>
          ))}
        </ul>
      </Card>

      {selected && (
        <Card>
          <h2>当前会话</h2>
          <form className="session-create" onSubmit={(event) => void rename(event)}>
            <input
              required
              maxLength={120}
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              aria-label="会话名称"
            />
            <Button type="submit" disabled={pending || selected.status === "deleting"}>改名</Button>
          </form>
          {confirmingDelete ? (
            <div className="delete-confirmation" role="alert">
              <p>删除后会同时清理该会话的消息、结果和运行记录，确认继续吗？</p>
              <div className="account-actions">
                <Button disabled={pending} onClick={() => void onDelete()}>确认删除</Button>
                <Button disabled={pending} onClick={() => setConfirmingDelete(false)}>取消</Button>
              </div>
            </div>
          ) : (
            <Button disabled={pending} onClick={() => setConfirmingDelete(true)}>删除会话</Button>
          )}
        </Card>
      )}
    </aside>
  );
}
