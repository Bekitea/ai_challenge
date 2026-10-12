export interface AvailableModel {
  provider: string;
  model_id: string;
  display_name: string;
}

export interface ChatPreview {
  agent_id: number;
  name: string;
  last_message_timestamp: string | null;
  message_count: number;
  last_message_preview: string | null;
}

export interface Chat {
  agent_id: number;
  name: string;
  strategy_type: string;
  current_phase: string;
  system_prompt: string | null;
  task_profile_name: string | null;
}

export interface Settings {
  model_id: string | null;
  provider: string | null;
  top_k: number | null;
  top_p: number | null;
  temperature: number | null;
  max_tokens: number | null;
  reasoning_effort: string | null;
  context_window_size: number | null;
  reranker_enabled: boolean;
}

export interface HistoryMessage {
  role: string;
  content: string;
  reasoning: string | null;
  has_tool_calls: boolean;
  timestamp: string | null;
}

export interface RagSource {
  document_name: string;
  chunk_id: number;
  chunk_index: number;
  text: string;
  relevance: number | null;
}

export interface MessageResponse {
  content: string;
  reasoning: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  context_window_size: number | null;
  rag_sources: RagSource[] | null;
}

export interface PhaseChangeResult {
  success: boolean;
  message: string;
  current_phase: string;
}

export interface ActionResult {
  success: boolean;
  message: string | null;
}

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  listModels: () => request<AvailableModel[]>("/models"),
  listChats: () => request<ChatPreview[]>("/chats"),
  getChat: (id: number) => request<Chat>(`/chats/${id}`),
  createChat: (payload: {
    name: string;
    system_prompt?: string | null;
    settings: Settings;
  }) =>
    request<Chat>("/chats", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getHistory: (id: number) =>
    request<HistoryMessage[]>(`/chats/${id}/history`),
  sendMessage: (id: number, message: string) =>
    request<MessageResponse>(`/chats/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  getSettings: (id: number) => request<Settings>(`/chats/${id}/settings`),
  updateSettings: (id: number, settings: Settings) =>
    request<Settings>(`/chats/${id}/settings`, {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  setRerank: (id: number, enabled: boolean) =>
    request<{ enabled: boolean }>(`/chats/${id}/rerank`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  changePhase: (id: number, command: string) =>
    request<PhaseChangeResult>(`/chats/${id}/phase`, {
      method: "POST",
      body: JSON.stringify({ command }),
    }),
};
