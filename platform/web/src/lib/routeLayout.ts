/**
 * Static layered layout for the Agent Route graph:
 *
 *   User → Main agent → Orchestrator   ← one row, so the graph stays landscape
 *   Finance   Trading   Marketing     ← one column per specialist
 *    ├ tool    ├ tool    ├ tool     ← tools stacked on a rail under their agent
 *    └ tool    └ tool    └ tool
 *   [schema]  [schema]  [schema]    ← datasource, bracketed from each tool
 *
 * Positions depend only on the topology (graph + any tools/agents that showed
 * up in events), never on status, so nodes don't jump while a turn streams.
 */
import type { Graph, GraphToolType, ToolKind } from "@/api/types";
import { agentMeta, type AgentTone } from "./agents";
import { dsNodeId, edgeId, toolNodeId, USER_NODE, type EdgeStatus, type NodeStatus, type RouteState } from "./routeGraph";

export const COL_W = 300;
export const AGENT_W = 260;
export const TOOL_INDENT = 28;
export const TOOL_W = AGENT_W - TOOL_INDENT;
export const TOOL_GAP = 68;

export interface RouteNodeData extends Record<string, unknown> {
  label: string;
  sublabel?: string;
  /** Datasource nodes: the internet rather than a Postgres schema. */
  internet?: boolean;
  tone: AgentTone;
  status: NodeStatus;
  steps: number[];
  ms: number | null;
  dim: boolean;
  role?: "user" | "root" | "router" | "specialist";
  toolKind?: ToolKind | GraphToolType;
  rowCount?: number | null;
  error?: string | null;
  title?: string;
  runs?: number;
}

export interface RouteEdgeData extends Record<string, unknown> {
  status: EdgeStatus;
  tone: AgentTone;
  dim: boolean;
  dashed?: boolean;
}

export interface LayoutNode {
  id: string;
  type: "user" | "agent" | "tool" | "datasource";
  position: { x: number; y: number };
  data: RouteNodeData;
  width: number;
}

export interface LayoutEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  data: RouteEdgeData;
}

export function layoutRoute(graph: Graph, state: RouteState): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const running = state.status !== "idle";
  const agentsById = new Map(graph.agents.map((a) => [a.id, a] as const));
  const root = graph.agents.find((a) => a.role === "root" || !a.parent)?.id ?? "main_agent";
  const router = graph.agents.find((a) => a.role === "router")?.id ?? "orchestrator";

  // Specialists: graph order, then any extra agents that appeared in events.
  const specialists = graph.agents.filter((a) => a.id !== root && a.id !== router).map((a) => a.id);
  for (const n of Object.values(state.nodes)) {
    if (n.kind === "agent" && n.id !== root && n.id !== router && !specialists.includes(n.id)) specialists.push(n.id);
  }

  // Tools per specialist: graph tools, then event-only tools.
  const toolsBy = new Map<string, { name: string; kind: ToolKind | GraphToolType; title?: string }[]>();
  for (const s of specialists) toolsBy.set(s, []);
  for (const t of graph.tools) toolsBy.get(t.agent)?.push({ name: t.name, kind: t.tool_type, title: t.title });
  for (const n of Object.values(state.nodes)) {
    if (n.kind !== "tool" || !n.agent || !n.name) continue;
    const list = toolsBy.get(n.agent);
    if (list && !list.some((t) => t.name === n.name)) list.push({ name: n.name, kind: n.toolKind ?? "sql" });
  }

  const ns = (id: string) => state.nodes[id];
  const status = (id: string): NodeStatus => ns(id)?.status ?? "idle";
  const dim = (id: string) => running && status(id) === "idle";
  const est = (s: string, t: string): EdgeStatus => state.edges[edgeId(s, t)]?.status ?? "idle";

  const nodes: LayoutNode[] = [];
  const edges: LayoutEdge[] = [];
  const width = Math.max(1, specialists.length) * COL_W - (COL_W - AGENT_W);
    const toneOf = (id: string) => agentMeta(id, agentsById.get(id)).tone;

  const agentNode = (id: string, x: number, y: number, role: RouteNodeData["role"]) => {
    const a = agentsById.get(id);
    const meta = agentMeta(id, a);
    const st = ns(id);
    nodes.push({
      id,
      type: "agent",
      position: { x, y },
      width: AGENT_W,
      data: {
        label: meta.label,
        sublabel: role === "root" ? "persona · writes the answer" : role === "router" ? "routes to specialists" : (a?.description ?? "specialist"),
        tone: meta.tone,
        status: status(id),
        steps: st?.steps ?? [],
        ms: st?.ms ?? null,
        dim: dim(id),
        role,
        error: st?.error ?? null,
        runs: st?.runs ?? 0,
      },
    });
  };

  // Row 0: User → Main → Orchestrator, left to right; the orchestrator sits
  // over the specialists so its fan-out reads as a tree.
  const ROW0_Y = 0;
  const orchX = Math.max(width - AGENT_W, 2 * (AGENT_W + 50) + 140 - AGENT_W);
  const mainX = orchX - AGENT_W - 50;
  const userX = mainX - 140 - 50;
  nodes.push({
    id: USER_NODE,
    type: "user",
    position: { x: userX, y: ROW0_Y + 8 },
    width: 140,
    data: { label: "User", tone: "other", status: status(USER_NODE), steps: [], ms: state.elapsedMs, dim: false, role: "user" },
  });
  agentNode(root, mainX, ROW0_Y, "root");
  edges.push({ id: edgeId(USER_NODE, root), source: USER_NODE, target: root, targetHandle: "left", data: { status: est(USER_NODE, root), tone: toneOf(root), dim: running && est(USER_NODE, root) === "idle" } });
  agentNode(router, orchX, ROW0_Y, "router");
  edges.push({ id: edgeId(root, router), source: root, sourceHandle: "right", target: router, targetHandle: "left", data: { status: est(root, router), tone: toneOf(router), dim: running && est(root, router) === "idle" } });

  const AGENT_Y = 130;
  const TOOLS_Y = AGENT_Y + 96;
  const maxTools = Math.max(1, ...[...toolsBy.values()].map((l) => l.length));
  const DS_Y = TOOLS_Y + maxTools * TOOL_GAP + 16;

  specialists.forEach((sid, i) => {
    const x = i * COL_W;
    agentNode(sid, x, AGENT_Y, "specialist");
    const parent = agentsById.get(sid)?.parent ?? router;
    const e = est(parent, sid);
    edges.push({ id: edgeId(parent, sid), source: parent, sourceHandle: "bottom", target: sid, targetHandle: "top", data: { status: e, tone: toneOf(sid), dim: running && e === "idle" } });

    const tone = toneOf(sid);
    const ds = agentsById.get(sid)?.datasource;
    const dsId = ds ? dsNodeId(ds) : null;
    (toolsBy.get(sid) ?? []).forEach((t, j) => {
      const id = toolNodeId(sid, t.name);
      const st = ns(id);
      nodes.push({
        id,
        type: "tool",
        position: { x: x + TOOL_INDENT, y: TOOLS_Y + j * TOOL_GAP },
        width: TOOL_W,
        data: {
          label: t.name,
          title: t.title,
          tone,
          status: st?.status ?? "idle",
          steps: st?.steps ?? [],
          ms: st?.ms ?? null,
          dim: running && (st?.status ?? "idle") === "idle",
          toolKind: st?.toolKind ?? t.kind,
          rowCount: st?.rowCount ?? null,
          error: st?.error ?? null,
          runs: st?.runs ?? 0,
        },
      });
      const te = est(sid, id);
      edges.push({ id: edgeId(sid, id), source: sid, sourceHandle: "rail", target: id, data: { status: te, tone, dim: running && te === "idle" } });
      if (dsId) {
        const de = est(id, dsId);
        edges.push({ id: edgeId(id, dsId), source: id, sourceHandle: "ds", target: dsId, targetHandle: "side", data: { status: de, tone, dim: running && de === "idle", dashed: de === "idle" } });
      }
    });

    if (ds && dsId) {
      const label = graph.datasources.find((d) => d.id === ds)?.label ?? ds;
      const st = ns(dsId);
      nodes.push({
        id: dsId,
        type: "datasource",
        position: { x: x + TOOL_INDENT, y: DS_Y },
        width: TOOL_W,
        data: { label, tone, status: st?.status ?? "idle", steps: [], ms: null, dim: running && (st?.status ?? "idle") === "idle", sublabel: ds === "internet" ? "via the news MCP server" : `Postgres · ${ds}.*`, internet: ds === "internet" },
      });
    }
  });

  return { nodes, edges };
}
