import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, MessageSquarePlus, RotateCcw, Square, Waypoints } from "lucide-react";
import { toast } from "sonner";
import { endpoints, streamChat } from "@/api/client";
import { useChatExamples, useGraph } from "@/api/hooks";
import type { ChatEvent } from "@/api/types";
import { LlmKeyCallout } from "@/components/HealthChips";
import { Markdown } from "@/components/Markdown";
import { Button, Skeleton } from "@/components/ui";
import { agentMeta, DEFAULT_GRAPH, toneColor } from "@/lib/agents";
import { formatMs } from "@/lib/format";
import { buildRouteState, contextFromGraph } from "@/lib/routeGraph";
import { loadTranscript, newTranscript, saveTranscript, type ChatMessage, type Transcript } from "@/lib/transcript";
import { cn, newId } from "@/lib/utils";
import { RoutePanel } from "./RoutePanel";

export default function ChatPage() {
  const graphQ = useGraph();
  const graph = graphQ.data ?? DEFAULT_GRAPH;
  const ctx = useMemo(() => contextFromGraph(graph), [graph]);

  const [transcript, setTranscript] = useState<Transcript>(loadTranscript);
  const [selectedId, setSelectedId] = useState<string | null>(() => [...transcript.messages].reverse().find((m) => m.role === "assistant")?.id ?? null);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [replay, setReplay] = useState<{ id: string; upto: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => saveTranscript(transcript), [transcript]);
  useEffect(() => () => abortRef.current?.abort(), []);

  const patchMessage = useCallback((id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setTranscript((t) => ({ ...t, messages: t.messages.map((m) => (m.id === id ? fn(m) : m)) }));
  }, []);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || streamingId) return;
      const userMsg: ChatMessage = { id: newId(), role: "user", text: message, createdAt: Date.now() };
      const asst: ChatMessage = { id: newId(), role: "assistant", text: "", createdAt: Date.now(), events: [], status: "streaming" };
      setTranscript((t) => ({ ...t, messages: [...t.messages, userMsg, asst] }));
      setSelectedId(asst.id);
      setReplay(null);
      setStreamingId(asst.id);
      const ac = new AbortController();
      abortRef.current = ac;
      let finished = false;
      const onEvent = (ev: ChatEvent) => {
        if (ev.type === "answer" || ev.type === "error") finished = true;
        patchMessage(asst.id, (m) => {
          const events = [...(m.events ?? []), ev];
          if (ev.type === "answer") return { ...m, events, text: ev.text, status: "done", elapsedMs: ev.elapsed_ms ?? null };
          if (ev.type === "error") return { ...m, events, status: "error", error: ev.message };
          return { ...m, events };
        });
      };
      await streamChat({ conversation_id: transcript.conversationId, message }, onEvent, ac.signal);
      if (!finished) {
        if (ac.signal.aborted) onEvent({ type: "error", message: "Stopped.", ts: Date.now() });
        else onEvent({ type: "error", message: "The stream ended without an answer. Check the app logs (make logs).", ts: Date.now() });
      }
      abortRef.current = null;
      setStreamingId(null);
    },
    [patchMessage, streamingId, transcript.conversationId],
  );

  const stop = () => abortRef.current?.abort();

  const newChat = async () => {
    abortRef.current?.abort();
    const old = transcript.conversationId;
    setTranscript(newTranscript());
    setSelectedId(null);
    setReplay(null);
    try {
      await endpoints.chatReset(old);
    } catch {
      /* the old session simply expires server-side */
    }
    toast.success("Started a new conversation");
  };

  // ---- route shown on the right -------------------------------------------------------------
  const selected = transcript.messages.find((m) => m.id === selectedId && m.role === "assistant") ?? null;
  const selectedEvents = selected?.events ?? [];
  const shownEvents = replay && replay.id === selected?.id ? selectedEvents.slice(0, replay.upto) : selectedEvents;
  const routeState = useMemo(() => buildRouteState(shownEvents, ctx), [shownEvents, ctx]);
  const question = useMemo(() => {
    if (!selected) return null;
    const idx = transcript.messages.findIndex((m) => m.id === selected.id);
    for (let i = idx - 1; i >= 0; i--) if (transcript.messages[i]!.role === "user") return transcript.messages[i]!.text;
    return null;
  }, [selected, transcript.messages]);

  // Replay: feed the stored events back in, paced by their original gaps (clamped).
  useEffect(() => {
    if (!replay || !selected) return;
    const evs = selected.events ?? [];
    if (replay.upto >= evs.length) {
      const t = setTimeout(() => setReplay(null), 600);
      return () => clearTimeout(t);
    }
    const prev = evs[replay.upto - 1]?.ts;
    const cur = evs[replay.upto]?.ts;
    const gap = prev && cur ? Math.min(900, Math.max(180, (cur - prev) * 0.8)) : 350;
    const t = setTimeout(() => setReplay((r) => (r ? { ...r, upto: r.upto + 1 } : r)), replay.upto === 0 ? 150 : gap);
    return () => clearTimeout(t);
  }, [replay, selected]);

  const live = !!streamingId && streamingId === selected?.id;
  const firstTs = selectedEvents[0]?.ts ?? selected?.createdAt ?? null;

  return (
    <div className="grid h-full grid-cols-1 overflow-y-auto lg:grid-cols-[minmax(340px,0.8fr)_minmax(0,1.25fr)] lg:overflow-hidden">
      <section className="flex min-h-[70dvh] min-w-0 flex-col border-border lg:min-h-0 lg:border-r" aria-label="Conversation">
        <ChatHeader onNew={newChat} disabled={!transcript.messages.length && !streamingId} />
        <TranscriptView
          messages={transcript.messages}
          selectedId={selectedId}
          streamingId={streamingId}
          onSelect={(id) => {
            setSelectedId(id);
            setReplay(null);
          }}
          onExample={send}
        />
        <Composer onSend={send} onStop={stop} streaming={!!streamingId} showExamples={transcript.messages.length > 0} onExample={send} />
      </section>
      <section className="h-[860px] min-w-0 border-t border-border bg-card lg:h-auto lg:min-h-0 lg:border-t-0" aria-label="Agent route">
        <RoutePanel
          graph={graph}
          state={routeState}
          live={live}
          liveSince={firstTs}
          replaying={!!replay}
          canReplay={selectedEvents.length > 0 && !streamingId}
          onReplay={() => selected && setReplay({ id: selected.id, upto: 0 })}
          onStopReplay={() => setReplay(null)}
          caption={question}
        />
      </section>
    </div>
  );
}

function ChatHeader({ onNew, disabled }: { onNew: () => void; disabled: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight">Ask Nimbus</h1>
        <p className="text-[13px] text-muted-foreground">Main agent → orchestrator → specialist agents</p>
      </div>
      <Button size="sm" variant="outline" onClick={onNew} disabled={disabled}>
        <MessageSquarePlus className="size-4" aria-hidden /> New chat
      </Button>
    </div>
  );
}

function Examples({ onPick, compact }: { onPick: (p: string) => void; compact?: boolean }) {
  const { data, isLoading, isError } = useChatExamples();
  if (isLoading)
    return (
      <div className={cn(compact ? "flex gap-2" : "grid grid-cols-1 gap-2.5 sm:grid-cols-2")}>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className={compact ? "h-8 w-40 rounded-full" : "h-[72px] w-full rounded-xl"} />
        ))}
      </div>
    );
  if (isError || !data?.length) return null;
  return (
    <div className={cn(compact ? "flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" : "grid grid-cols-1 gap-2.5 sm:grid-cols-2")}>
      {data.map((ex) => (
        <button
          key={ex.prompt}
          type="button"
          onClick={() => onPick(ex.prompt)}
          title={ex.prompt}
          className={cn(
            "group shrink-0 rounded-xl border border-border bg-card text-left transition-[border-color,background-color,transform] duration-150 hover:border-ring/60 hover:bg-muted/50 active:scale-[0.99]",
            compact ? "rounded-full px-3 py-1.5 text-[13px]" : "w-full px-4 py-3",
          )}
        >
          <span className={cn("font-semibold", compact ? "" : "block text-[13px] text-muted-foreground")}>{ex.label}</span>
          {compact ? null : <span className="mt-1 block text-[14.5px] leading-snug">{ex.prompt}</span>}
        </button>
      ))}
    </div>
  );
}

function RouteChips({ m }: { m: ChatMessage }) {
  const agents = new Set<string>();
  let steps = 0;
  for (const e of m.events ?? []) {
    if (e.type === "tool_call") {
      steps++;
      if (e.kind === "agent" && e.tool !== "orchestrator") agents.add(e.tool);
    }
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      {[...agents].map((a) => {
        const meta = agentMeta(a);
        return (
          <span key={a} className="inline-flex items-center gap-1.5 font-medium" style={{ color: toneColor(meta.tone) }}>
            <span className="size-1.5 rounded-full" style={{ background: toneColor(meta.tone) }} />
            {meta.short}
          </span>
        );
      })}
      <span className="text-muted-foreground">
        {steps} step{steps === 1 ? "" : "s"}
        {m.elapsedMs ? ` · ${formatMs(m.elapsedMs)}` : ""}
      </span>
    </span>
  );
}

function TranscriptView({
  messages,
  selectedId,
  streamingId,
  onSelect,
  onExample,
}: {
  messages: ChatMessage[];
  selectedId: string | null;
  streamingId: string | null;
  onSelect: (id: string) => void;
  onExample: (p: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, last?.text, last?.status]);

  if (!messages.length) {
    return (
      <div className="flex flex-1 overflow-y-auto px-6 py-10">
        <div className="m-auto flex w-full max-w-3xl flex-col items-center gap-6">
        <LlmKeyCallout className="w-full max-w-2xl" />
        <div className="text-center">
          <Waypoints className="mx-auto mb-3 size-9 text-agent-main" aria-hidden />
          <h2 className="text-xl font-semibold tracking-tight">Ask about Nimbus Markets</h2>
          <p className="mx-auto mt-1.5 max-w-md text-[14.5px] text-muted-foreground">
            Finance, trading or, once you've built its agent, marketing. Watch the route panel to see which agents and tools answer, and which run in parallel.
          </p>
        </div>
        <div className="w-full">
          <Examples onPick={onExample} />
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5">
      <LlmKeyCallout className="mb-4" />
      <ol className="mx-auto flex max-w-3xl flex-col gap-5">
        {messages.map((m) =>
          m.role === "user" ? (
            <li key={m.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[15px] whitespace-pre-wrap text-primary-foreground">{m.text}</div>
            </li>
          ) : (
            <li key={m.id}>
              <div
                role="button"
                tabIndex={0}
                aria-pressed={m.id === selectedId}
                onClick={() => onSelect(m.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(m.id);
                  }
                }}
                className={cn(
                  "group rounded-2xl rounded-tl-md border px-4 py-3 transition-[border-color,box-shadow,background-color] duration-150",
                  m.id === selectedId ? "border-agent-main/50 bg-card shadow-[0_6px_20px_-12px_hsl(var(--agent-main)/0.6)]" : "border-border bg-card hover:border-input",
                )}
              >
                <div className="mb-1.5 flex items-center gap-2 text-[12.5px]">
                  <span className="font-semibold" style={{ color: toneColor("main") }}>
                    Main agent
                  </span>
                  {m.status === "done" ? <RouteChips m={m} /> : null}
                  <span className="ml-auto text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">{m.id === selectedId ? "showing route" : "show route"}</span>
                </div>
                {m.status === "streaming" ? (
                  <div className="flex items-center gap-1.5 py-1.5 text-muted-foreground" aria-label="Agents are working">
                    <span className="typing-dot size-1.5 rounded-full bg-current" />
                    <span className="typing-dot size-1.5 rounded-full bg-current [animation-delay:150ms]" />
                    <span className="typing-dot size-1.5 rounded-full bg-current [animation-delay:300ms]" />
                    <span className="ml-1.5 text-[13.5px]">{m.id === streamingId ? "Routing your question…" : ""}</span>
                  </div>
                ) : m.status === "error" ? (
                  <div className="text-[14.5px]">
                    <p className="font-medium text-danger">Couldn't answer this one.</p>
                    <p className="mt-0.5 text-foreground/80">{m.error}</p>
                  </div>
                ) : (
                  <Markdown>{m.text}</Markdown>
                )}
              </div>
            </li>
          ),
        )}
      </ol>
      <div ref={endRef} />
    </div>
  );
}

function Composer({ onSend, onStop, streaming, showExamples, onExample }: { onSend: (t: string) => void; onStop: () => void; streaming: boolean; showExamples: boolean; onExample: (p: string) => void }) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [text]);
  const submit = () => {
    if (!text.trim() || streaming) return;
    onSend(text);
    setText("");
  };
  return (
    <div className="border-t border-border px-5 pt-3 pb-4">
      {showExamples && !streaming ? (
        <div className="mx-auto mb-2.5 max-w-3xl">
          <Examples onPick={onExample} compact />
        </div>
      ) : null}
      <form
        className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-input bg-card p-2 pl-4 transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/15"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Message
        </label>
        <textarea
          id="chat-input"
          ref={ref}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask about revenue, trades or campaigns…"
          className="max-h-[180px] min-h-[40px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground/80"
        />
        {streaming ? (
          <Button type="button" variant="outline" size="icon" onClick={onStop} aria-label="Stop" title="Stop">
            <Square className="size-4" />
          </Button>
        ) : (
          <Button type="submit" variant="primary" size="icon" disabled={!text.trim()} aria-label="Send" title="Send (Enter)">
            <ArrowUp className="size-[18px]" />
          </Button>
        )}
      </form>
      <p className="mx-auto mt-1.5 flex max-w-3xl items-center gap-1 text-[11.5px] text-muted-foreground">
        <RotateCcw className="size-3" aria-hidden /> Enter to send · Shift+Enter for a new line · click an answer to see its route
      </p>
    </div>
  );
}
