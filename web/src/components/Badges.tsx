import { Bot, Database, FileText, Megaphone, Route, Sparkles, SquareFunction, type LucideIcon } from "lucide-react";
import type { ToolKind } from "@/api/types";
import { agentMeta, toneColor, type AgentTone } from "@/lib/agents";
import { cn } from "@/lib/utils";

export const TONE_ICON: Record<AgentTone, LucideIcon> = {
  main: Sparkles,
  orchestrator: Route,
  finance: Bot,
  trading: Bot,
  marketing: Megaphone,
  other: Bot,
};

export const KIND_ICON: Record<ToolKind, LucideIcon> = {
  sql: Database,
  factual: FileText,
  function: SquareFunction,
  agent: Bot,
};

export function AgentBadge({ agent, className, size = "md" }: { agent: string; className?: string; size?: "sm" | "md" }) {
  const meta = agentMeta(agent.endsWith("_agent") || agent === "orchestrator" ? agent : `${agent}_agent`);
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full font-medium", size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-0.5 text-[13px]", className)}
      style={{ color: toneColor(meta.tone), background: toneColor(meta.tone, 0.12) }}
    >
      <span className="size-1.5 rounded-full" style={{ background: toneColor(meta.tone) }} aria-hidden />
      {meta.short}
    </span>
  );
}

export const KIND_LABEL: Record<ToolKind, string> = { sql: "SQL", factual: "Factual", function: "Python", agent: "Agent" };

export function ToolTypeBadge({ type, className }: { type: ToolKind; className?: string }) {
  const Icon = KIND_ICON[type];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
        type === "factual" ? "bg-success/12 text-success" : "bg-muted text-muted-foreground",
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {KIND_LABEL[type]}
    </span>
  );
}
