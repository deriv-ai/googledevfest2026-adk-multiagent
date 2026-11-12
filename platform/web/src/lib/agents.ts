import type { Graph, GraphAgent, ToolAgent } from "@/api/types";

/** Visual identity per agent. `tone` maps to the --agent-* tokens in index.css. */
export type AgentTone = "main" | "orchestrator" | "finance" | "trading" | "news" | "marketing" | "other";

export interface AgentMeta {
  id: string;
  label: string;
  tone: AgentTone;
  short: string;
}

const KNOWN: Record<string, AgentMeta> = {
  main_agent: { id: "main_agent", label: "Main agent", tone: "main", short: "Main" },
  orchestrator: { id: "orchestrator", label: "Orchestrator", tone: "orchestrator", short: "Orchestrator" },
  finance_agent: { id: "finance_agent", label: "Finance agent", tone: "finance", short: "Finance" },
  trading_agent: { id: "trading_agent", label: "Trading agent", tone: "trading", short: "Trading" },
  news_agent: { id: "news_agent", label: "News agent", tone: "news", short: "News" },
  marketing_agent: { id: "marketing_agent", label: "Marketing agent", tone: "marketing", short: "Marketing" },
};

export function agentMeta(id: string, graphAgent?: GraphAgent): AgentMeta {
  const k = KNOWN[id];
  if (k) return graphAgent?.label ? { ...k, label: graphAgent.label } : k;
  const label = graphAgent?.label ?? id.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  return { id, label, tone: "other", short: label.replace(/ agent$/i, "") };
}

/** Tool specs say `finance` / `trading`; the graph and events say `finance_agent`. */
export function toolAgentId(agent: ToolAgent | string): string {
  return agent.endsWith("_agent") ? agent : `${agent}_agent`;
}

export function toneOfToolAgent(agent: ToolAgent | string): AgentTone {
  return agentMeta(toolAgentId(agent)).tone;
}

/** CSS custom-property value for a tone, e.g. `hsl(var(--agent-finance))`. */
export function toneColor(tone: AgentTone, alpha?: number): string {
  return alpha === undefined ? `hsl(var(--agent-${tone}))` : `hsl(var(--agent-${tone}) / ${alpha})`;
}

/** Fallback topology so the route graph renders even before /api/graph answers. */
export const DEFAULT_GRAPH: Graph = {
  agents: [
    { id: "main_agent", label: "Main agent", role: "root" },
    { id: "orchestrator", label: "Orchestrator", role: "router", parent: "main_agent" },
    { id: "finance_agent", label: "Finance agent", role: "specialist", parent: "orchestrator", datasource: "finance" },
    { id: "trading_agent", label: "Trading agent", role: "specialist", parent: "orchestrator", datasource: "trading" },
    { id: "news_agent", label: "News agent", role: "specialist", parent: "orchestrator", datasource: "internet" },
  ],
  tools: [],
  datasources: [
    { id: "finance", label: "finance schema" },
    { id: "trading", label: "trading schema" },
    { id: "internet", label: "Internet (RSS)" },
  ],
};
