import { useState } from "react";
import { setApiKey } from "../api/client";

interface Props {
  onSaved: () => void;
}

export default function ApiKeyGate({ onSaved }: Props) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Введите API-ключ.");
      return;
    }
    setApiKey(trimmed);
    onSaved();
  };

  return (
    <div className="api-key-gate">
      <form className="api-key-card" onSubmit={submit}>
        <h2>Доступ к API</h2>
        <p>
          Вставьте API-ключ, полученный через CLI (главное меню → «API-ключи»).
          Ключ хранится только в этом браузере.
        </p>
        <input
          type="password"
          value={value}
          placeholder="aic_..."
          autoFocus
          onChange={(event) => {
            setValue(event.target.value);
            setError(null);
          }}
        />
        {error && <div className="api-key-error">{error}</div>}
        <button type="submit">Войти</button>
      </form>
    </div>
  );
}
