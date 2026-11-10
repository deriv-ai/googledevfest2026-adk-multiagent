import { Bot, Database, FileText, Globe, Network, Route, Sparkles, type LucideIcon } from "lucide-react";
import type { ToolKind } from "@/api/types";
import { agentMeta, toneColor, type AgentTone } from "@/lib/agents";
import { cn } from "@/lib/utils";

export const TONE_ICON: Record<AgentTone, LucideIcon> = {
  main: Sparkles,
  orchestrator: Route,
  finance: Bot,
  trading: Bot,
  news: Globe,
  other: Bot,
};

export const KIND_ICON: Record<ToolKind, LucideIcon> = {
  sql: Database,
  factual: FileText,
  mcp: Network,
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

const KIND_LABEL: Record<ToolKind, string> = { sql: "SQL", factual: "Factual", mcp: "MCP", agent: "Agent" };

export function ToolTypeBadge({ type, className }: { type: ToolKind; className?: string }) {
  const Icon = KIND_ICON[type];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wide uppercase",
        type === "factual" ? "border-success/30 text-success" : "border-border text-muted-foreground",
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {KIND_LABEL[type]}
    </span>
  );
}
