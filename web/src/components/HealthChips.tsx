import { KeyRound } from "lucide-react";
import { useHealth } from "@/api/hooks";
import { cn } from "@/lib/utils";

type ChipState = "ok" | "error" | "warn" | "unknown";

function Chip({ label, state, value }: { label: string; state: ChipState; value: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card py-1 pr-3 pl-2.5 text-[13px]">
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          state === "ok" && "bg-success",
          state === "error" && "bg-danger",
          state === "warn" && "bg-warning",
          state === "unknown" && "bg-input",
        )}
      />
      <span className="font-medium">{label}</span>
      <span className="text-muted-foreground">{value}</span>
    </span>
  );
}

export function HealthChips({ className }: { className?: string }) {
  const { data, isError, isLoading } = useHealth();
  if (isLoading)
    return (
      <div className={cn("flex flex-wrap gap-2", className)}>
        {["API", "Database", "News MCP", "LLM key"].map((l) => (
          <Chip key={l} label={l} state="unknown" value="checking…" />
        ))}
      </div>
    );
  if (isError || !data)
    return (
      <div className={cn("flex flex-wrap gap-2", className)}>
        <Chip label="API" state="error" value="unreachable" />
      </div>
    );
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      <Chip label="API" state="ok" value="up" />
      <Chip label="Database" state={data.db === "ok" ? "ok" : "error"} value={data.db === "ok" ? "connected" : "error"} />
      <Chip label="News MCP" state={data.news_mcp === "ok" ? "ok" : "warn"} value={data.news_mcp === "ok" ? "connected" : "unreachable"} />
      <Chip label="LLM key" state={data.llm_key === "configured" ? "ok" : "error"} value={data.llm_mode ? `${data.llm_key} · ${data.llm_mode}` : data.llm_key} />
      <Chip label="Model" state="ok" value={data.model} />
    </div>
  );
}

/** Loud callout shown wherever chatting would fail because the key is missing. */
export function LlmKeyCallout({ className }: { className?: string }) {
  const { data } = useHealth();
  if (data?.llm_key !== "missing") return null;
  return (
    <div role="alert" className={cn("flex gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4", className)}>
      <KeyRound className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
      <div className="text-sm">
        <p className="font-semibold">No Gemini API key configured</p>
        <p className="mt-1 text-foreground/80">
          Put <code className="rounded bg-muted px-1 py-0.5 text-[13px]">GEMINI_API_KEY=…</code> (Google AI Studio) or{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-[13px]">LITELLM_GEMINI_API_KEY=…</code> +{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-[13px]">OPENAI_BASE_URL=…</code> (LiteLLM proxy) in{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-[13px]">.env</code> at the repo root, then run{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-[13px]">make up</code> again. The agents can't answer until then; the Tools and Schema pages still work.
        </p>
      </div>
    </div>
  );
}
