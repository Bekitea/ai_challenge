import { useEffect, useState } from "react";
import type { AvailableModel, Settings } from "../api/client";

const REASONING_EFFORTS = ["none", "low", "medium", "high"];

interface Props {
  settings: Settings;
  models: AvailableModel[];
  busy: boolean;
  onSave: (settings: Settings) => void;
  onToggleRerank: (enabled: boolean) => void;
}

export default function SettingsPanel({
  settings,
  models,
  busy,
  onSave,
  onToggleRerank,
}: Props) {
  const [draft, setDraft] = useState<Settings>(settings);

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  const modelKey = `${draft.provider ?? ""}|${draft.model_id ?? ""}`;

  return (
    <section className="panel">
      <h3>Настройки</h3>

      <label>
        Модель
        <select
          value={modelKey}
          onChange={(event) => {
            const [provider, ...rest] = event.target.value.split("|");
            setDraft({ ...draft, provider, model_id: rest.join("|") });
          }}
        >
          {draft.model_id && !models.some((m) => `${m.provider}|${m.model_id}` === modelKey) && (
            <option value={modelKey}>
              {draft.provider}: {draft.model_id}
            </option>
          )}
          {models.map((model) => (
            <option
              key={`${model.provider}-${model.model_id}`}
              value={`${model.provider}|${model.model_id}`}
            >
              [{model.provider}] {model.display_name || model.model_id}
            </option>
          ))}
        </select>
      </label>

      <label>
        Температура
        <input
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={draft.temperature ?? ""}
          onChange={(event) =>
            setDraft({
              ...draft,
              temperature: event.target.value === "" ? null : Number(event.target.value),
            })
          }
        />
      </label>

      <label>
        Размер контекстного окна
        <input
          type="number"
          value={draft.context_window_size ?? ""}
          onChange={(event) =>
            setDraft({
              ...draft,
              context_window_size:
                event.target.value === "" ? null : Number(event.target.value),
            })
          }
        />
      </label>

      <label>
        Reasoning effort
        <select
          value={draft.reasoning_effort ?? "none"}
          onChange={(event) =>
            setDraft({ ...draft, reasoning_effort: event.target.value })
          }
        >
          {REASONING_EFFORTS.map((effort) => (
            <option key={effort} value={effort}>
              {effort}
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={draft.reranker_enabled}
          onChange={(event) => onToggleRerank(event.target.checked)}
        />
        Реранкинг RAG
      </label>

      <button className="primary" onClick={() => onSave(draft)} disabled={busy}>
        Сохранить
      </button>
    </section>
  );
}
