import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, Trash2 } from "@/components/icons";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { useDeleteTool, useSetToolEnabled, useTool } from "@/api/hooks";
import type { ToolParam, ToolRun } from "@/api/types";
import { AgentBadge, ToolTypeBadge } from "@/components/Badges";
import { Markdown } from "@/components/Markdown";
import { SqlEditor } from "@/components/SqlEditor";
import { EmptyState, ErrorState } from "@/components/States";
import { Button, ConfirmDialog, Panel, Skeleton, Switch } from "@/components/ui";
import { formatMs, formatRelative, summarizeArgs } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ToolDetailPage() {
  const { name = "" } = useParams();
  const navigate = useNavigate();
  const { data: tool, isLoading, isError, error, refetch } = useTool(name);
  const toggle = useSetToolEnabled();
  const del = useDeleteTool();
  const [confirm, setConfirm] = useState(false);

  if (isLoading)
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-6 py-8 lg:px-10">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-9 w-96" />
        <Skeleton className="h-5 w-[32rem]" />
        <Skeleton className="mt-6 h-64 w-full rounded-xl" />
      </div>
    );
  if (isError || !tool)
    return (
      <div className="mx-auto max-w-5xl px-6 py-8 lg:px-10">
        <BackLink />
        {error instanceof ApiError && error.status === 404 ? (
          <EmptyState title={`No tool named “${name}”`} action={<Link to="/tools"><Button variant="primary">Back to tools</Button></Link>}>
            It may have been deleted or renamed.
          </EmptyState>
        ) : (
          <ErrorState error={error} onRetry={() => void refetch()} />
        )}
      </div>
    );

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 lg:px-10">
      <BackLink />
      <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <AgentBadge agent={tool.agent} />
            <ToolTypeBadge type={tool.tool_type} />
          </div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight break-all">{tool.name}</h1>
          <p className="mt-1 text-[15px] text-muted-foreground">{tool.title}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="mr-1 flex items-center gap-2 text-[13px] font-medium">
            <Switch
              checked={tool.enabled}
              label={tool.enabled ? "Disable tool" : "Enable tool"}
              disabled={toggle.isPending}
              onChange={(enabled) =>
                toggle.mutate(
                  { name: tool.name, enabled },
                  { onSuccess: () => toast.success(enabled ? "Enabled" : "Disabled"), onError: (e) => toast.error(e.message) },
                )
              }
            />
            {tool.enabled ? "Enabled" : "Disabled"}
          </label>
          <Link to={`/tools/${encodeURIComponent(tool.name)}/edit`}>
            <Button variant="outline">
              <Pencil className="size-4" aria-hidden /> Edit
            </Button>
          </Link>
          <Button variant="ghost" className="text-danger hover:bg-danger/10 hover:text-danger" onClick={() => setConfirm(true)}>
            <Trash2 className="size-4" aria-hidden /> Delete
          </Button>
        </div>
      </header>

      <div className="space-y-10">
        <Section title="Description" hint="This is what the LLM reads to decide when to call the tool.">
          <p className="max-w-[75ch] text-[15px] leading-relaxed whitespace-pre-wrap">{tool.description}</p>
        </Section>

        {tool.tool_type === "sql" ? (
          <>
            <Section title="SQL">
              <SqlEditor value={tool.sql ?? ""} readOnly minHeight="120px" />
            </Section>
            <Section title="Parameters" hint="Each parameter becomes a typed argument of the function.">
              <ParamsTable params={tool.params} />
            </Section>
          </>
        ) : (
          <Section title="Answer" hint={tool.source ? `Source: ${tool.source}` : undefined}>
            <Panel className="px-5 py-4">
              <Markdown>{tool.answer ?? ""}</Markdown>
            </Panel>
          </Section>
        )}

        <Section title="Recent runs" hint="Most recent first.">
          <RunsTable runs={tool.runs ?? []} />
        </Section>
      </div>

      <ConfirmDialog
        open={confirm}
        title={`Delete ${tool.name}?`}
        body={<>The {tool.agent} agent loses this tool on its next question. This can't be undone; disable it instead if you might want it back.</>}
        confirmLabel="Delete tool"
        busy={del.isPending}
        onClose={() => setConfirm(false)}
        onConfirm={() =>
          del.mutate(tool.name, {
            onSuccess: () => {
              toast.success(`Deleted ${tool.name}`);
              navigate("/tools");
            },
            onError: (e) => toast.error(`Couldn't delete: ${e.message}`),
          })
        }
      />
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/tools" className="group mb-6 inline-flex items-center gap-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground">
      <ArrowLeft className="size-3.5 transition-[translate] duration-200 ease-out group-hover:-translate-x-0.5" aria-hidden /> All tools
    </Link>
  );
}

export function Section({ title, hint, children, actions }: { title: string; hint?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function ParamsTable({ params }: { params: ToolParam[] }) {
  if (!params.length) return <p className="text-sm text-muted-foreground">No parameters: the function takes no arguments.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left text-[13px]">
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            {["Name", "Type", "Required", "Description", "Example", "Default", "Allowed"].map((h) => (
              <th key={h} className="px-3 py-2 font-medium whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {params.map((p) => (
            <tr key={p.name} className="border-t border-border align-top">
              <td className="px-3 py-2 font-mono font-medium">{p.name}</td>
              <td className="px-3 py-2 font-mono text-muted-foreground">{p.type}</td>
              <td className="px-3 py-2">{p.required ? "yes" : <span className="text-muted-foreground">no</span>}</td>
              <td className="max-w-[24rem] px-3 py-2">{p.description || <span className="text-muted-foreground">–</span>}</td>
              <td className="px-3 py-2 font-mono">{fmt(p.example)}</td>
              <td className="px-3 py-2 font-mono">{fmt(p.default)}</td>
              <td className="px-3 py-2 font-mono text-xs">
                {p.enum?.length ? p.enum.join(" | ") : typeof p.min === "number" || typeof p.max === "number" ? `${p.min ?? "−∞"} … ${p.max ?? "∞"}` : <span className="text-muted-foreground">–</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const fmt = (v: unknown) => (v === null || v === undefined || v === "" ? <span className="text-muted-foreground">–</span> : String(v));

function RunsTable({ runs }: { runs: ToolRun[] }) {
  if (!runs.length) return <p className="text-sm text-muted-foreground">No runs yet. Ask a question in Chat that needs this tool, or test it from the editor.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-left text-[13px]">
        <thead className="bg-muted/60 text-xs text-muted-foreground">
          <tr>
            {["When", "Arguments", "Rows", "Duration", "Result"].map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((r, i) => (
            <tr key={r.id ?? i} className="border-t border-border">
              <td className="px-3 py-2 whitespace-nowrap text-muted-foreground" title={r.created_at}>
                {formatRelative(r.created_at)}
              </td>
              <td className="max-w-[26rem] truncate px-3 py-2 font-mono text-xs" title={JSON.stringify(r.args)}>
                {summarizeArgs(r.args ?? null, 80) || "–"}
              </td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">{r.row_count ?? "–"}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">{formatMs(r.duration_ms)}</td>
              <td className={cn("max-w-[22rem] truncate px-3 py-2", r.error ? "text-danger" : "text-success")} title={r.error ?? undefined}>
                {r.error ?? "ok"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
