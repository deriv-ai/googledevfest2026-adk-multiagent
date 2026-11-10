import type { ChatEvent } from "@/api/types";
import { newId } from "./utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: number;
  /** Assistant only: every SSE event of this turn, so its route can be replayed. */
  events?: ChatEvent[];
  status?: "streaming" | "done" | "error";
  error?: string | null;
  elapsedMs?: number | null;
}

export interface Transcript {
  conversationId: string;
  messages: ChatMessage[];
}

const KEY = "nimbus-chat-v1";

export function newTranscript(): Transcript {
  return { conversationId: newId(), messages: [] };
}

export function loadTranscript(): Transcript {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return newTranscript();
    const t = JSON.parse(raw) as Transcript;
    if (!t || typeof t.conversationId !== "string" || !Array.isArray(t.messages)) return newTranscript();
    // A turn that was streaming when the page unloaded can't resume.
    t.messages = t.messages.map((m) => (m.status === "streaming" ? { ...m, status: "error", error: "Interrupted — the page was reloaded while this answer was streaming." } : m));
    return t;
  } catch {
    return newTranscript();
  }
}

export function saveTranscript(t: Transcript): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(t));
  } catch {
    /* quota or private mode: transcript just won't survive a reload */
  }
}
