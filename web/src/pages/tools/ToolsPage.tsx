import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertCircle, Plus, Search, Wrench } from "lucide-react";
import { toast } from "sonner";
import { useSetToolEnabled, useTools } from "@/api/hooks";
import type { Tool, ToolAgent } from "@/api/types";
import { ToolTypeBadge } from "@/components/Badges";
import { EmptyState, ErrorState, PageHeader } from "@/components/States";
import { Button, Input, Segmented, Skeleton, Switch } from "@/components/ui";
import { agentMeta, toneColor, toolAgentId } from "@/lib/agents";
import { formatMs, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

type AgentFilter = "all" | ToolAgent;
type TypeFilter = "all" | "sql" | "factual";

export default function ToolsPage() {
  const { data, isLoading, isError, error, refetch } = useTools();
  const [q, setQ] = useState("");
  const [agent, setAgent] = useState<AgentFilter>("all");
  const [type, setType] = useState<TypeFilter>("all");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data ?? []).filter(
      (t) =>
        (agent === "all" || t.agent === agent) &&
        (type === "all" || t.tool_type === type) &&
        (!needle || `${t.name} ${t.title} ${t.description}`.toLowerCase().includes(needle)),
    );
  }, [data, q, agent, type]);

  const groups: { agent: ToolAgent; tools: Tool[] }[] = (["finance", "trading"] as ToolAgent[])
    .map((a) => ({ agent: a, tools: filtered.filter((t) => t.agent === a) }))
    .filter((g) => agent === "all" || g.agent === agent);

  return (
    <div className="mx-auto max-w-6xl px-6 py-8 lg:px-10">
      <PageHeader
        title="Tools"
        description="Every row in tools.tools becomes a typed ADK FunctionTool for its agent. Agents pick up changes on the next question, with no restart."
        actions={
          <Link to="/tools/new">
            <Button variant="primary">
              <Plus className="size-4" aria-hidden /> New tool
            </Button>
          </Link>
        }
      />

      <div className="mb-8 flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, title or description" className="h-9 pl-9" aria-label="Search tools" />
        </div>
        <Segmented
          value={agent}
          onChange={setAgent}
          options={[
            { value: "all", label: "All agents" },
            { value: "finance", label: "Finance" },
            { value: "trading", label: "Trading" },
          ]}
        />
        <Segmented
          value={type}
          onChange={setType}
          options={[
            { value: "all", label: "All types" },
            { value: "sql", label: "SQL" },
            { value: "factual", label: "Factual" },
          ]}
        />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[92px] w-full rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} title="Couldn't load the tool registry" />
      ) : !data?.length ? (
        <EmptyState
          icon={<Wrench className="size-8" />}
          title="No tools registered yet"
          action={
            <Link to="/tools/new">
              <Button variant="primary">Create the first tool</Button>
            </Link>
          }
        >
          The starter tools are seeded from seed/starter_tools.yaml when the app starts. If this stays empty, check the app logs.
        </EmptyState>
      ) : (
        <div className="space-y-10">
          {groups.map((g) => (
            <ToolGroup key={g.agent} agent={g.agent} tools={g.tools} total={data.filter((t) => t.agent === g.agent).length} />
          ))}
        </div>
      )}
    </div>
  );
}

function ToolGroup({ agent, tools, total }: { agent: ToolAgent; tools: Tool[]; total: number }) {
  const meta = agentMeta(toolAgentId(agent));
  const enabled = tools.filter((t) => t.enabled).length;
  return (
    <section aria-labelledby={`group-${agent}`}>
      <div className="mb-3 flex items-baseline gap-2.5">
        <span className="size-2 translate-y-[-1px] rounded-full" style={{ background: toneColor(meta.tone) }} aria-hidden />
        <h2 id={`group-${agent}`} className="text-base font-semibold tracking-tight">
          {meta.label}
        </h2>
        <span className="text-[13px] text-muted-foreground">
          {tools.length === total ? `${total} tool${total === 1 ? "" : "s"}` : `${tools.length} of ${total} shown`} · {enabled} enabled
        </span>
      </div>
      {tools.length ? (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card shadow-xs">
          {tools.map((t) => (
            <ToolRow key={t.name} tool={t} />
          ))}
        </ul>
      ) : (
        <p className="rounded-xl border border-dashed border-input/70 px-5 py-6 text-sm text-muted-foreground">No {meta.short.toLowerCase()} tools match these filters.</p>
      )}
    </section>
  );
}

function ToolRow({ tool }: { tool: Tool }) {
  const navigate = useNavigate();
  const toggle = useSetToolEnabled();
  const run = tool.last_run;
  const open = () => navigate(`/tools/${encodeURIComponent(tool.name)}`);
  return (
    <li
      className={cn("group flex cursor-pointer items-start gap-4 px-5 py-4 transition-colors duration-150 hover:bg-muted/50 focus-visible:-outline-offset-2", !tool.enabled && "bg-muted/25")}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" && e.target === e.currentTarget) open();
      }}
      tabIndex={0}
      aria-label={`${tool.name}: ${tool.title}`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("font-mono text-[13px] font-semibold", !tool.enabled && "text-muted-foreground")}>{tool.name}</span>
          <ToolTypeBadge type={tool.tool_type} />
          {!tool.enabled ? <span className="rounded-md bg-subtle px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">disabled</span> : null}
        </div>
        <div className={cn("mt-1 text-sm font-medium", !tool.enabled && "text-foreground/70")}>{tool.title}</div>
        <p className="mt-0.5 line-clamp-2 max-w-[90ch] text-[13px] text-muted-foreground">{tool.description}</p>
      </div>
      <div className="hidden w-44 shrink-0 text-right text-xs leading-relaxed sm:block">
        {run ? (
          <>
            <div className={cn("inline-flex items-center gap-1", run.error ? "text-danger" : "text-foreground/80")}>
              {run.error ? <AlertCircle className="size-3.5" aria-hidden /> : null}
              {run.error ? "Last run failed" : `${run.row_count ?? 0} rows · ${formatMs(run.duration_ms)}`}
            </div>
            <div className="text-muted-foreground">{formatRelative(run.created_at)}</div>
          </>
        ) : (
          <span className="text-muted-foreground">Not run yet</span>
        )}
      </div>
      <div className="pt-0.5" onClick={(e) => e.stopPropagation()}>
        <Switch
          checked={tool.enabled}
          label={tool.enabled ? `Disable ${tool.name}` : `Enable ${tool.name}`}
          disabled={toggle.isPending && toggle.variables?.name === tool.name}
          onChange={(enabled) =>
            toggle.mutate(
              { name: tool.name, enabled },
              {
                onSuccess: () => toast.success(`${tool.name} ${enabled ? "enabled" : "disabled"}. Agents see it on the next question.`),
                onError: (e) => toast.error(`Couldn't update ${tool.name}: ${e.message}`),
              },
            )
          }
        />
      </div>
    </li>
  );
}

