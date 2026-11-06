/**
 * The one place the SPA talks HTTP. JSON in, JSON out; non-2xx responses carry
 * `{"detail": "...", "errors"?: [...]}` (contract) and become ApiError.
 */
import { createSseParser } from "@/lib/sse";
import type {
  ChatEvent,
  ChatExample,
  Graph,
  Health,
  SampleRows,
  SchemaDetail,
  SchemaName,
  SchemaSummary,
  Tool,
  ToolDetail,
  ToolSpec,
  ToolTestResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly errors: string[];
  constructor(status: number, message: string, errors: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }
}

function detailMessage(status: number, body: unknown): { message: string; errors: string[] } {
  const b = (body && typeof body === "object" ? body : {}) as Record<string, unknown>;
  const errors = Array.isArray(b.errors) ? b.errors.map(String) : [];
  let message = "";
  if (typeof b.detail === "string") message = b.detail;
  else if (Array.isArray(b.detail)) {
    // FastAPI's own 422 shape: [{loc, msg}]
    const msgs = b.detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)));
    message = msgs[0] ?? "";
    if (!errors.length) errors.push(...msgs);
  }
  if (!message) {
    if (status === 0) message = "Could not reach the API — is the app container running on :8080?";
    else if (status === 404) message = "Not found.";
    else if (status === 409) message = "A tool with this name already exists.";
    else if (status >= 500) message = `The server hit an error (${status}).`;
    else message = `Request failed (${status}).`;
  }
  return { message, errors };
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...rest,
      headers: {
        Accept: "application/json",
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    const { message } = detailMessage(0, null);
    throw new ApiError(0, message);
  }
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { detail: text.slice(0, 300) };
    }
  }
  if (!res.ok) {
    const { message, errors } = detailMessage(res.status, body);
    throw new ApiError(res.status, message, errors);
  }
  return body as T;
}

const enc = encodeURIComponent;

export const endpoints = {
  health: () => api<Health>("/health"),
  graph: () => api<Graph>("/graph"),
  chatExamples: () => api<ChatExample[]>("/chat/examples"),
  chatReset: (conversation_id: string) => api<{ ok: boolean }>("/chat/reset", { method: "POST", json: { conversation_id } }),

  tools: (params: { agent?: string; q?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.agent) qs.set("agent", params.agent);
    if (params.q) qs.set("q", params.q);
    const s = qs.toString();
    return api<Tool[]>(`/tools${s ? `?${s}` : ""}`);
  },
  tool: (name: string) => api<ToolDetail>(`/tools/${enc(name)}`),
  createTool: (spec: ToolSpec) => api<Tool>("/tools", { method: "POST", json: spec }),
  updateTool: (name: string, spec: ToolSpec) => api<Tool>(`/tools/${enc(name)}`, { method: "PUT", json: spec }),
  setToolEnabled: (name: string, enabled: boolean) => api<Tool>(`/tools/${enc(name)}/enabled`, { method: "PATCH", json: { enabled } }),
  deleteTool: (name: string) => api<{ ok: boolean }>(`/tools/${enc(name)}`, { method: "DELETE" }),
  testTool: (spec: ToolSpec & { args?: Record<string, unknown> }) => api<ToolTestResponse>("/tools/test", { method: "POST", json: spec }),

  schemas: () => api<{ schemas: SchemaSummary[] }>("/schema"),
  schema: (name: SchemaName) => api<SchemaDetail>(`/schema/${enc(name)}`),
  sample: (schema: SchemaName, table: string, limit = 5) => api<SampleRows>(`/schema/${enc(schema)}/${enc(table)}/sample?limit=${limit}`),
};

/**
 * POST /api/chat and stream its SSE events. Resolves when the stream ends.
 * Network / HTTP failures are surfaced as a synthetic `error` event so the UI
 * has a single path for "something went wrong".
 */
export async function streamChat(
  body: { conversation_id: string; message: string },
  onEvent: (ev: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal?.aborted) return;
    onEvent({ type: "error", message: detailMessage(0, null).message, ts: Date.now() });
    void err;
    return;
  }
  if (!res.ok || !res.body) {
    let parsed: unknown = null;
    try {
      parsed = await res.json();
    } catch {
      /* not JSON */
    }
    onEvent({ type: "error", message: detailMessage(res.status, parsed).message, ts: Date.now() });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser<ChatEvent>({
    decode: (data) => {
      const v = JSON.parse(data) as ChatEvent;
      return v && typeof v === "object" && typeof v.type === "string" ? v : undefined;
    },
  });
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      for (const ev of parser.push(decoder.decode(value, { stream: true }))) onEvent(ev);
    }
    for (const ev of parser.push(decoder.decode())) onEvent(ev);
    for (const ev of parser.flush()) onEvent(ev);
  } catch (err) {
    if (signal?.aborted) return;
    onEvent({ type: "error", message: err instanceof Error ? `Stream interrupted: ${err.message}` : "Stream interrupted.", ts: Date.now() });
  } finally {
    reader.releaseLock();
  }
}
