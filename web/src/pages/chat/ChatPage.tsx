import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowUp, MessageSquarePlus, Square, Waypoints, Workflow } from "@/components/icons";
import { endpoints, streamChat } from "@/api/client";
import { useChatExamples, useGraph } from "@/api/hooks";
import type { ChatEvent } from "@/api/types";
import { LlmKeyCallout } from "@/components/LlmKeyCallout";
import { Markdown } from "@/components/Markdown";
import { SplitView, type RightPane } from "@/components/SplitView";
import { Button, PRESS, Skeleton } from "@/components/ui";
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
          // Answer text streams in; it isn't part of the route, so it stays out of `events`.
          if (ev.type === "answer_delta") return { ...m, text: m.text + ev.text };
          const events = [...(m.events ?? []), ev];
          // Text the main agent wrote before handing off is a preamble; the answer comes after.
          if (ev.type === "tool_call" && ev.agent === "main_agent") return { ...m, events, text: "" };
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
  const location = useLocation();
  const navigate = useNavigate();

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
  };

  // The sidebar's New chat button lands here with a fresh `newChat` marker in the route state.
  const newChatMarker = (location.state as { newChat?: number } | null)?.newChat;
  useEffect(() => {
    if (!newChatMarker) return;
    void newChat();
    navigate(location.pathname, { replace: true, state: null });
  }, [newChatMarker]);

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
    <SplitView
      storageKey="nimbus.routePane"
      rightLabel="Agent route"
      left={(route) => (
        <section className="flex min-h-0 flex-1 flex-col" aria-label="Conversation">
          <ChatHeader
            title={transcript.messages.find((m) => m.role === "user")?.text ?? "New chat"}
            onNew={newChat}
            canStartNew={transcript.messages.length > 0 || !!streamingId}
            route={route}
          />
          {transcript.messages.length ? (
            <>
              <TranscriptView
                messages={transcript.messages}
                selectedId={selectedId}
                streamingId={streamingId}
                onSelect={(id) => {
                  setSelectedId(id);
                  setReplay(null);
                }}
              />
              <div className="px-5 pt-2 pb-5">
                <Composer onSend={send} onStop={stop} streaming={!!streamingId} />
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 overflow-y-auto px-5 pb-[12vh]">
              <LlmKeyCallout className="w-full max-w-3xl" />
              <h2 className="text-center text-[28px] font-semibold tracking-tight">What would you like to know?</h2>
              <div className="w-full">
                <Composer onSend={send} onStop={stop} streaming={!!streamingId} />
              </div>
              <div className="w-full max-w-3xl">
                <Examples onPick={send} />
              </div>
            </div>
          )}
        </section>
      )}
      right={(collapse) => (
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
          onCollapse={collapse}
        />
      )}
    />
  );
}

function ChatHeader({ title, onNew, canStartNew, route }: { title: string; onNew: () => void; canStartNew: boolean; route: RightPane }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 px-4">
      <h1 className="min-w-0 flex-1 truncate text-[15px] font-medium">{title}</h1>
      {/* The sidebar has New chat on larger screens. */}
      <Button size="icon" variant="ghost" onClick={onNew} disabled={!canStartNew} className="md:hidden" aria-label="New chat" title="New chat">
        <MessageSquarePlus className="size-[18px]" aria-hidden />
      </Button>
      <Button size="sm" variant="ghost" onClick={route.toggle} aria-pressed={route.open} className={cn("hidden lg:inline-flex", route.open && "bg-muted")}>
        <Workflow className="size-4" aria-hidden /> Agent route
      </Button>
    </header>
  );
}

function Examples({ onPick }: { onPick: (p: string) => void }) {
  const { data, isLoading, isError } = useChatExamples();
  if (isLoading)
    return (
      <div className="flex flex-wrap justify-center gap-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-9 w-40 rounded-full" />
        ))}
      </div>
    );
  if (isError || !data?.length) return null;
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {data.map((ex) => (
        <button
          key={ex.prompt}
          type="button"
          onClick={() => onPick(ex.prompt)}
          title={ex.prompt}
          className={cn(
            "rounded-full border border-border px-3.5 py-2 text-[13px] text-muted-foreground transition-[background-color,color,scale] duration-160 ease-out hover:bg-muted hover:text-foreground",
            PRESS,
          )}
        >
          {ex.label}
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
}: {
  messages: ChatMessage[];
  selectedId: string | null;
  streamingId: string | null;
  onSelect: (id: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, last?.text, last?.status]);

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5">
      <LlmKeyCallout className="mb-4" />
      <ol className="mx-auto flex max-w-3xl flex-col gap-8">
        {messages.map((m) =>
          m.role === "user" ? (
            <li key={m.id} className="flex justify-end">
              <div className="max-w-[80%] rounded-3xl bg-muted px-5 py-2.5 text-[15px] whitespace-pre-wrap">{m.text}</div>
            </li>
          ) : (
            <li key={m.id} className="min-w-0">
              {m.status === "streaming" && m.text ? (
                <Markdown>{m.text}</Markdown>
              ) : m.status === "streaming" ? (
                <div className="flex items-center gap-1.5 py-1.5 text-muted-foreground" aria-label="Agents are working">
                  <span className="typing-dot size-1.5 rounded-full bg-current" />
                  <span className="typing-dot size-1.5 rounded-full bg-current [animation-delay:150ms]" />
                  <span className="typing-dot size-1.5 rounded-full bg-current [animation-delay:300ms]" />
                  <span className="ml-1.5 text-[13px]">{m.id === streamingId ? "Routing your question…" : ""}</span>
                </div>
              ) : m.status === "error" ? (
                <div className="text-[15px]">
                  <p className="font-medium text-danger">Couldn't answer this one.</p>
                  <p className="mt-0.5 text-foreground/80">{m.error}</p>
                </div>
              ) : (
                <Markdown>{m.text}</Markdown>
              )}
              {m.status === "done" || m.status === "error" ? (
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                  {m.status === "done" ? <RouteChips m={m} /> : null}
                  <button
                    type="button"
                    aria-pressed={m.id === selectedId}
                    onClick={() => onSelect(m.id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 transition-colors duration-150",
                      m.id === selectedId ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Waypoints className="size-3.5" aria-hidden />
                    {m.id === selectedId ? "Showing route" : "Show route"}
                  </button>
                </div>
              ) : null}
            </li>
          ),
        )}
      </ol>
      <div ref={endRef} />
    </div>
  );
}

function Composer({ onSend, onStop, streaming }: { onSend: (t: string) => void; onStop: () => void; streaming: boolean }) {
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
    <div>
      <form
        className="mx-auto flex max-w-3xl items-end gap-2 rounded-[28px] border border-input bg-card p-2.5 pl-5 shadow-md transition-[border-color,box-shadow] duration-150 ease-out focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/15"
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
          placeholder="Ask Nimbus anything…"
          className="max-h-[180px] min-h-[40px] flex-1 resize-none bg-transparent py-2 text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground/80"
        />
        {streaming ? (
          <Button type="button" variant="outline" size="icon" onClick={onStop} aria-label="Stop" title="Stop" className="rounded-full">
            <Square className="size-4" />
          </Button>
        ) : (
          <Button type="submit" variant="primary" size="icon" disabled={!text.trim()} aria-label="Send" title="Send (Enter)" className="rounded-full">
            <ArrowUp className="size-[18px]" />
          </Button>
        )}
      </form>
    </div>
  );
}
