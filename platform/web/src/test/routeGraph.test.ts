import { describe, expect, it } from "vitest";
import type { ChatEvent } from "@/api/types";
import { DEFAULT_GRAPH } from "@/lib/agents";
import { layoutRoute } from "@/lib/routeLayout";
import { activeAgents, buildRouteState, contextFromGraph, dsNodeId, edgeId, parallelGroups, reduceRoute, initialRouteState, toolNodeId, USER_NODE } from "@/lib/routeGraph";

const ctx = contextFromGraph(DEFAULT_GRAPH);
const withMarketing = contextFromGraph({
  ...DEFAULT_GRAPH,
  agents: [...DEFAULT_GRAPH.agents, { id: "marketing_agent", label: "Marketing agent", role: "specialist", parent: "orchestrator", datasource: "marketing" }],
  datasources: [...DEFAULT_GRAPH.datasources, { id: "marketing", label: "marketing schema" }],
});
let t = 1000;
const at = <T extends ChatEvent>(e: T): T => ({ ...e, ts: (t += 100) });

function parallelScript(): ChatEvent[] {
  t = 1000;
  return [
    at({ type: "start", conversation_id: "c" }),
    at({ type: "agent_start", agent: "main_agent" }),
    at({ type: "tool_call", agent: "main_agent", tool: "orchestrator", call_id: "o1", kind: "agent", args: { request: "q3 recon" } }),
    at({ type: "agent_start", agent: "orchestrator" }),
    at({ type: "tool_call", agent: "orchestrator", tool: "finance_agent", call_id: "f1", kind: "agent", args: { request: "commission revenue Q3" } }),
    at({ type: "tool_call", agent: "orchestrator", tool: "trading_agent", call_id: "t1", kind: "agent", args: { request: "commission earned Q3" } }),
    at({ type: "agent_start", agent: "finance_agent" }),
    at({ type: "agent_start", agent: "trading_agent" }),
    at({ type: "tool_call", agent: "finance_agent", tool: "finance_revenue_breakdown", call_id: "s1", kind: "sql", args: { start_date: "2026-07-01" } }),
    at({ type: "tool_call", agent: "trading_agent", tool: "trading_activity_summary", call_id: "s2", kind: "sql", args: { start_date: "2026-07-01" } }),
    at({ type: "tool_result", agent: "trading_agent", tool: "trading_activity_summary", call_id: "s2", kind: "sql", ok: true, ms: 40, row_count: 3 }),
    at({ type: "tool_result", agent: "finance_agent", tool: "finance_revenue_breakdown", call_id: "s1", kind: "sql", ok: true, ms: 55, row_count: 4 }),
    at({ type: "agent_end", agent: "trading_agent", ms: 900 }),
    at({ type: "agent_end", agent: "finance_agent", ms: 1100 }),
    at({ type: "tool_result", agent: "orchestrator", tool: "trading_agent", call_id: "t1", kind: "agent", ok: true, ms: 950 }),
    at({ type: "tool_result", agent: "orchestrator", tool: "finance_agent", call_id: "f1", kind: "agent", ok: true, ms: 1150 }),
    at({ type: "agent_end", agent: "orchestrator", ms: 2000 }),
    at({ type: "tool_result", agent: "main_agent", tool: "orchestrator", call_id: "o1", kind: "agent", ok: true, ms: 2100 }),
    at({ type: "agent_end", agent: "main_agent", ms: 2500 }),
    at({ type: "answer", text: "They match.", route: ["main_agent", "orchestrator", "finance_agent", "trading_agent"], elapsed_ms: 2600 }),
  ];
}

describe("reduceRoute", () => {
  it("starts with the user node active and the root edge", () => {
    const s = buildRouteState(parallelScript().slice(0, 2), ctx);
    expect(s.status).toBe("running");
    expect(s.nodes[USER_NODE]?.status).toBe("active");
    expect(s.nodes.main_agent?.status).toBe("active");
    expect(s.edges[edgeId(USER_NODE, "main_agent")]?.status).toBe("active");
  });

  it("treats kind=agent tool_calls as delegation edges and queues the target", () => {
    const s = buildRouteState(parallelScript().slice(0, 3), ctx);
    expect(s.edges[edgeId("main_agent", "orchestrator")]).toMatchObject({ status: "active", step: 1 });
    expect(s.nodes.orchestrator).toMatchObject({ status: "queued", steps: [1] });
  });

  it("detects a parallel fan-out: overlapping calls from the same caller share a group", () => {
    const s = buildRouteState(parallelScript().slice(0, 8), ctx);
    const fin = s.steps.find((x) => x.tool === "finance_agent")!;
    const trd = s.steps.find((x) => x.tool === "trading_agent")!;
    expect(fin.group).toBe(trd.group);
    expect([...parallelGroups(s.steps).values()]).toEqual([[2, 3]]);
    expect(activeAgents(s).sort()).toEqual(["finance_agent", "main_agent", "orchestrator", "trading_agent"]);
    expect(s.edges[edgeId("orchestrator", "finance_agent")]?.status).toBe("active");
    expect(s.edges[edgeId("orchestrator", "trading_agent")]?.status).toBe("active");
  });

  it("creates leaf tool nodes + datasource edges and completes them with ms and row_count", () => {
    const events = parallelScript();
    const mid = buildRouteState(events.slice(0, 10), ctx);
    const tn = toolNodeId("trading_agent", "trading_activity_summary");
    expect(mid.nodes[tn]).toMatchObject({ kind: "tool", status: "active", toolKind: "sql", agent: "trading_agent" });
    expect(mid.edges[edgeId(tn, dsNodeId("trading"))]?.status).toBe("active");
    expect(mid.nodes[dsNodeId("trading")]?.status).toBe("active");

    const after = buildRouteState(events.slice(0, 11), ctx);
    expect(after.nodes[tn]).toMatchObject({ status: "done", ms: 40, rowCount: 3 });
    expect(after.nodes[dsNodeId("trading")]?.status).toBe("done");
    expect(after.steps.find((x) => x.callId === "s2")).toMatchObject({ status: "ok", ms: 40, rowCount: 3 });
    // the finance call is still running
    expect(after.steps.find((x) => x.callId === "s1")?.status).toBe("running");
  });

  it("finishes everything on answer", () => {
    const s = buildRouteState(parallelScript(), ctx);
    expect(s.status).toBe("done");
    expect(s.answer).toBe("They match.");
    expect(s.elapsedMs).toBe(2600);
    expect(s.steps.map((x) => x.n)).toEqual([1, 2, 3, 4, 5]);
    expect(s.steps.every((x) => x.status === "ok")).toBe(true);
    expect(Object.values(s.edges).some((e) => e.status === "active")).toBe(false);
    expect(s.nodes.finance_agent).toMatchObject({ status: "done", ms: 1100 });
    expect(activeAgents(s)).toEqual([]);
  });

  it("sequential calls get separate groups", () => {
    t = 0;
    const s = buildRouteState(
      [
        at({ type: "start", conversation_id: "c" }),
        at({ type: "agent_start", agent: "orchestrator" }),
        at({ type: "tool_call", agent: "orchestrator", tool: "trading_agent", call_id: "a", kind: "agent" }),
        at({ type: "tool_result", agent: "orchestrator", tool: "trading_agent", call_id: "a", kind: "agent", ok: true }),
        at({ type: "tool_call", agent: "orchestrator", tool: "marketing_agent", call_id: "b", kind: "agent" }),
        at({ type: "agent_start", agent: "marketing_agent" }),
        at({ type: "tool_call", agent: "marketing_agent", tool: "campaign_performance", call_id: "m", kind: "function", args: { entity_id: "NM-SG" } }),
      ],
      withMarketing,
    );
    expect(s.steps[0]!.group).not.toBe(s.steps[1]!.group);
    expect(parallelGroups(s.steps).size).toBe(0);
    expect(s.nodes.trading_agent?.status).toBe("done");
    expect(s.nodes[toolNodeId("marketing_agent", "campaign_performance")]?.toolKind).toBe("function");
    expect(s.edges[edgeId(toolNodeId("marketing_agent", "campaign_performance"), dsNodeId("marketing"))]?.status).toBe("active");
  });

  it("marks failed tool results and stream errors red", () => {
    t = 0;
    let s = buildRouteState(
      [
        at({ type: "start", conversation_id: "c" }),
        at({ type: "agent_start", agent: "finance_agent" }),
        at({ type: "tool_call", agent: "finance_agent", tool: "finance_monthly_pnl", call_id: "x", kind: "sql" }),
        at({ type: "tool_result", agent: "finance_agent", tool: "finance_monthly_pnl", call_id: "x", kind: "sql", ok: false, error: "bad date" }),
        at({ type: "tool_call", agent: "finance_agent", tool: "finance_budget_vs_actual", call_id: "y", kind: "sql" }),
      ],
      ctx,
    );
    expect(s.nodes[toolNodeId("finance_agent", "finance_monthly_pnl")]).toMatchObject({ status: "error", error: "bad date" });
    expect(s.steps[0]!.status).toBe("error");
    s = reduceRoute(s, { type: "error", message: "GEMINI_API_KEY missing", ts: 999 }, ctx);
    expect(s.status).toBe("error");
    expect(s.error).toMatch(/GEMINI/);
    expect(s.steps[1]!.status).toBe("error");
    expect(s.nodes.finance_agent?.status).toBe("error");
    expect(s.nodes[USER_NODE]?.status).toBe("done");
  });

  it("finalises the route on error even when a nested agent never sends agent_end", () => {
    t = 0;
    const s = buildRouteState(
      [
        at({ type: "start", conversation_id: "c" }),
        at({ type: "agent_start", agent: "main_agent" }),
        at({ type: "tool_call", agent: "main_agent", tool: "orchestrator", call_id: "o", kind: "agent" }),
        at({ type: "agent_start", agent: "orchestrator" }),
        at({ type: "tool_call", agent: "orchestrator", tool: "trading_agent", call_id: "t", kind: "agent" }),
        at({ type: "agent_start", agent: "trading_agent" }),
        at({ type: "tool_call", agent: "trading_agent", tool: "trading_top_instruments", call_id: "q", kind: "sql" }),
        at({ type: "error", message: "model call failed" }),
      ],
      ctx,
    );
    expect(s.status).toBe("error");
    expect(s.elapsedMs).toBe(700);
    expect(activeAgents(s)).toEqual([]);
    expect(Object.values(s.nodes).some((n) => n.status === "active" || n.status === "queued")).toBe(false);
    expect(Object.values(s.edges).filter((e) => e.status === "active")).toEqual([]);
    expect(s.edges[edgeId("orchestrator", "trading_agent")]?.status).toBe("error");
    expect(s.nodes.trading_agent?.status).toBe("error");
    expect(s.steps.every((x) => x.status === "error")).toBe(true);
  });

  it("matches a result without a known call_id to the oldest running call of that tool", () => {
    let s = initialRouteState();
    s = reduceRoute(s, { type: "tool_call", agent: "trading_agent", tool: "trading_top_instruments", call_id: "", kind: "sql" }, ctx);
    s = reduceRoute(s, { type: "tool_result", agent: "trading_agent", tool: "trading_top_instruments", call_id: "zzz", kind: "sql", ok: true, row_count: 5 }, ctx);
    expect(s.status).toBe("running");
    expect(s.steps[0]).toMatchObject({ status: "ok", rowCount: 5 });
  });

  it("a fresh start event resets previous state", () => {
    const done = buildRouteState(parallelScript(), ctx);
    const s = reduceRoute(done, { type: "start", conversation_id: "c2" }, ctx);
    expect(s.steps).toEqual([]);
    expect(s.answer).toBeNull();
    expect(s.conversationId).toBe("c2");
  });
});

describe("layoutRoute", () => {
  it("gives the marketing agent its own column with function tools and its schema", () => {
    const graph = {
      ...DEFAULT_GRAPH,
      agents: [...DEFAULT_GRAPH.agents, { id: "marketing_agent", label: "Marketing agent", role: "specialist" as const, parent: "orchestrator", datasource: "marketing" }],
      tools: [{ name: "campaign_performance", agent: "marketing_agent", tool_type: "function" as const, title: "Spend, clicks and sign-ups per campaign for a date range." }],
      datasources: [...DEFAULT_GRAPH.datasources, { id: "marketing", label: "marketing schema" }],
    };
    const { nodes, edges } = layoutRoute(graph, initialRouteState());
    const agent = nodes.find((n) => n.id === "marketing_agent");
    const tool = nodes.find((n) => n.id === toolNodeId("marketing_agent", "campaign_performance"));
    const ds = nodes.find((n) => n.id === dsNodeId("marketing"));
    expect(agent?.data).toMatchObject({ label: "Marketing agent", tone: "marketing" });
    expect(tool?.data).toMatchObject({ toolKind: "function", tone: "marketing" });
    expect(ds?.data).toMatchObject({ label: "marketing schema", sublabel: "Postgres · marketing.*" });
    expect(edges.some((e) => e.source === tool?.id && e.target === ds?.id)).toBe(true);
  });
});
