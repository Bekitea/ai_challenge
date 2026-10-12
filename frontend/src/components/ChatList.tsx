import type { ChatPreview } from "../api/client";

interface Props {
  chats: ChatPreview[];
  currentId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
}

export default function ChatList({ chats, currentId, onSelect, onNew }: Props) {
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNew}>
        + Новый чат
      </button>
      <div className="chat-list">
        {chats.length === 0 && <p className="muted">Чатов пока нет</p>}
        {chats.map((chat) => (
          <button
            key={chat.agent_id}
            className={
              "chat-item" + (chat.agent_id === currentId ? " active" : "")
            }
            onClick={() => onSelect(chat.agent_id)}
          >
            <span className="chat-name">{chat.name}</span>
            <span className="chat-preview">
              {chat.last_message_preview ?? "(нет сообщений)"}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
