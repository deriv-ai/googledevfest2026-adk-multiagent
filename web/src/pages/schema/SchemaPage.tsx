import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronDown, KeyRound, Link2, Rows3, Table2 } from "lucide-react";
import { useSample, useSchema } from "@/api/hooks";
import type { SchemaName, SchemaTable } from "@/api/types";
import { CopyButton } from "@/components/CopyButton";
import { ResultTable } from "@/components/ResultTable";
import { ErrorState, PageHeader } from "@/components/States";
import { Button, Panel, Segmented, Skeleton } from "@/components/ui";
import { ErDiagram, shortType } from "@/graph/ErDiagram";
import { toneColor, type AgentTone } from "@/lib/agents";
import { formatCount } from "@/lib/format";
import { selectSnippet } from "@/lib/sqlSnippet";
import { cn } from "@/lib/utils";

const SCHEMAS: { value: SchemaName; label: string; tone: AgentTone; who: string }[] = [
  { value: "finance", label: "finance", tone: "finance", who: "Read by the finance agent's tools" },
  { value: "trading", label: "trading", tone: "trading", who: "Read by the trading agent's tools" },
  { value: "tools", label: "tools", tone: "main", who: "The tool registry itself (not readable by agents)" },
];

export default function SchemaPage() {
  const params = useParams();
  const navigate = useNavigate();
  const active = (SCHEMAS.find((s) => s.value === params.schema)?.value ?? "finance") as SchemaName;
  const meta = SCHEMAS.find((s) => s.value === active)!;
  const { data, isLoading, isError, error, refetch } = useSchema(active);

  const jump = useCallback((table: string) => {
    document.getElementById(`table-${table}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-8 lg:px-10">
      <PageHeader
        title="Data schema"
        description="One Postgres database, three schemas. Every description below comes live from the database's COMMENT ON, so it can't drift. Use it to write your own tools."
      />

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Segmented
          value={active}
          onChange={(v) => navigate(`/schema/${v}`)}
          options={SCHEMAS.map((s) => ({
            value: s.value,
            label: (
              <>
                <span className="size-2 rounded-full" style={{ background: toneColor(s.tone) }} aria-hidden />
                <span className="font-mono">{s.label}</span>
              </>
            ),
          }))}
        />
        <span className="text-[14px] text-muted-foreground">{meta.who}</span>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-5 w-[28rem]" />
          <Skeleton className="h-[460px] w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      ) : isError || !data ? (
        <ErrorState error={error} onRetry={() => void refetch()} title={`Couldn't load the ${active} schema`} />
      ) : (
        <>
          {data.comment ? <p className="mb-4 max-w-[75ch] text-[15px]">{data.comment}</p> : null}

          <Panel className="relative mb-4 h-[480px] overflow-hidden">
            <ErDiagram schema={data} onSelect={jump} />
            <div className="pointer-events-none absolute bottom-3 left-3 flex gap-3 rounded-lg bg-card/90 px-2.5 py-1.5 text-[12px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <KeyRound className="size-3 text-warning" aria-hidden /> primary key
              </span>
              <span className="inline-flex items-center gap-1">
                <Link2 className="size-3 text-link" aria-hidden /> foreign key
              </span>
              <span>click a table to jump to its details</span>
            </div>
          </Panel>

          <nav aria-label="Tables" className="mb-8 flex flex-wrap gap-2">
            {data.tables.map((t) => (
              <button key={t.name} type="button" onClick={() => jump(t.name)} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 font-mono text-[13px] hover:bg-muted">
                <Table2 className="size-3.5 text-muted-foreground" aria-hidden />
                {t.name}
              </button>
            ))}
          </nav>

          <div className="space-y-6">
            {data.tables.map((t) => (
              <TableCard key={t.name} schema={active} table={t} onJump={jump} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TableCard({ schema, table, onJump }: { schema: SchemaName; table: SchemaTable; onJump: (t: string) => void }) {
  const [showSample, setShowSample] = useState(false);
  const sample = useSample(schema, table.name, showSample);
  const snippet = selectSnippet(schema, table);

  return (
    <Panel id={`table-${table.name}`} className="scroll-mt-6 overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 pb-3">
        <div className="min-w-0">
          <h2 className="font-mono text-[18px] font-semibold">
            <span className="text-muted-foreground">{schema}.</span>
            {table.name}
          </h2>
          {table.comment ? <p className="mt-1 max-w-[75ch] text-[14.5px] text-foreground/85">{table.comment}</p> : null}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[13px] text-muted-foreground tabular-nums">{formatCount(table.row_count)} rows</span>
          <CopyButton text={snippet} label="Copy SELECT" toastMessage={`SELECT for ${schema}.${table.name} copied`} />
        </div>
      </div>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full text-left text-[14px]">
          <thead className="bg-muted/60 text-[12.5px] text-muted-foreground">
            <tr>
              <th className="w-[22%] px-5 py-2 font-medium">Column</th>
              <th className="w-[16%] px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Null</th>
              <th className="px-3 py-2 font-medium">Key</th>
              <th className="px-3 py-2 pr-5 font-medium">Description</th>
            </tr>
          </thead>
          <tbody>
            {table.columns.map((c) => (
              <tr key={c.name} className="border-t border-border align-top">
                <td className={cn("px-5 py-2 font-mono text-[13.5px]", c.pk && "font-semibold")}>{c.name}</td>
                <td className="px-3 py-2 font-mono text-[12.5px] whitespace-nowrap text-muted-foreground">{shortType(c.type)}</td>
                <td className="px-3 py-2 text-[13px] text-muted-foreground">{c.nullable ? "yes" : "no"}</td>
                <td className="px-3 py-2 text-[13px] whitespace-nowrap">
                  {c.pk ? (
                    <span className="inline-flex items-center gap-1 font-medium text-warning">
                      <KeyRound className="size-3.5" aria-hidden /> PK
                    </span>
                  ) : null}
                  {c.fk ? (
                    <button type="button" onClick={() => onJump(c.fk!.table)} className={cn("inline-flex items-center gap-1 font-mono text-[12.5px] text-link hover:underline", c.pk && "ml-2")} title={`Go to ${c.fk.table}`}>
                      <Link2 className="size-3.5" aria-hidden /> {c.fk.table}.{c.fk.column}
                    </button>
                  ) : null}
                  {!c.pk && !c.fk ? <span className="text-muted-foreground">–</span> : null}
                </td>
                <td className="max-w-[48ch] px-3 py-2 pr-5 text-[13.5px]">{c.comment ?? <span className="text-muted-foreground">No comment</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-border px-5 py-3">
        <Button size="sm" variant="ghost" onClick={() => setShowSample((s) => !s)} aria-expanded={showSample}>
          <Rows3 className="size-4" aria-hidden /> {showSample ? "Hide sample rows" : "Show 5 sample rows"}
          <ChevronDown className={cn("size-3.5 transition-transform", showSample && "rotate-180")} aria-hidden />
        </Button>
        {showSample ? (
          <div className="mt-3">
            {sample.isLoading ? (
              <Skeleton className="h-36 w-full rounded-lg" />
            ) : sample.isError ? (
              <ErrorState error={sample.error} onRetry={() => void sample.refetch()} />
            ) : sample.data ? (
              <ResultTable columns={sample.data.columns} rows={sample.data.rows} compact maxHeight="18rem" />
            ) : null}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
