import { memo, useMemo } from "react";
import { Background, BackgroundVariant, Controls, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { KeyRound, Link2 } from "lucide-react";
import type { SchemaDetail, SchemaTable } from "@/api/types";
import { formatCount } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { useAutoFit, useSyncedNodes } from "./useAutoFit";

interface TableData extends Record<string, unknown> {
  table: SchemaTable;
  schema: string;
  onSelect?: (table: string) => void;
}
type TNode = Node<TableData, "table">;

const NODE_W = 264;
const HEADER_H = 46;
const ROW_H = 26;

const TableNode = memo(function TableNode({ data }: NodeProps<TNode>) {
  const { table, onSelect } = data;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-md" style={{ width: NODE_W }}>
      <button type="button" onClick={() => onSelect?.(table.name)} className="flex h-[46px] w-full items-center justify-between gap-2 border-b border-border bg-muted/70 px-3 text-left transition-colors hover:bg-subtle" title={table.comment ?? undefined}>
        <span className="truncate font-mono text-[13px] font-semibold">{table.name}</span>
        <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">{formatCount(table.row_count)} rows</span>
      </button>
      <ul>
        {table.columns.map((c) => (
          <li key={c.name} className="relative flex h-[26px] items-center gap-2 px-3 text-xs" title={c.comment ?? undefined}>
            <Handle type="source" id={`l-${c.name}`} position={Position.Left} />
            <Handle type="target" id={`r-${c.name}`} position={Position.Right} />
            <span className="inline-flex w-3.5 shrink-0 justify-center">
              {c.pk ? <KeyRound className="size-3 text-warning" aria-label="primary key" /> : c.fk ? <Link2 className="size-3 text-link" aria-label="foreign key" /> : null}
            </span>
            <span className={c.pk ? "font-mono font-semibold" : "font-mono"}>{c.name}</span>
            <span className="ml-auto truncate pl-2 font-mono text-[11px] text-muted-foreground">{shortType(c.type)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
});

export function shortType(t: string): string {
  return t.replace("timestamp with time zone", "timestamptz").replace("character varying", "varchar").replace("character", "char");
}

const nodeTypes = { table: TableNode };

/**
 * Column layout: a table's level is 1 + the level of the tables it references
 * (dimensions on the left, facts on the right); tables stack within a level.
 */
export function layoutEr(schema: SchemaDetail): { positions: Record<string, { x: number; y: number }>; edges: { source: string; target: string; column: string; refColumn: string }[] } {
  const byName = new Map(schema.tables.map((t) => [t.name, t] as const));
  const level = new Map<string, number>();
  const visit = (name: string, stack: Set<string>): number => {
    if (level.has(name)) return level.get(name)!;
    if (stack.has(name)) return 0;
    stack.add(name);
    const t = byName.get(name);
    let lv = 0;
    for (const c of t?.columns ?? []) if (c.fk && c.fk.table !== name && byName.has(c.fk.table) && !c.fk.schema) lv = Math.max(lv, visit(c.fk.table, stack) + 1);
    stack.delete(name);
    level.set(name, lv);
    return lv;
  };
  for (const t of schema.tables) visit(t.name, new Set());
  const cols = new Map<number, SchemaTable[]>();
  for (const t of schema.tables) cols.set(level.get(t.name)!, [...(cols.get(level.get(t.name)!) ?? []), t]);
  const positions: Record<string, { x: number; y: number }> = {};
  for (const [lv, tables] of cols) {
    let y = 0;
    for (const t of tables) {
      positions[t.name] = { x: lv * (NODE_W + 120), y };
      y += HEADER_H + t.columns.length * ROW_H + 40;
    }
  }
  const edges = schema.tables.flatMap((t) =>
    t.columns.filter((c) => c.fk && byName.has(c.fk.table) && c.fk.table !== t.name && !c.fk.schema).map((c) => ({ source: t.name, target: c.fk!.table, column: c.name, refColumn: c.fk!.column })),
  );
  return { positions, edges };
}

function Inner({ schema, onSelect }: { schema: SchemaDetail; onSelect?: (t: string) => void }) {
  const { resolved } = useTheme();
  const wrapRef = useAutoFit(schema.name + schema.tables.length, 0.1);
  const { nodes: nextNodes, edges } = useMemo(() => {
    const { positions, edges: fk } = layoutEr(schema);
    const nodes: TNode[] = schema.tables.map((t) => ({ id: t.name, type: "table", position: positions[t.name]!, data: { table: t, schema: schema.name, onSelect }, draggable: true, selectable: false }));
    const edges: Edge[] = fk.map((e) => ({
      id: `${e.source}.${e.column}->${e.target}.${e.refColumn}`,
      source: e.source,
      sourceHandle: `l-${e.column}`,
      target: e.target,
      targetHandle: `r-${e.refColumn}`,
      type: "smoothstep",
      style: { stroke: "hsl(var(--link))", strokeWidth: 1.5, opacity: 0.75 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(var(--link))", width: 16, height: 16 },
      selectable: false,
    }));
    return { nodes, edges };
  }, [schema, onSelect]);

  const [nodes, onNodesChange] = useSyncedNodes<TNode>(nextNodes);
  return (
    <div ref={wrapRef} className="h-full w-full">
    <ReactFlow nodes={nodes} onNodesChange={onNodesChange} edges={edges} nodeTypes={nodeTypes} colorMode={resolved} fitView fitViewOptions={{ padding: 0.12 }} minZoom={0.2} maxZoom={1.5} nodesConnectable={false} zoomOnScroll={false} panOnScroll preventScrolling={false}>
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="hsl(var(--input))" />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
    </div>
  );
}

export function ErDiagram(props: { schema: SchemaDetail; onSelect?: (t: string) => void }) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
