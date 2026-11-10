import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, ExternalLink, KeyRound, Link2, Table2 } from "lucide-react";
import { useSchema } from "@/api/hooks";
import type { SchemaName, SchemaTable } from "@/api/types";
import { ErrorState } from "@/components/States";
import { Skeleton } from "@/components/ui";
import { formatCount } from "@/lib/format";
import { selectSnippet } from "@/lib/sqlSnippet";
import { cn } from "@/lib/utils";

export function SchemaBrowser({ schema, onInsert }: { schema: SchemaName; onInsert: (text: string) => void }) {
  const { data, isLoading, isError, error, refetch } = useSchema(schema);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  return (
    <div className="flex min-h-0 flex-col">
      <div className="flex items-baseline justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <h3 className="text-[14.5px] font-semibold">
            <span className="font-mono">{schema}</span> schema
          </h3>
          <p className="text-[12.5px] text-muted-foreground">Click a table or column to insert it at the cursor.</p>
        </div>
        <Link to={`/schema/${schema}`} target="_blank" className="inline-flex shrink-0 items-center gap-1 text-[12.5px] text-link hover:underline">
          Full reference <ExternalLink className="size-3" aria-hidden />
        </Link>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState error={error} onRetry={() => void refetch()} className="m-2" />
        ) : (
          <ul className="space-y-0.5">
            {data?.tables.map((t) => (
              <TableItem key={t.name} schema={schema} table={t} open={!!open[t.name]} onToggle={() => setOpen((o) => ({ ...o, [t.name]: !o[t.name] }))} onInsert={onInsert} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function TableItem({ schema, table, open, onToggle, onInsert }: { schema: string; table: SchemaTable; open: boolean; onToggle: () => void; onInsert: (t: string) => void }) {
  return (
    <li>
      <div className="group flex items-center gap-1 rounded-md hover:bg-muted/60">
        <button type="button" onClick={onToggle} className="inline-flex size-8 shrink-0 items-center justify-center text-muted-foreground" aria-expanded={open} aria-label={`${open ? "Collapse" : "Expand"} ${table.name}`}>
          <ChevronRight className={cn("size-4 transition-transform", open && "rotate-90")} />
        </button>
        <button type="button" onClick={() => onInsert(`${schema}.${table.name}`)} className="flex min-w-0 flex-1 items-center gap-2 py-1.5 text-left" title={`Insert ${schema}.${table.name}`}>
          <Table2 className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          <span className="truncate font-mono text-[13.5px] font-medium">{table.name}</span>
          <span className="ml-auto pr-2 text-[11.5px] text-muted-foreground tabular-nums">{formatCount(table.row_count)} rows</span>
        </button>
      </div>
      {open ? (
        <div className="mb-2 ml-8 border-l border-border pl-3">
          {table.comment ? <p className="py-1 text-[12.5px] text-muted-foreground">{table.comment}</p> : null}
          <button type="button" onClick={() => onInsert(selectSnippet(schema, table))} className="mb-1 text-[12px] font-medium text-link hover:underline">
            Insert SELECT for this table
          </button>
          <ul>
            {table.columns.map((c) => (
              <li key={c.name}>
                <button type="button" onClick={() => onInsert(c.name)} className="flex w-full items-start gap-2 rounded px-1.5 py-1 text-left hover:bg-muted/60" title={c.comment ?? `Insert ${c.name}`}>
                  <span className="mt-0.5 inline-flex w-3.5 shrink-0 justify-center">
                    {c.pk ? <KeyRound className="size-3 text-warning" aria-label="primary key" /> : c.fk ? <Link2 className="size-3 text-link" aria-label="foreign key" /> : null}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-2">
                      <span className="font-mono text-[12.5px] font-medium">{c.name}</span>
                      <span className="truncate font-mono text-[11px] text-muted-foreground">{c.type}</span>
                    </span>
                    {c.comment ? <span className="block text-[11.5px] leading-snug text-muted-foreground">{c.comment}</span> : null}
                    {c.fk ? <span className="block font-mono text-[11px] text-link">→ {c.fk.table}.{c.fk.column}</span> : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </li>
  );
}
