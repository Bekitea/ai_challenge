import { useCallback, useEffect, useState } from "react";
import {
  api,
  type AvailableModel,
  type Chat,
  type ChatPreview,
  type HistoryMessage,
  type Settings,
} from "./api/client";
import ChatList from "./components/ChatList";
import ChatView from "./components/ChatView";
import NewChatDialog from "./components/NewChatDialog";
import PhaseBar from "./components/PhaseBar";
import SettingsPanel from "./components/SettingsPanel";

export default function App() {
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [chats, setChats] = useState<ChatPreview[]>([]);
  const [current, setCurrent] = useState<Chat | null>(null);
  const [history, setHistory] = useState<HistoryMessage[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadChats = useCallback(async () => {
    setChats(await api.listChats());
  }, []);

  useEffect(() => {
    api
      .listModels()
      .then(setModels)
      .catch((err: Error) => setError(err.message));
    loadChats().catch((err: Error) => setError(err.message));
  }, [loadChats]);

  const selectChat = useCallback(async (id: number) => {
    try {
      setError(null);
      const [chat, hist, cfg] = await Promise.all([
        api.getChat(id),
        api.getHistory(id),
        api.getSettings(id),
      ]);
      setCurrent(chat);
      setHistory(hist);
      setSettings(cfg);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const handleCreate = async (
    name: string,
    chatSettings: Settings,
    systemPrompt: string,
  ) => {
    try {
      setBusy(true);
      setError(null);
      const chat = await api.createChat({
        name,
        system_prompt: systemPrompt || null,
        settings: chatSettings,
      });
      setShowNew(false);
      await loadChats();
      await selectChat(chat.agent_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleSend = async (text: string) => {
    if (!current) {
      return;
    }
    try {
      setBusy(true);
      setError(null);
      const response = await api.sendMessage(current.agent_id, text);
      const stamp = new Date().toISOString();
      setHistory((prev) => [
        ...prev,
        {
          role: "user",
          content: text,
          reasoning: null,
          has_tool_calls: false,
          timestamp: stamp,
        },
        {
          role: "assistant",
          content: response.content,
          reasoning: response.reasoning,
          has_tool_calls: false,
          timestamp: stamp,
        },
      ]);
      await loadChats();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleSaveSettings = async (next: Settings) => {
    if (!current) {
      return;
    }
    try {
      setBusy(true);
      setError(null);
      const saved = await api.updateSettings(current.agent_id, next);
      setSettings(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleToggleRerank = async (enabled: boolean) => {
    if (!current) {
      return;
    }
    try {
      setError(null);
      const result = await api.setRerank(current.agent_id, enabled);
      setSettings((prev) =>
        prev ? { ...prev, reranker_enabled: result.enabled } : prev,
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handlePhase = async (command: string) => {
    if (!current) {
      return;
    }
    try {
      setError(null);
      const result = await api.changePhase(current.agent_id, command);
      setCurrent((prev) =>
        prev ? { ...prev, current_phase: result.current_phase } : prev,
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Chat</h1>
      </header>

      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="app-body">
        <ChatList
          chats={chats}
          currentId={current?.agent_id ?? null}
          onSelect={selectChat}
          onNew={() => setShowNew(true)}
        />

        <main className="main">
          {current ? (
            <>
              <PhaseBar
                currentPhase={current.current_phase}
                onChange={handlePhase}
              />
              <ChatView
                chat={current}
                history={history}
                busy={busy}
                onSend={handleSend}
              />
              {settings && (
                <SettingsPanel
                  settings={settings}
                  models={models}
                  busy={busy}
                  onSave={handleSaveSettings}
                  onToggleRerank={handleToggleRerank}
                />
              )}
            </>
          ) : (
            <div className="placeholder">
              <p>Выберите чат или создайте новый.</p>
            </div>
          )}
        </main>
      </div>

      {showNew && (
        <NewChatDialog
          models={models}
          busy={busy}
          onCancel={() => setShowNew(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  );
}
