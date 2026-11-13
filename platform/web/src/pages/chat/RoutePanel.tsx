import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, PanelRightClose, Play, Square, Workflow } from "@/components/icons";
import type { Graph } from "@/api/types";
import { RouteGraph } from "@/graph/RouteGraph";
import { Button } from "@/components/ui";
import { agentMeta, toneColor } from "@/lib/agents";
import { formatMs } from "@/lib/format";
import { activeAgents, parallelGroups, type RouteState } from "@/lib/routeGraph";
import { StepTimeline } from "./StepTimeline";

function useTicker(on: boolean, since: number | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [on]);
  return on && since ? Math.max(0, now - since) : 0;
}

export interface RoutePanelProps {
  graph: Graph;
  state: RouteState;
  /** Live streaming of the latest turn (vs. showing a finished one). */
  live: boolean;
  liveSince: number | null;
  replaying: boolean;
  canReplay: boolean;
  onReplay: () => void;
  onStopReplay: () => void;
  caption: string | null;
  /** Collapse the panel (large screens only). */
  onCollapse?: () => void;
}

export function RoutePanel({ graph, state, live, liveSince, replaying, canReplay, onReplay, onStopReplay, caption, onCollapse }: RoutePanelProps) {
  const elapsed = useTicker(live, liveSince);
  const working = activeAgents(state).filter((a) => a !== "main_agent" || activeAgents(state).length === 1);
  const groups = parallelGroups(state.steps);
  const agentsUsed = new Set(state.steps.filter((s) => s.kind === "agent").map((s) => s.tool));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-16 flex-wrap items-center gap-x-4 gap-y-2 border-b border-border px-5 py-2.5">
        <div className="flex items-center gap-2">
          <Workflow className="size-4 text-muted-foreground" aria-hidden />
          <h2 className="text-[15px] font-semibold">Agent route</h2>
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2 text-[13px]" aria-live="polite">
          {live ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-muted py-1 pr-3 pl-2 font-medium">
              <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden />
              Working… <span className="font-mono tabular-nums">{(elapsed / 1000).toFixed(1)}s</span>
              {working.length ? (
                <span className="hidden truncate font-normal text-muted-foreground sm:inline">
                  ·{" "}
                  {working.map((a, i) => (
                    <span key={a} style={{ color: toneColor(agentMeta(a).tone) }}>
                      {i ? ", " : ""}
                      {agentMeta(a).short}
                    </span>
                  ))}
                </span>
              ) : null}
            </span>
          ) : replaying ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-muted px-3 py-1 font-medium">Replaying…</span>
          ) : state.status === "done" ? (
            <span className="truncate text-muted-foreground">
              {state.steps.length} step{state.steps.length === 1 ? "" : "s"} · {agentsUsed.size} agent{agentsUsed.size === 1 ? "" : "s"}
              {groups.size ? ` · ${groups.size} parallel fan-out${groups.size === 1 ? "" : "s"}` : ""} · {formatMs(state.elapsedMs)}
            </span>
          ) : state.status === "error" ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-danger">
              <AlertTriangle className="size-3.5" aria-hidden /> Turn failed
            </span>
          ) : (
            <span className="text-muted-foreground">Ask a question to see how it is routed.</span>
          )}
        </div>
        {replaying ? (
          <Button size="sm" variant="outline" onClick={onStopReplay}>
            <Square className="size-3.5" aria-hidden /> Stop
          </Button>
        ) : (
          <Button size="sm" variant="outline" onClick={onReplay} disabled={!canReplay || live} title="Animate this route step by step">
            <Play className="size-3.5" aria-hidden /> Replay
          </Button>
        )}
        {onCollapse ? (
          <Button size="icon" variant="ghost" onClick={onCollapse} className="hidden lg:inline-flex" aria-label="Hide agent route" title="Hide agent route">
            <PanelRightClose className="size-4" aria-hidden />
          </Button>
        ) : null}
      </div>
      <div className="flex items-center gap-4 px-5 pt-3 pb-1 text-xs text-muted-foreground">
        <span className="min-w-0 flex-1 truncate">{caption ? <>Route for: “{caption}”</> : "No question selected"}</span>
        <Legend />
      </div>

      <div className="relative min-h-[340px] flex-[1.7] border-b border-border">
        <RouteGraph graph={graph} state={state} className="absolute inset-0" />
      </div>

      <div className="min-h-[140px] flex-1 overflow-y-auto px-3 py-3">
        {state.error ? (
          <div role="alert" className="mx-2 mb-3 flex gap-2.5 rounded-lg border border-danger/25 bg-danger/8 p-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
            <div>
              <div className="font-semibold text-danger">The agents hit an error</div>
              <div className="mt-0.5 text-foreground/85">{state.error}</div>
            </div>
          </div>
        ) : null}
        {state.steps.length ? (
          <StepTimeline steps={state.steps} />
        ) : (
          <p className="px-2 py-4 text-sm text-muted-foreground">
            {state.status === "running"
              ? "The main agent is reading the question…"
              : state.status === "done"
                ? "The main agent answered this one itself, without calling a specialist."
                : "Each delegation and tool call appears here in order, with its arguments, row count and timing."}
          </p>
        )}
      </div>
    </div>
  );
}

function Legend() {
  const items: [string, string][] = [
    ["main", "Main"],
    ["orchestrator", "Orchestrator"],
    ["finance", "Finance"],
    ["trading", "Trading"],
    ["news", "News"],
    ["marketing", "Marketing"],
  ];
  return (
    <div className="hidden shrink-0 gap-x-3 text-[11px] xl:flex" aria-label="Agent colours">
      {items.map(([tone, label]) => (
        <span key={tone} className="inline-flex items-center gap-1.5">
          <span className="size-1.5 rounded-full" style={{ background: `hsl(var(--agent-${tone}))` }} />
          {label}
        </span>
      ))}
    </div>
  );
}
