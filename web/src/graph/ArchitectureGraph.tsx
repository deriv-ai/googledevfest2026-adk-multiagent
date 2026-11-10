import { memo, useMemo } from "react";
import { Controls, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { Bot, Code2, Database, Globe, LayoutPanelLeft, Network, Route, Sparkles, Table2, Users, Wand2, type LucideIcon } from "lucide-react";
import { toneColor, type AgentTone } from "@/lib/agents";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
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
  icon: LucideIcon;
  tone: AgentTone | null;
  selected: boolean;
  onSelect: (id: string) => void;
}
type ANode = Node<ArchData, "arch">;
interface LaneData extends Record<string, unknown> {
  label: string;
  width: number;
  height: number;
}
type LNode = Node<LaneData, "lane">;

const ArchNode = memo(function ArchNode({ data }: NodeProps<ANode>) {
  const { info, icon: Icon, tone, selected, onSelect } = data;
  return (
    <button
      type="button"
      onClick={() => onSelect(info.id)}
      className={cn("relative flex w-[210px] items-center gap-3 rounded-xl border bg-card px-3 py-2.5 text-left transition-[box-shadow,border-color,transform] duration-150 hover:-translate-y-px", selected ? "border-2" : "border-border")}
      style={{
        borderColor: selected ? (tone ? toneColor(tone) : "hsl(var(--foreground))") : undefined,
        boxShadow: selected ? `0 10px 28px -12px ${tone ? toneColor(tone, 0.7) : "rgb(0 0 0 / .35)"}` : "0 1px 3px rgb(0 0 0 / .08)",
      }}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="target" id="top" position={Position.Top} />
      <span
        className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg"
        style={tone ? { background: toneColor(tone), color: "white" } : { background: "hsl(var(--muted))", color: "hsl(var(--foreground))" }}
      >
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[14px] leading-tight font-semibold">{info.title}</span>
        <span className="block truncate text-[12px] text-muted-foreground">{info.subtitle}</span>
      </span>
      <Handle type="source" position={Position.Right} />
      <Handle type="source" id="bottom" position={Position.Bottom} />
    </button>
  );
});

const LaneNode = memo(function LaneNode({ data }: NodeProps<LNode>) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-muted/30" style={{ width: data.width, height: data.height }}>
      <span className="absolute top-2.5 left-4 text-[12px] font-semibold tracking-wide text-muted-foreground uppercase">{data.label}</span>
    </div>
  );
});

const nodeTypes = { arch: ArchNode, lane: LaneNode };

export const ARCH_NODES: (ArchNodeInfo & { icon: LucideIcon; tone: AgentTone | null; x: number; y: number })[] = [
  { id: "dev", title: "Developer", subtitle: "you, at the workshop", icon: Code2, tone: null, x: 0, y: 40, body: "Writes a tool as data: a parameterised SQL query or a curated factual answer. No Python, no redeploy." },
  { id: "ui", title: "Tools registration UI", subtitle: "this app · /tools", icon: LayoutPanelLeft, tone: null, x: 270, y: 40, body: "Form with a live params editor, schema browser and test run. Shows the exact function declaration the LLM will see before you save.", link: { to: "/tools/new", label: "Register a tool" } },
  { id: "registry", title: "tools.tools", subtitle: "registry table (Postgres)", icon: Table2, tone: null, x: 540, y: 40, body: "One row per tool: name, agent, type, description, SQL or answer, typed params. updated_at drives hot reload.", link: { to: "/schema/tools", label: "See the registry schema" } },
  { id: "factory", title: "ADK wraps as tools", subtitle: "rows → FunctionTool", icon: Wand2, tone: null, x: 810, y: 40, body: "A toolset per agent turns each enabled row into a typed ADK FunctionTool (signature + docstring from the row). It re-checks the registry every question, so new tools work without a restart." },
  { id: "finance_agent", title: "Finance agent", subtitle: "GL, P&L, budgets, FX", icon: Bot, tone: "finance", x: 810, y: 200, body: "Specialist LlmAgent. Its tools may only read the finance schema, as the read-only agent_ro role." },
  { id: "trading_agent", title: "Trading agent", subtitle: "clients, trades, prices", icon: Bot, tone: "trading", x: 810, y: 330, body: "Specialist LlmAgent. Its tools may only read the trading schema, as the read-only agent_ro role." },
  { id: "news_agent", title: "News agent", subtitle: "market headlines", icon: Globe, tone: "news", x: 810, y: 460, body: "Specialist LlmAgent with an MCP toolset: latest_headlines, search_news, list_feeds." },
  { id: "finance_ds", title: "finance schema", subtitle: "synthetic ledger", icon: Database, tone: null, x: 1080, y: 200, body: "Entities, chart of accounts, FX rates, GL entries and budgets for the fictional Nimbus Markets.", link: { to: "/schema/finance", label: "Browse the finance schema" } },
  { id: "trading_ds", title: "trading schema", subtitle: "synthetic trades", icon: Database, tone: null, x: 1080, y: 330, body: "Clients, instruments, trades and daily prices. Commission reconciles with the finance GL.", link: { to: "/schema/trading", label: "Browse the trading schema" } },
  { id: "mcp", title: "news-mcp", subtitle: "FastMCP server :8001", icon: Network, tone: null, x: 1080, y: 460, body: "Our own MCP server. A background listener polls free RSS feeds into a rolling buffer and serves them over streamable HTTP." },
  { id: "internet", title: "Internet", subtitle: "public RSS feeds", icon: Globe, tone: null, x: 1080, y: 580, body: "The only live data in the demo: real headlines. Every price and trade is synthetic." },
  { id: "orchestrator", title: "Orchestrator", subtitle: "routes to specialists", icon: Route, tone: "orchestrator", x: 540, y: 330, body: "Sees each specialist as a function (AgentTool). The LLM picks which to call: several at once when they're independent (parallel), one after another when one answer feeds the next." },
  { id: "main_agent", title: "Main agent", subtitle: "persona · final answer", icon: Sparkles, tone: "main", x: 270, y: 330, body: "The root agent users talk to. Handles small talk itself, sends data and news questions to the orchestrator, and writes the final answer.", link: { to: "/chat", label: "Open the chat" } },
  { id: "users", title: "Users", subtitle: "ask in plain English", icon: Users, tone: null, x: 0, y: 330, body: "Chat on the Chat page and watch the live route panel light up the agents and tools that answer.", link: { to: "/chat", label: "Ask a question" } },
];

const E: [string, string, string?, { sh?: string; th?: string; dashed?: boolean; tone?: AgentTone; both?: boolean }?][] = [
  ["dev", "ui", "registers"],
  ["ui", "registry", "test + save"],
  ["registry", "factory", "hot reload"],
  ["factory", "finance_agent", "", { sh: "bottom", th: "top", dashed: true }],
  ["factory", "trading_agent", "", { sh: "bottom", dashed: true }],
  ["finance_agent", "finance_ds", "SQL", { tone: "finance" }],
  ["trading_agent", "trading_ds", "SQL", { tone: "trading" }],
  ["news_agent", "mcp", "MCP", { tone: "news" }],
  ["mcp", "internet", "", { sh: "bottom", th: "top", tone: "news" }],
  ["users", "main_agent", "", { both: true }],
  ["main_agent", "orchestrator", "AgentTool", { tone: "orchestrator" }],
  ["orchestrator", "finance_agent", "", { tone: "finance" }],
  ["orchestrator", "trading_agent", "", { tone: "trading" }],
  ["orchestrator", "news_agent", "", { tone: "news" }],
];

function Inner({ selected, onSelect }: { selected: string | null; onSelect: (id: string) => void }) {
  const { resolved } = useTheme();
  const wrapRef = useAutoFit("arch", 0.04);
  const { nodes: nextNodes, edges } = useMemo(() => {
    const lanes: LNode[] = [
      { id: "lane-build", type: "lane", position: { x: -20, y: 0 }, data: { label: "Build time", width: 1070, height: 124 }, selectable: false, draggable: false, zIndex: -1 },
      { id: "lane-run", type: "lane", position: { x: -20, y: 156 }, data: { label: "Run time", width: 1330, height: 500 }, selectable: false, draggable: false, zIndex: -1 },
    ];
    const nodes: (ANode | LNode)[] = [
      ...lanes,
      ...ARCH_NODES.map((n) => ({ id: n.id, type: "arch" as const, position: { x: n.x, y: n.y }, data: { info: n, icon: n.icon, tone: n.tone, selected: selected === n.id, onSelect }, draggable: false })),
    ];
    const edges: Edge[] = E.map(([s, t, label, o]) => {
      const color = o?.tone ? toneColor(o.tone) : "hsl(var(--muted-foreground))";
      return {
        id: `${s}-${t}`,
        source: s,
        target: t,
        sourceHandle: o?.sh ?? null,
        targetHandle: o?.th ?? null,
        type: "smoothstep",
        label: label || undefined,
        labelStyle: { fontSize: 11.5, fontWeight: 600, fill: "hsl(var(--muted-foreground))" },
        labelBgStyle: { fill: "hsl(var(--card))" },
        labelBgPadding: [6, 3] as [number, number],
        labelBgBorderRadius: 6,
        animated: !!o?.dashed,
        style: { stroke: color, strokeWidth: 1.75, opacity: selected && selected !== s && selected !== t ? 0.35 : 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
        markerStart: o?.both ? { type: MarkerType.ArrowClosed, color, width: 16, height: 16 } : undefined,
        selectable: false,
      };
    });
    return { nodes, edges };
  }, [selected, onSelect]);

  const [nodes, onNodesChange] = useSyncedNodes<ANode | LNode>(nextNodes);
  return (
    <div ref={wrapRef} className="h-full w-full">
    <ReactFlow nodes={nodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} colorMode={resolved} fitView fitViewOptions={{ padding: 0.06 }} minZoom={0.3} maxZoom={1.4} nodesConnectable={false} elementsSelectable={false} zoomOnScroll={false} panOnScroll preventScrolling={false}>
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
    </div>
  );
}

export function ArchitectureGraph(props: { selected: string | null; onSelect: (id: string) => void }) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
