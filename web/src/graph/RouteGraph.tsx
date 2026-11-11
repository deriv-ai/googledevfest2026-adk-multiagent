import { memo, useMemo } from "react";
import {
  BaseEdge,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { AlertCircle, Check, Database, User } from "lucide-react";
import type { Graph } from "@/api/types";
import { KIND_ICON, KIND_LABEL, TONE_ICON } from "@/components/Badges";
import { toneColor } from "@/lib/agents";
import { formatMs } from "@/lib/format";
import { layoutRoute, type RouteEdgeData, type RouteNodeData } from "@/lib/routeLayout";
import type { RouteState } from "@/lib/routeGraph";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { useAutoFit, useSyncedNodes } from "./useAutoFit";

type RNode = Node<RouteNodeData>;
type REdge = Edge<RouteEdgeData>;

// ---- pieces ------------------------------------------------------------------------------

function StepBadges({ steps, tone }: { steps: number[]; tone: RouteNodeData["tone"] }) {
  if (!steps.length) return null;
  return (
    <div className="absolute -top-2.5 -right-2 flex gap-1">
      {steps.slice(-3).map((n) => (
        <span
          key={n}
          className="pop-in inline-flex size-6 items-center justify-center rounded-full font-mono text-[11px] font-semibold text-white shadow-[0_2px_6px_-1px_rgb(0_0_0/0.35)]"
          style={{ background: toneColor(tone) }}
          title={`Step ${n}`}
        >
          {n}
        </span>
      ))}
    </div>
  );
}

function StatusLine({ d }: { d: RouteNodeData }) {
  if (d.status === "error")
    return (
      <span className="inline-flex items-center gap-1 text-danger" title={d.error ?? undefined}>
        <AlertCircle className="size-3.5" aria-hidden /> {d.error ? "error" : "failed"}
      </span>
    );
  if (d.status === "active") return <span style={{ color: toneColor(d.tone) }}>working…</span>;
  if (d.status === "queued") return <span className="text-muted-foreground">called · starting</span>;
  if (d.status === "done")
    return (
      <span className="inline-flex items-center gap-1 text-success">
        <Check className="size-3.5" aria-hidden />
        {d.ms !== null ? formatMs(d.ms) : "done"}
        {typeof d.rowCount === "number" ? <span className="text-muted-foreground">· {d.rowCount} rows</span> : null}
      </span>
    );
  return null;
}

function nodeChrome(d: RouteNodeData) {
  const tone = toneColor(d.tone);
  const lit = d.status !== "idle";
  return {
    className: cn(
      "relative rounded-xl border bg-card transition-[opacity,border-color,outline-color,box-shadow] duration-300 ease-out",
      d.status === "active" && "node-active",
      d.status === "error" && "border-danger!",
      d.dim && "opacity-40",
    ),
    style: {
      ["--tone" as string]: `var(--agent-${d.tone})`,
      // Lit nodes get a 2px edge from border + outline, so the content never shifts by a pixel.
      borderColor: lit ? tone : undefined,
      outline: `1px solid ${d.status === "error" ? "hsl(var(--danger))" : lit ? tone : "transparent"}`,
      outlineOffset: 0,
      boxShadow: d.status === "done" ? `0 4px 14px -8px ${toneColor(d.tone, 0.45)}` : d.status === "idle" ? "var(--elev-1)" : undefined,
    } as React.CSSProperties,
  };
}

// ---- nodes ------------------------------------------------------------------------------

const UserNode = memo(function UserNode({ data }: NodeProps<RNode>) {
  return (
    <div
      className={cn("flex h-11 w-[140px] items-center justify-center gap-2 rounded-full border bg-card text-sm font-semibold shadow-xs outline-1 transition-[border-color,outline-color] duration-300 ease-out", data.status === "active" ? "border-foreground outline-foreground" : "border-border outline-transparent")}
    >
      <User className="size-4" aria-hidden /> User
      <Handle type="source" position={Position.Right} />
    </div>
  );
});

const AgentNode = memo(function AgentNode({ data }: NodeProps<RNode>) {
  const Icon = TONE_ICON[data.tone];
  const chrome = nodeChrome(data);
  return (
    <div className={cn(chrome.className, "w-[260px] px-3.5 py-3")} style={chrome.style}>
      <Handle type="target" id="top" position={Position.Top} />
      <Handle type="target" id="left" position={Position.Left} />
      <Handle type="source" id="right" position={Position.Right} />
      <div className="flex items-center gap-3">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-white" style={{ background: toneColor(data.tone) }}>
          <Icon className="size-[18px]" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] leading-tight font-semibold">{data.label}</div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">{data.status === "idle" ? data.sublabel : <StatusLine d={data} />}</div>
        </div>
      </div>
      <StepBadges steps={data.steps} tone={data.tone} />
      <Handle type="source" id="bottom" position={Position.Bottom} />
      <Handle type="source" id="rail" position={Position.Bottom} style={{ left: 14 }} />
    </div>
  );
});

function breakable(name: string) {
  const parts = name.split("_");
  return parts.map((p, i) => (
    <span key={i}>
      {p}
      {i < parts.length - 1 ? (
        <>
          _<wbr />
        </>
      ) : null}
    </span>
  ));
}

const ToolNode = memo(function ToolNode({ data }: NodeProps<RNode>) {
  const kind = data.toolKind === "factual" || data.toolKind === "function" ? data.toolKind : "sql";
  const Icon = KIND_ICON[kind];
  const chrome = nodeChrome(data);
  return (
    <div className={cn(chrome.className, "w-[232px] px-2.5 py-2")} style={chrome.style} title={data.title ?? data.label}>
      <Handle type="target" position={Position.Left} />
      <div className="flex items-start gap-2">
        <span
          className="mt-px inline-flex size-6 shrink-0 items-center justify-center rounded-md"
          style={{ color: toneColor(data.tone), background: toneColor(data.tone, 0.12) }}
          aria-label={`${KIND_LABEL[kind]} tool`}
        >
          <Icon className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-mono text-xs leading-snug font-medium [overflow-wrap:anywhere]">{breakable(data.label)}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {data.status === "idle" ? <span className="font-mono tracking-wide uppercase">{KIND_LABEL[kind]}</span> : <StatusLine d={data} />}
          </div>
        </div>
      </div>
      <StepBadges steps={data.steps} tone={data.tone} />
      <Handle type="source" id="ds" position={Position.Right} />
    </div>
  );
});

const DatasourceNode = memo(function DatasourceNode({ data }: NodeProps<RNode>) {
  const chrome = nodeChrome(data);
  return (
    <div className={cn(chrome.className, "w-[232px] border-dashed px-3 py-2.5")} style={{ ...chrome.style, borderStyle: data.status === "idle" ? "dashed" : "solid" }}>
      <Handle type="target" id="side" position={Position.Right} />
      <div className="flex items-center gap-2.5">
        <Database className="size-4 shrink-0" style={{ color: toneColor(data.tone) }} aria-hidden />
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold">{data.label}</div>
          <div className="truncate text-[11px] text-muted-foreground">{data.status === "active" ? "reading…" : data.sublabel}</div>
        </div>
      </div>
    </div>
  );
});

// ---- edge ---------------------------------------------------------------------------------

const FlowEdge = memo(function FlowEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data }: EdgeProps<REdge>) {
  const sameSide = sourcePosition === Position.Right && targetPosition === Position.Right;
  const [path] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, borderRadius: 12, offset: sameSide ? 18 : 16 });
  const st = data?.status ?? "idle";
  const color = st === "error" ? "hsl(var(--danger))" : st === "idle" ? "hsl(var(--input))" : toneColor(data?.tone ?? "other");
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: color,
          strokeWidth: st === "active" ? 2.75 : st === "idle" ? 1.25 : 2,
          strokeDasharray: data?.dashed ? "4 4" : undefined,
          opacity: data?.dim ? 0.3 : st === "done" ? 0.85 : 1,
          transition: "stroke 300ms var(--curve-out), opacity 300ms var(--curve-out), stroke-width 300ms var(--curve-out)",
        }}
      />
      {st === "active" ? (
        <circle className="edge-dot" r={4.5} fill={color}>
          <animateMotion dur="1.1s" repeatCount="indefinite" path={path} />
        </circle>
      ) : null}
    </>
  );
});

const nodeTypes = { user: UserNode, agent: AgentNode, tool: ToolNode, datasource: DatasourceNode };
const edgeTypes = { flow: FlowEdge };

// ---- graph --------------------------------------------------------------------------------

function Inner({ graph, state, className }: { graph: Graph; state: RouteState; className?: string }) {
  const { resolved } = useTheme();
  const layout = useMemo(() => layoutRoute(graph, state), [graph, state]);
  const nextNodes: RNode[] = useMemo(
    () => layout.nodes.map((n) => ({ id: n.id, type: n.type, position: n.position, data: n.data, draggable: false, selectable: false, connectable: false })),
    [layout],
  );
  const edges: REdge[] = useMemo(
    () =>
      layout.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
        targetHandle: e.targetHandle ?? null,
        type: "flow",
        data: e.data,
        zIndex: e.data.status === "active" ? 2 : e.data.status === "idle" ? 0 : 1,
        selectable: false,
      })),
    [layout],
  );
  // Refit when the topology changes (new tool nodes), not on every status tick.
  const [nodes, onNodesChange] = useSyncedNodes(nextNodes);
  const wrapRef = useAutoFit(layout.nodes.map((n) => n.id).join("|"));

  return (
    <div ref={wrapRef} className={className}>
    <ReactFlow
      nodes={nodes}
      onNodesChange={onNodesChange}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      colorMode={resolved}
      fitView
      fitViewOptions={{ padding: 0.06 }}
      minZoom={0.25}
      maxZoom={1.6}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnScroll
      zoomOnScroll={false}
      zoomOnPinch
      preventScrolling={false}
    >
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
    </div>
  );
}

export function RouteGraph(props: { graph: Graph; state: RouteState; className?: string }) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
