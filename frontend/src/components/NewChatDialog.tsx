import { useState } from "react";
import type { AvailableModel, Settings } from "../api/client";

interface Props {
  models: AvailableModel[];
  busy: boolean;
  onCancel: () => void;
  onCreate: (name: string, settings: Settings, systemPrompt: string) => void;
}

function defaultSettings(model: AvailableModel | undefined): Settings {
  return {
    model_id: model?.model_id ?? null,
    provider: model?.provider ?? null,
    top_k: null,
    top_p: null,
    temperature: null,
    max_tokens: null,
    reasoning_effort: "none",
    context_window_size: 200000,
    reranker_enabled: true,
  };
}

export default function NewChatDialog({
  models,
  busy,
  onCancel,
  onCreate,
}: Props) {
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [modelIndex, setModelIndex] = useState(0);

  const create = () => {
    onCreate(name, defaultSettings(models[modelIndex]), systemPrompt);
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>Новый чат</h2>
        {models.length === 0 ? (
          <p className="error">
            Нет доступных моделей. Проверьте, что Ollama запущена.
          </p>
        ) : (
          <>
            <label>
              Название
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Чат N"
              />
            </label>
            <label>
              Модель
              <select
                value={modelIndex}
                onChange={(event) => setModelIndex(Number(event.target.value))}
              >
                {models.map((model, index) => (
                  <option key={`${model.provider}-${model.model_id}`} value={index}>
                    [{model.provider}] {model.display_name || model.model_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Системный промпт (опционально)
              <textarea
                rows={3}
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
              />
            </label>
          </>
        )}
        <div className="modal-actions">
          <button onClick={onCancel} disabled={busy}>
            Отмена
          </button>
          <button
            className="primary"
            onClick={create}
            disabled={busy || models.length === 0}
          >
            Создать
          </button>
        </div>
      </div>
    </div>
  );
}
