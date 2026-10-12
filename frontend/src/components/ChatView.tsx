import { useState } from "react";
import type { Chat, HistoryMessage } from "../api/client";

interface Props {
  chat: Chat;
  history: HistoryMessage[];
  busy: boolean;
  onSend: (text: string) => void;
}

export default function ChatView({ chat, history, busy, onSend }: Props) {
  const [input, setInput] = useState("");

  const send = () => {
    const text = input.trim();
    if (!text || busy) {
      return;
    }
    onSend(text);
    setInput("");
  };

  const visible = history.filter(
    (message) => message.role !== "system" && !message.has_tool_calls,
  );

  return (
    <section className="chat-view">
      <header className="chat-header">
        <h2>{chat.name}</h2>
        <span className="phase">Фаза: {chat.current_phase}</span>
      </header>

      <div className="messages">
        {visible.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.reasoning && (
              <div className="reasoning">{message.reasoning}</div>
            )}
            <div className="bubble">
              {message.content || "(пустой ответ)"}
            </div>
          </div>
        ))}
        {visible.length === 0 && (
          <p className="muted">История пуста. Напишите сообщение.</p>
        )}
      </div>

      <div className="composer">
        <textarea
          rows={2}
          value={input}
          placeholder="Введите сообщение..."
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          disabled={busy}
        />
        <button className="primary" onClick={send} disabled={busy}>
          {busy ? "..." : "Отправить"}
        </button>
      </div>
    </section>
  );
}
