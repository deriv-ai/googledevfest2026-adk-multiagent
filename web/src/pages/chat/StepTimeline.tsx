import { ArrowRight, ChevronRight, CornerDownRight, Loader2, AlertCircle, Check } from "lucide-react";
import { KIND_ICON } from "@/components/Badges";
import { JsonView } from "@/components/JsonView";
import { agentMeta, toneColor } from "@/lib/agents";
import { formatMs, summarizeArgs } from "@/lib/format";
import { parallelGroups, type RouteStep } from "@/lib/routeGraph";
import { cn } from "@/lib/utils";

function StepRow({ step, parallel, first, last }: { step: RouteStep; parallel: number | null; first: boolean; last: boolean }) {
  const caller = agentMeta(step.agent);
  const isAgent = step.kind === "agent";
  const target = isAgent ? agentMeta(step.tool) : null;
  const tone = isAgent ? target!.tone : caller.tone;
  const Icon = KIND_ICON[step.kind];
  const hasDetail = (step.args && Object.keys(step.args).length > 0) || step.preview !== undefined || step.error;

  return (
    <li className="fade-up relative">
      {parallel !== null ? (
        <span
          aria-hidden
          className={cn("absolute left-[13px] w-px bg-input", first ? "top-1/2" : "top-0", last ? "bottom-1/2" : "bottom-0")}
        />
      ) : null}
      <details className="group rounded-lg open:bg-muted/50">
        <summary className={cn("flex list-none items-start gap-3 rounded-lg px-2 py-2 hover:bg-muted/60 [&::-webkit-details-marker]:hidden", !hasDetail && "cursor-default")}>
          <span
            className="relative z-10 mt-px inline-flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-[11.5px] font-semibold text-white"
            style={{ background: step.status === "error" ? "hsl(var(--danger))" : toneColor(tone) }}
          >
            {step.n}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[13.5px]">
              <span className="font-medium" style={{ color: toneColor(caller.tone) }}>
                {caller.short}
              </span>
              <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
              {isAgent ? (
                <span className="font-semibold" style={{ color: toneColor(tone) }}>
                  {target!.label}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 font-mono text-[12.5px] font-medium">
                  <Icon className="size-3.5 text-muted-foreground" aria-hidden />
                  {step.tool}
                </span>
              )}
              {parallel !== null ? <span className="rounded-full bg-subtle px-1.5 py-px text-[10.5px] font-semibold tracking-wide text-muted-foreground uppercase">parallel ×{parallel}</span> : null}
            </div>
            {step.args && Object.keys(step.args).length ? (
              <div className={cn("mt-0.5 truncate text-[12.5px] text-muted-foreground", !isAgent && "font-mono text-[12px]")}>
                {isAgent ? <CornerDownRight className="mr-1 inline size-3 align-[-1px]" aria-hidden /> : null}
                {summarizeArgs(step.args, 120)}
              </div>
            ) : null}
            {step.error ? <div className="mt-0.5 text-[12.5px] text-danger">{step.error}</div> : null}
          </div>
          <div className="flex shrink-0 items-center gap-2 pt-0.5 text-[12.5px] tabular-nums">
            {typeof step.rowCount === "number" ? <span className="text-muted-foreground">{step.rowCount} rows</span> : null}
            {step.status === "running" ? (
              <Loader2 className="size-3.5 animate-spin" style={{ color: toneColor(tone) }} aria-label="running" />
            ) : step.status === "error" ? (
              <AlertCircle className="size-3.5 text-danger" aria-label="failed" />
            ) : (
              <Check className="size-3.5 text-success" aria-label="ok" />
            )}
            <span className="w-14 text-right font-mono text-muted-foreground">{step.status === "running" ? "…" : formatMs(step.ms)}</span>
            {hasDetail ? <ChevronRight className="size-3.5 text-muted-foreground transition-transform group-open:rotate-90" aria-hidden /> : <span className="w-3.5" />}
          </div>
        </summary>
        {hasDetail ? (
          <div className="space-y-2 px-2 pt-1 pb-3 pl-11">
            {step.args && Object.keys(step.args).length ? (
              <div>
                <div className="mb-1 text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">Arguments</div>
                <JsonView value={step.args} className="max-h-56 p-3 text-[12px]" />
              </div>
            ) : null}
            {step.preview !== undefined && step.preview !== null ? (
              <div>
                <div className="mb-1 text-[11.5px] font-semibold tracking-wide text-muted-foreground uppercase">Result preview</div>
                {typeof step.preview === "string" ? (
                  <pre className="max-h-56 overflow-auto rounded-lg border border-border bg-muted/50 p-3 text-[12px] whitespace-pre-wrap">{step.preview}</pre>
                ) : (
                  <JsonView value={step.preview} className="max-h-56 p-3 text-[12px]" />
                )}
              </div>
            ) : null}
          </div>
        ) : null}
      </details>
    </li>
  );
}

export function StepTimeline({ steps, className }: { steps: RouteStep[]; className?: string }) {
  const groups = parallelGroups(steps);
  if (!steps.length) return null;
  return (
    <ol className={cn("space-y-0.5", className)} aria-label="Route steps">
      {steps.map((st) => {
        const g = groups.get(st.group);
        return <StepRow key={`${st.n}-${st.callId}`} step={st} parallel={g ? g.length : null} first={!!g && g[0] === st.n} last={!!g && g[g.length - 1] === st.n} />;
      })}
    </ol>
  );
}
