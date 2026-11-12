import { KeyRound } from "@/components/icons";
import { useHealth } from "@/api/hooks";
import { cn } from "@/lib/utils";

/** Loud callout shown wherever chatting would fail because the key is missing. */
export function LlmKeyCallout({ className }: { className?: string }) {
  const { data } = useHealth();
  if (data?.llm_key !== "missing") return null;
  return (
    <div role="alert" className={cn("flex gap-3 rounded-xl border border-warning/30 bg-warning/8 p-4", className)}>
      <KeyRound className="mt-0.5 size-5 shrink-0 text-warning" aria-hidden />
      <div className="text-sm">
        <p className="font-semibold">No LLM API key configured</p>
        <p className="mt-1 text-foreground/80">
          Put <code className="rounded bg-muted px-1 py-0.5 text-xs">LLM_API_KEY=…</code> and{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">AGENT_MODEL=…</code> in{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">.env</code> at the repo root (step 2 of Set up in the README), then run{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">make up</code> again. The agents can't answer until then; the Tools and Schema pages still work.
        </p>
      </div>
    </div>
  );
}
