/**
 * Route-graph reducer: folds the chat SSE events into the state the Agent
 * Route panel draws (node + edge status, numbered steps, parallel groups).
 * Pure and synchronous, so the same function powers live streaming, clicking
 * an old answer (fold all its events) and Replay (fold a growing prefix).
 */
import type { ChatEvent, Graph, ToolKind } from "@/api/types";

export type NodeStatus = "idle" | "queued" | "active" | "done" | "error";
export type EdgeStatus = "idle" | "active" | "done" | "error";
export type RouteNodeKind = "user" | "agent" | "tool" | "datasource";

export interface RouteNodeState {
  id: string;
  kind: RouteNodeKind;
  status: NodeStatus;
  /** Step numbers that touched this node (delegations into an agent, calls of a tool). */
  steps: number[];
  /** Duration of the latest completed run. */
  ms: number | null;
  /** Agent that owns a tool node. */
  agent?: string;
  /** For tool nodes: sql | factual | function. */
  toolKind?: ToolKind;
  /** For tool and datasource nodes: the name / id. */
  name?: string;
  rowCount?: number | null;
  error?: string | null;
  runs: number;
}

export interface RouteEdgeState {
  id: string;
  source: string;
  target: string;
  status: EdgeStatus;
  step: number | null;
}

export type StepStatus = "running" | "ok" | "error";

export interface RouteStep {
  n: number;
  callId: string;
  /** The calling agent. */
  agent: string;
  tool: string;
  kind: ToolKind;
  args: Record<string, unknown> | null;
  status: StepStatus;
  ms: number | null;
  rowCount: number | null;
  error: string | null;
  preview: unknown;
  startTs: number | null;
  endTs: number | null;
  /** Steps sharing a group were in flight at the same time under the same caller. */
  group: number;
}

export type RouteStatus = "idle" | "running" | "done" | "error";

export interface RouteState {
  status: RouteStatus;
  nodes: Record<string, RouteNodeState>;
  edges: Record<string, RouteEdgeState>;
  steps: RouteStep[];
  answer: string | null;
  error: string | null;
  route: string[] | null;
  startTs: number | null;
  elapsedMs: number | null;
  conversationId: string | null;
}

export interface RouteContext {
  /** agent id → parent agent id (main_agent has none). */
  parents: Record<string, string | undefined>;
  /** agent id → datasource id. */
  datasources: Record<string, string | undefined>;
  root: string;
}

export const USER_NODE = "user";
export const toolNodeId = (agent: string, tool: string) => `tool:${agent}:${tool}`;
export const dsNodeId = (ds: string) => `ds:${ds}`;
export const edgeId = (s: string, t: string) => `${s}->${t}`;

export function contextFromGraph(graph: Graph): RouteContext {
  const parents: RouteContext["parents"] = {};
  const datasources: RouteContext["datasources"] = {};
  let root = "main_agent";
  for (const a of graph.agents) {
    parents[a.id] = a.parent;
    datasources[a.id] = a.datasource;
    if (a.role === "root" || !a.parent) root = a.id;
  }
  return { parents, datasources, root };
}

export function initialRouteState(): RouteState {
  return {
    status: "idle",
    nodes: {},
    edges: {},
    steps: [],
    answer: null,
    error: null,
    route: null,
    startTs: null,
    elapsedMs: null,
    conversationId: null,
  };
}

// ---- small immutable helpers -----------------------------------------------------------

function ensureNode(s: RouteState, id: string, kind: RouteNodeKind, extra: Partial<RouteNodeState> = {}): RouteNodeState {
  const existing = s.nodes[id];
  if (existing) return existing;
  const n: RouteNodeState = { id, kind, status: "idle", steps: [], ms: null, runs: 0, ...extra };
  s.nodes = { ...s.nodes, [id]: n };
  return n;
}

function patchNode(s: RouteState, id: string, patch: Partial<RouteNodeState>) {
  const n = s.nodes[id];
  if (!n) return;
  s.nodes = { ...s.nodes, [id]: { ...n, ...patch } };
}

function setEdge(s: RouteState, source: string, target: string, status: EdgeStatus, step?: number | null) {
  const id = edgeId(source, target);
  const prev = s.edges[id];
  s.edges = {
    ...s.edges,
    [id]: { id, source, target, status, step: step === undefined ? (prev?.step ?? null) : step },
  };
}

function edgeStatus(s: RouteState, source: string, target: string): EdgeStatus | undefined {
  return s.edges[edgeId(source, target)]?.status;
}

function settle(s: RouteState, to: "done" | "error") {
  const nodes: Record<string, RouteNodeState> = {};
  for (const [k, n] of Object.entries(s.nodes)) {
    nodes[k] = n.status === "active" || n.status === "queued" ? { ...n, status: to === "error" && n.kind !== "user" ? "error" : "done" } : n;
  }
  const edges: Record<string, RouteEdgeState> = {};
  for (const [k, e] of Object.entries(s.edges)) edges[k] = e.status === "active" ? { ...e, status: to } : e;
  s.nodes = nodes;
  s.edges = edges;
  if (to === "error") {
    s.steps = s.steps.map((st) => (st.status === "running" ? { ...st, status: "error", error: st.error ?? "interrupted" } : st));
  }
}

function begin(s: RouteState, ts: number | null, conversationId: string | null) {
  Object.assign(s, initialRouteState());
  s.status = "running";
  s.startTs = ts;
  s.conversationId = conversationId;
  ensureNode(s, USER_NODE, "user");
  patchNode(s, USER_NODE, { status: "active" });
}

// ---- reducer ------------------------------------------------------------------------------

export function reduceRoute(prev: RouteState, ev: ChatEvent, ctx: RouteContext): RouteState {
  const s: RouteState = { ...prev };
  const ts = typeof ev.ts === "number" ? ev.ts : null;

  if (ev.type === "start") {
    begin(s, ts, ev.conversation_id ?? null);
    return s;
  }
  if (s.status === "idle") begin(s, ts, null);

  switch (ev.type) {
    case "agent_start": {
      const node = ensureNode(s, ev.agent, "agent");
      patchNode(s, ev.agent, { status: "active", runs: node.runs + 1, error: null });
      const parent = ctx.parents[ev.agent];
      if (ev.agent === ctx.root || !parent) {
        setEdge(s, USER_NODE, ev.agent, "active");
      } else if (edgeStatus(s, parent, ev.agent) !== "active") {
        // No delegation tool_call seen (or it already resolved) — still show the hop.
        ensureNode(s, parent, "agent");
        setEdge(s, parent, ev.agent, "active");
      }
      break;
    }

    case "agent_end": {
      const node = ensureNode(s, ev.agent, "agent");
      patchNode(s, ev.agent, { status: node.status === "error" ? "error" : "done", ms: ev.ms ?? node.ms });
      const parent = ctx.parents[ev.agent];
      const src = ev.agent === ctx.root || !parent ? USER_NODE : parent;
      if (edgeStatus(s, src, ev.agent) === "active") setEdge(s, src, ev.agent, "done");
      break;
    }

    case "tool_call": {
      const n = s.steps.length + 1;
      // Parallel fan-out: another call from the same caller is still in flight.
      const sibling = s.steps.find((st) => st.status === "running" && st.agent === ev.agent);
      const group = sibling ? sibling.group : n;
      const step: RouteStep = {
        n,
        callId: ev.call_id,
        agent: ev.agent,
        tool: ev.tool,
        kind: ev.kind,
        args: ev.args ?? null,
        status: "running",
        ms: null,
        rowCount: null,
        error: null,
        preview: undefined,
        startTs: ts,
        endTs: null,
        group,
      };
      s.steps = [...s.steps, step];
      ensureNode(s, ev.agent, "agent");

      if (ev.kind === "agent") {
        const target = ensureNode(s, ev.tool, "agent");
        patchNode(s, ev.tool, {
          status: target.status === "active" ? "active" : "queued",
          steps: [...target.steps, n],
        });
        setEdge(s, ev.agent, ev.tool, "active", n);
      } else {
        const id = toolNodeId(ev.agent, ev.tool);
        const tn = ensureNode(s, id, "tool", { agent: ev.agent, name: ev.tool, toolKind: ev.kind });
        patchNode(s, id, { status: "active", steps: [...tn.steps, n], toolKind: ev.kind, runs: tn.runs + 1, error: null });
        setEdge(s, ev.agent, id, "active", n);
        const ds = ctx.datasources[ev.agent];
        if (ds) {
          const dsId = dsNodeId(ds);
          ensureNode(s, dsId, "datasource", { name: ds });
          patchNode(s, dsId, { status: "active" });
          setEdge(s, id, dsId, "active", n);
        }
      }
      break;
    }

    case "tool_result": {
      let idx = s.steps.findIndex((st) => st.callId === ev.call_id && st.status === "running");
      if (idx === -1) idx = s.steps.findIndex((st) => st.callId === ev.call_id);
      if (idx === -1) {
        // Result for a call we never saw: match the oldest running call of that tool.
        idx = s.steps.findIndex((st) => st.status === "running" && st.agent === ev.agent && st.tool === ev.tool);
      }
      const failed = ev.ok === false || !!ev.error;
      const status: StepStatus = failed ? "error" : "ok";
      let ms = ev.ms ?? null;
      if (idx !== -1) {
        const st = s.steps[idx]!;
        if (ms === null && st.startTs !== null && ts !== null) ms = ts - st.startTs;
        const updated: RouteStep = {
          ...st,
          status,
          ms,
          rowCount: ev.row_count ?? null,
          error: ev.error ?? null,
          preview: ev.preview,
          endTs: ts,
        };
        s.steps = s.steps.map((x, i) => (i === idx ? updated : x));
      }
      const kind = ev.kind ?? s.steps[idx]?.kind;
      if (kind === "agent") {
        setEdge(s, ev.agent, ev.tool, failed ? "error" : "done");
        const target = s.nodes[ev.tool];
        if (target && (target.status === "active" || target.status === "queued" || failed)) {
          patchNode(s, ev.tool, { status: failed ? "error" : "done", ms: target.ms ?? ms, error: ev.error ?? null });
        }
      } else {
        const id = toolNodeId(ev.agent, ev.tool);
        ensureNode(s, id, "tool", { agent: ev.agent, name: ev.tool, toolKind: kind });
        patchNode(s, id, { status: failed ? "error" : "done", ms, rowCount: ev.row_count ?? null, error: ev.error ?? null });
        setEdge(s, ev.agent, id, failed ? "error" : "done");
        const ds = ctx.datasources[ev.agent];
        if (ds) {
          const dsId = dsNodeId(ds);
          setEdge(s, id, dsId, failed ? "error" : "done");
          const stillBusy = Object.values(s.edges).some((e) => e.target === dsId && e.status === "active");
          if (!stillBusy) patchNode(s, dsId, { status: "done" });
        }
      }
      break;
    }

    case "answer": {
      s.answer = ev.text;
      s.route = ev.route ?? null;
      s.elapsedMs = ev.elapsed_ms ?? (s.startTs !== null && ts !== null ? ts - s.startTs : null);
      settle(s, "done");
      s.status = "done";
      break;
    }

    case "error": {
      s.error = ev.message;
      if (s.startTs !== null && ts !== null) s.elapsedMs = ts - s.startTs;
      settle(s, "error");
      s.status = "error";
      break;
    }
  }
  return s;
}

export function buildRouteState(events: readonly ChatEvent[], ctx: RouteContext): RouteState {
  let s = initialRouteState();
  for (const ev of events) s = reduceRoute(s, ev, ctx);
  return s;
}

/** Group ids that contain more than one step, i.e. real parallel fan-outs. */
export function parallelGroups(steps: readonly RouteStep[]): Map<number, number[]> {
  const m = new Map<number, number[]>();
  for (const st of steps) m.set(st.group, [...(m.get(st.group) ?? []), st.n]);
  for (const [k, v] of m) if (v.length < 2) m.delete(k);
  return m;
}

/** Agents currently working (for the "Working…" label). */
export function activeAgents(s: RouteState): string[] {
  return Object.values(s.nodes)
    .filter((n) => n.kind === "agent" && n.status === "active")
    .map((n) => n.id);
}
