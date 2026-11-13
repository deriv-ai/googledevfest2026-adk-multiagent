import { memo, useMemo } from "react";
import { BaseEdge, Controls, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider, type Edge, type EdgeProps, type Node, type NodeProps } from "@xyflow/react";
import { Code2, Database, Globe, LayoutPanelLeft, Table2, Users, Wand2, type AppIcon } from "@/components/icons";
import { TONE_ICON } from "@/components/Badges";
import type { Graph } from "@/api/types";
import { toneColor, type AgentTone } from "@/lib/agents";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { roundedPath } from "./paths";
import { useAutoFit, useSyncedNodes } from "./useAutoFit";

export interface ArchNodeInfo {
  id: string;
  title: string;
  subtitle: string;
  body: string;
  link?: { to: string; label: string };
}

interface ArchData extends Record<string, unknown> {
  info: ArchNodeInfo;
  icon: AppIcon;
  tone: AgentTone | null;
  selected: boolean;
  pending: boolean;
  onSelect: (id: string) => void;
}
type ANode = Node<ArchData, "arch">;
interface LaneData extends Record<string, unknown> {
  label: string;
  width: number;
  height: number;
}
type LNode = Node<LaneData, "lane">;

export const WORKSHOP_NOTE = "built in the workshop";

/** Icon tile colours; a pending node gets a soft tint instead of a solid fill. */
export function iconStyle(tone: AgentTone | null, pending = false): React.CSSProperties {
  if (!tone) return { background: "hsl(var(--muted))", color: "hsl(var(--foreground))" };
  return pending ? { background: toneColor(tone, 0.14), color: toneColor(tone) } : { background: toneColor(tone), color: "white" };
}

const ArchNode = memo(function ArchNode({ data }: NodeProps<ANode>) {
  const { info, icon: Icon, tone, selected, pending, onSelect } = data;
  return (
    <button
      type="button"
      onClick={() => onSelect(info.id)}
      className={cn(
        "relative flex w-[210px] items-center gap-3 rounded-xl border bg-card px-3 py-2.5 text-left transition-[box-shadow,border-color,outline-color,scale] duration-200 ease-out active:scale-[0.97]",
        selected ? "" : pending ? "border-input hover:border-muted-foreground/50" : "border-border hover:border-input",
        pending && "border-dashed",
      )}
      style={{
        // Selected: border + 1px outline reads as 2px without nudging the content.
        borderColor: selected ? (tone ? toneColor(tone) : "hsl(var(--foreground))") : undefined,
        outline: `1px solid ${selected ? (tone ? toneColor(tone) : "hsl(var(--foreground))") : "transparent"}`,
        outlineOffset: 0,
        boxShadow: selected ? `0 10px 28px -14px ${tone ? toneColor(tone, 0.7) : "rgb(0 0 0 / .35)"}` : "var(--elev-1)",
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="target" id="top" position={Position.Top} />
      <Handle type="target" id="upper" position={Position.Left} style={{ top: "25%" }} />
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg" style={iconStyle(tone, pending)}>
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm leading-tight font-semibold">{info.title}</span>
        <span className="block truncate text-xs text-muted-foreground">{pending ? WORKSHOP_NOTE : info.subtitle}</span>
      </span>
      <Handle type="source" position={Position.Right} />
      <Handle type="source" id="bottom" position={Position.Bottom} />
    </button>
  );
});

const LaneNode = memo(function LaneNode({ data }: NodeProps<LNode>) {
  return (
    <div className="rounded-2xl border border-dashed border-input/60 bg-muted/25" style={{ width: data.width, height: data.height }}>
      <span className="absolute top-2.5 left-4 text-xs font-medium text-muted-foreground">{data.label}</span>
    </div>
  );
});

const nodeTypes = { arch: ArchNode, lane: LaneNode };

export const ARCH_NODES: (ArchNodeInfo & { icon: AppIcon; tone: AgentTone | null; x: number; y: number; workshop?: boolean })[] = [
  { id: "dev", title: "Developer", subtitle: "you, at the workshop", icon: Code2, tone: null, x: 0, y: 40, body: "Writes a tool as data: a parameterised SQL query or a curated factual answer. No Python, no redeploy." },
  { id: "ui", title: "Tools registration UI", subtitle: "this app · /tools", icon: LayoutPanelLeft, tone: null, x: 270, y: 40, body: "Form with a live params editor, schema browser and test run. Shows the exact function declaration the LLM will see before you save.", link: { to: "/tools/new", label: "Register a tool" } },
  { id: "registry", title: "tools.tools", subtitle: "registry table (Postgres)", icon: Table2, tone: null, x: 540, y: 40, body: "One row per tool: name, agent, type, description, SQL or answer, typed params. updated_at drives hot reload.", link: { to: "/schema/tools", label: "See the registry schema" } },
  { id: "factory", title: "ADK wraps as tools", subtitle: "rows → FunctionTool", icon: Wand2, tone: null, x: 810, y: 40, body: "A toolset per agent turns each enabled row into a typed ADK FunctionTool (signature + docstring from the row). It re-checks the registry every question, so new tools work without a restart." },
  { id: "finance_agent", title: "Finance agent", subtitle: "GL, P&L, budgets, FX", icon: TONE_ICON.finance, tone: "finance", x: 810, y: 200, body: "Specialist LlmAgent. Its tools may only read the finance schema, as the read-only agent_ro role." },
  { id: "trading_agent", title: "Trading agent", subtitle: "clients, trades, prices", icon: TONE_ICON.trading, tone: "trading", x: 810, y: 330, body: "Specialist LlmAgent. Its tools may only read the trading schema, as the read-only agent_ro role." },
  { id: "news_agent", title: "News agent", subtitle: "live market headlines", icon: TONE_ICON.news, tone: "news", x: 810, y: 460, body: "Specialist LlmAgent whose tools come from an MCP server (ADK's McpToolset). It has no Nimbus data, only real-world headlines. If the server is down, it says news is unavailable instead of failing the question." },
  { id: "marketing_agent", title: "Marketing agent", subtitle: "campaigns, sign-ups", icon: TONE_ICON.marketing, tone: "marketing", x: 810, y: 590, workshop: true, body: "Specialist LlmAgent with plain Python function tools that read the marketing schema. You build it in the workshop; it appears here once the orchestrator knows about it." },
  { id: "finance_ds", title: "finance schema", subtitle: "synthetic ledger", icon: Database, tone: null, x: 1080, y: 200, body: "Entities, chart of accounts, FX rates, GL entries and budgets for the fictional Nimbus Markets.", link: { to: "/schema/finance", label: "Browse the finance schema" } },
  { id: "trading_ds", title: "trading schema", subtitle: "synthetic trades", icon: Database, tone: null, x: 1080, y: 330, body: "Clients, instruments, trades and daily prices. Commission reconciles with the finance GL.", link: { to: "/schema/trading", label: "Browse the trading schema" } },
  { id: "news_ds", title: "Internet (RSS)", subtitle: "via the news MCP server", icon: Globe, tone: null, x: 1080, y: 460, body: "A small MCP server in its own container. It polls Google News RSS feeds every few minutes and offers latest_headlines, search_news and list_feeds as tools." },
  { id: "marketing_ds", title: "marketing schema", subtitle: "synthetic campaigns", icon: Database, tone: null, x: 1080, y: 590, body: "Campaigns, daily spend and sign-ups. Campaign spend reconciles with the finance GL; sign-ups point at trading clients.", link: { to: "/schema/marketing", label: "Browse the marketing schema" } },
  { id: "orchestrator", title: "Orchestrator", subtitle: "routes to specialists", icon: TONE_ICON.orchestrator, tone: "orchestrator", x: 540, y: 330, body: "Sees each specialist as a function (AgentTool). The LLM picks which to call: several at once when they're independent (parallel), one after another when one answer feeds the next." },
  { id: "main_agent", title: "Main agent", subtitle: "persona · final answer", icon: TONE_ICON.main, tone: "main", x: 270, y: 330, body: "The root agent users talk to. Handles small talk itself, sends data questions to the orchestrator, and writes the final answer.", link: { to: "/chat", label: "Open the chat" } },
  { id: "users", title: "Users", subtitle: "ask in plain English", icon: Users, tone: null, x: 0, y: 330, body: "Chat on the Chat page and watch the live route panel light up the agents and tools that answer.", link: { to: "/chat", label: "Ask a question" } },
];

type Route = "trunk" | "lane";

const E: [string, string, string?, { sh?: string; th?: string; dashed?: boolean; tone?: AgentTone; both?: boolean; route?: Route }?][] = [
  ["dev", "ui", "registers"],
  ["ui", "registry", "test + save"],
  ["registry", "factory", "hot reload"],
  ["factory", "finance_agent", "", { sh: "bottom", th: "top", dashed: true }],
  ["factory", "trading_agent", "", { sh: "bottom", th: "upper", dashed: true, route: "lane" }],
  ["finance_agent", "finance_ds", "SQL", { tone: "finance" }],
  ["trading_agent", "trading_ds", "SQL", { tone: "trading" }],
  ["news_agent", "news_ds", "MCP", { tone: "news" }],
  ["marketing_agent", "marketing_ds", "Python", { tone: "marketing" }],
  ["users", "main_agent", "", { both: true }],
  ["main_agent", "orchestrator", "AgentTool", { tone: "orchestrator" }],
  ["orchestrator", "finance_agent", "", { tone: "finance", route: "trunk" }],
  ["orchestrator", "trading_agent", "", { tone: "trading" }],
  ["orchestrator", "news_agent", "", { tone: "news", route: "trunk" }],
  ["orchestrator", "marketing_agent", "", { tone: "marketing", route: "trunk" }],
];

/**
 * Hand-routed edges, so lines that share the space left of the agents never overlap.
 * trunk: the orchestrator's fan-out, turning just right of the orchestrator.
 * lane: the dashed ADK line, dropping into the gap between the two lanes, then down its own
 * column into the agent's upper handle, clear of the trunk and the orchestrator's line.
 */
const ElbowEdge = memo(function ElbowEdge({ id, sourceX, sourceY, targetX, targetY, data, style, markerEnd }: EdgeProps<Edge<{ route: Route }>>) {
  const points: [number, number][] =
    data?.route === "lane"
      ? [[sourceX, sourceY], [sourceX, sourceY + 40], [targetX - 14, sourceY + 40], [targetX - 14, targetY], [targetX, targetY]]
      : [[sourceX, sourceY], [sourceX + 18, sourceY], [sourceX + 18, targetY], [targetX, targetY]];
  return <BaseEdge id={id} path={roundedPath(points)} style={style} markerEnd={markerEnd} />;
});

const edgeTypes = { elbow: ElbowEdge };

/** Workshop nodes that /api/graph doesn't list yet (all of them until it answers). */
export function pendingNodes(graph: Graph | undefined): string[] {
  return ARCH_NODES.filter((n) => n.workshop && !graph?.agents.some((a) => a.id === n.id)).map((n) => n.id);
}

function edgeOpacity(s: string, t: string, selected: string | null, pending: boolean) {
  const base = pending ? 0.6 : 1;
  return selected && selected !== s && selected !== t ? base * 0.35 : base;
}

interface Props {
  selected: string | null;
  onSelect: (id: string) => void;
  pending: string[];
}

function Inner({ selected, onSelect, pending }: Props) {
  const { resolved } = useTheme();
  const wrapRef = useAutoFit("arch", 0.04);
  const { nodes: nextNodes, edges } = useMemo(() => {
    const lanes: LNode[] = [
      { id: "lane-build", type: "lane", position: { x: -20, y: 0 }, data: { label: "Build time", width: 1070, height: 124 }, selectable: false, draggable: false, zIndex: -1 },
      { id: "lane-run", type: "lane", position: { x: -20, y: 156 }, data: { label: "Run time", width: 1330, height: 510 }, selectable: false, draggable: false, zIndex: -1 },
    ];
    const nodes: (ANode | LNode)[] = [
      ...lanes,
      ...ARCH_NODES.map((n) => ({ id: n.id, type: "arch" as const, position: { x: n.x, y: n.y }, data: { info: n, icon: n.icon, tone: n.tone, selected: selected === n.id, pending: pending.includes(n.id), onSelect }, draggable: false })),
    ];
    const edges: Edge[] = E.map(([s, t, label, o]) => {
      const unbuilt = pending.includes(s) || pending.includes(t);
      const color = o?.tone && !unbuilt ? toneColor(o.tone) : "hsl(var(--muted-foreground))";
      return {
        id: `${s}-${t}`,
        source: s,
        target: t,
        sourceHandle: o?.sh ?? null,
        targetHandle: o?.th ?? null,
        type: o?.route ? "elbow" : "smoothstep",
        data: o?.route ? { route: o.route } : undefined,
        label: label || undefined,
        labelStyle: { fontSize: 11, fontWeight: 500, fill: "hsl(var(--muted-foreground))" },
        labelBgStyle: { fill: "hsl(var(--card))" },
        labelBgPadding: [6, 3] as [number, number],
        labelBgBorderRadius: 6,
        animated: !!o?.dashed,
        style: { stroke: color, strokeWidth: 1.5, strokeDasharray: unbuilt ? "6 5" : undefined, opacity: edgeOpacity(s, t, selected, unbuilt) },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
        markerStart: o?.both ? { type: MarkerType.ArrowClosed, color, width: 16, height: 16 } : undefined,
        selectable: false,
      };
    });
    return { nodes, edges };
  }, [selected, onSelect, pending]);

  const [nodes, onNodesChange] = useSyncedNodes<ANode | LNode>(nextNodes);
  return (
    <div ref={wrapRef} className="h-full w-full">
    <ReactFlow nodes={nodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} colorMode={resolved} fitView fitViewOptions={{ padding: 0.06 }} minZoom={0.2} maxZoom={1.4} nodesConnectable={false} elementsSelectable={false} zoomOnScroll={false} panOnScroll preventScrolling={false}>
      <Controls showInteractive={false} position="top-right" />
    </ReactFlow>
    </div>
  );
}

export function ArchitectureGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
