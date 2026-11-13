/**
 * Dev-only mock backend (VITE_MOCK=1). Patches window.fetch so every `/api/*`
 * call is answered from fixtures, including a scripted SSE chat that exercises
 * parallel fan-out, sequential hops, the marketing agent and the error path.
 * Set localStorage `mock-no-marketing` to see the graph before the workshop adds it.
 * Imported only behind `import.meta.env.DEV`, so it never ships in a build.
 */
import type { ChatEvent, Graph, SchemaName, Tool, ToolParam, ToolSpec, ToolTestResponse } from "@/api/types";
import { extractPlaceholders } from "@/lib/placeholders";
import * as fx from "./fixtures";

type Step = [delay: number, ev: ChatEvent | ((ctx: ScriptCtx) => ChatEvent)];
interface ScriptCtx {
  conversationId: string;
  t0: number;
}

let tools: Tool[] = structuredClone(fx.tools);
let callSeq = 0;
const cid = () => `call_${++callSeq}`;

// ---- chat scripts ---------------------------------------------------------------------------

function delegate(from: string, to: string, request: string, inner: Step[], innerMs: number): Step[] {
  const id = cid();
  return [
    [180, { type: "tool_call", agent: from, tool: to, call_id: id, kind: "agent", args: { request } }],
    [220, { type: "agent_start", agent: to, invocation_id: `inv-${id}` }],
    ...inner,
    [260, { type: "agent_end", agent: to, ms: innerMs }],
    [90, { type: "tool_result", agent: from, tool: to, call_id: id, kind: "agent", ok: true, ms: innerMs + 120, row_count: null, error: null, preview: `${to} findings…` }],
  ];
}

function leaf(agent: string, tool: string, kind: "sql" | "factual" | "function", args: Record<string, unknown>, ms: number, rows: number | null, preview: unknown, error?: string): Step[] {
  const id = cid();
  return [
    [380, { type: "tool_call", agent, tool, call_id: id, kind, args }],
    [ms + 400, { type: "tool_result", agent, tool, call_id: id, kind, ok: !error, ms, row_count: error ? null : rows, error: error ?? null, preview: error ? null : preview }],
  ];
}

/** Interleave two step lists so they run "in parallel" (both calls first, then results). */
function parallel(from: string, branches: { to: string; request: string; inner: Step[]; ms: number }[]): Step[] {
  const calls: Step[] = [];
  const starts: Step[] = [];
  const bodies: Step[][] = [];
  const ends: Step[] = [];
  for (const b of branches) {
    const id = cid();
    calls.push([160, { type: "tool_call", agent: from, tool: b.to, call_id: id, kind: "agent", args: { request: b.request } }]);
    starts.push([140, { type: "agent_start", agent: b.to, invocation_id: `inv-${id}` }]);
    bodies.push(b.inner);
    ends.push([220, { type: "agent_end", agent: b.to, ms: b.ms }]);
    ends.push([60, { type: "tool_result", agent: from, tool: b.to, call_id: id, kind: "agent", ok: true, ms: b.ms + 90, preview: `${b.to} findings…` }]);
  }
  // Interleave the bodies step by step.
  const merged: Step[] = [];
  const max = Math.max(...bodies.map((b) => b.length));
  for (let i = 0; i < max; i++) for (const b of bodies) if (b[i]) merged.push(b[i]!);
  return [...calls, ...starts, ...merged, ...ends];
}

function wrap(inner: Step[], answer: string, route: string[]): Step[] {
  const o = cid();
  return [
    [0, (c) => ({ type: "start", conversation_id: c.conversationId })],
    [150, { type: "agent_start", agent: "main_agent", invocation_id: "inv-main" }],
    [500, { type: "tool_call", agent: "main_agent", tool: "orchestrator", call_id: o, kind: "agent", args: { request: "Self-contained rewrite of the user's question" } }],
    [200, { type: "agent_start", agent: "orchestrator", invocation_id: "inv-orch" }],
    ...inner,
    [300, { type: "agent_end", agent: "orchestrator", ms: 4200 }],
    [80, { type: "tool_result", agent: "main_agent", tool: "orchestrator", call_id: o, kind: "agent", ok: true, ms: 4400, preview: "Merged findings from specialists" }],
    [700, { type: "agent_end", agent: "main_agent", ms: 5600 }],
    [60, (c) => ({ type: "answer", text: answer, route: ["main_agent", "orchestrator", ...route], elapsed_ms: Date.now() - c.t0 })],
  ];
}

const campaignRows = [
  ["CMP-041", "Nimbus Go launch - social ads", 31_620.4, 34],
  ["CMP-042", "Nimbus Go launch - search ads", 27_310.9, 29],
  ["CMP-033", "NM-SG Q2 2026 - search ads", 18_240.0, 30],
];

const topRows = [
  ["BTCUSD", "Bitcoin", "crypto", 812, 41_220_000, 96_480.5, -12_300.1],
  ["XAUUSD", "Gold", "commodities", 640, 28_900_000, 61_210.0, 8_420.9],
  ["EURUSD", "Euro / US Dollar", "forex", 1_204, 52_100_000, 48_930.2, -3_110.4],
];

function scriptFor(message: string): Step[] {
  const m = message.toLowerCase();
  callSeq = 0;

  if (/\b(hi|hello|hey|thanks|who are you)\b/.test(m) && m.length < 40) {
    return [
      [0, (c) => ({ type: "start", conversation_id: c.conversationId })],
      [150, { type: "agent_start", agent: "main_agent" }],
      [900, { type: "agent_end", agent: "main_agent", ms: 900 }],
      [50, (c) => ({ type: "answer", text: "Hi! I'm the Nimbus Markets assistant. Ask me about our **finance** numbers, **trading** activity or **marketing** campaigns.", route: ["main_agent"], elapsed_ms: Date.now() - c.t0 })],
    ];
  }

  if (m.includes("fail") || m.includes("api key")) {
    // A nested agent raises: no agent_end / tool_result ever arrives, only `error`.
    return [
      [0, (c) => ({ type: "start", conversation_id: c.conversationId })],
      [150, { type: "agent_start", agent: "main_agent" }],
      [400, { type: "tool_call", agent: "main_agent", tool: "orchestrator", call_id: "e1", kind: "agent", args: { request: "Top instruments last month" } }],
      [200, { type: "agent_start", agent: "orchestrator" }],
      [300, { type: "tool_call", agent: "orchestrator", tool: "trading_agent", call_id: "e2", kind: "agent", args: { request: "Top instruments by commission, October 2026" } }],
      [200, { type: "agent_start", agent: "trading_agent" }],
      [700, { type: "error", message: "LLM_API_KEY is missing or invalid. Add it to .env at the repo root and run make up again." }],
    ];
  }

  if (m.includes("match") || m.includes("reconcil")) {
    return wrap(
      parallel("orchestrator", [
        {
          to: "finance_agent",
          request: "Total Trading commission revenue booked in the GL for Q3 2026 (Jul–Sep), by month.",
          inner: leaf("finance_agent", "finance_revenue_breakdown", "sql", { start_date: "2026-07-01", end_date: "2026-09-30", group_by: "category" }, 46, 4, [["Trading commission", 1_284_310.55, 61.2]]),
          ms: 1900,
        },
        {
          to: "trading_agent",
          request: "Total commission earned on closed trades in Q3 2026 (Jul–Sep), by month.",
          inner: leaf("trading_agent", "trading_activity_summary", "sql", { start_date: "2026-07-01", end_date: "2026-09-30" }, 58, 3, [["2026-07-01", 6110, 182_000_000, 402_118.2]]),
          ms: 2100,
        },
      ]),
      "**Yes — they reconcile within 0.04%.**\n\n| Month | GL commission revenue | Trading desk commission | Difference |\n|---|---:|---:|---:|\n| Jul | $402,301 | $402,118 | $183 |\n| Aug | $371,950 | $371,802 | $148 |\n| Sep | $510,060 | $509,871 | $189 |\n| **Q3** | **$1,284,311** | **$1,283,791** | **$520** |\n\nThe small gap is FX rounding on non-USD entities (finance agent, `finance_revenue_breakdown`; trading agent, `trading_activity_summary`).",
      ["finance_agent", "trading_agent", "finance_revenue_breakdown", "trading_activity_summary"],
    );
  }

  if (m.includes("overspen") || m.includes("overrun")) {
    return wrap(
      [
        ...delegate(
          "orchestrator",
          "finance_agent",
          "Marketing budget vs actual by entity, Jun–Sep 2026.",
          leaf("finance_agent", "finance_budget_vs_actual", "sql", { month: "2026-08-01", by_entity: true }, 58, 6, [["NM-SG", "Marketing", 40_000, 62_100, 22_100]]),
          1500,
        ),
        ...delegate(
          "orchestrator",
          "marketing_agent",
          "Spend and sign-ups per campaign at NM-SG, Jun–Sep 2026.",
          leaf("marketing_agent", "campaign_performance", "function", { entity_id: "NM-SG", start_date: "2026-06-01", end_date: "2026-09-30" }, 36, 3, campaignRows),
          1300,
        ),
      ],
      "**NM-SG** overspent its Marketing budget by about **55%** since June (finance agent, `finance_budget_vs_actual`).\n\nIt did **not** buy more clients (marketing agent, `campaign_performance`): the **Nimbus Go launch** campaigns cost about 50% more than NM-SG's earlier campaigns but brought in about the same number of sign-ups, so cost per sign-up rose from ~$610 to ~$930.",
      ["finance_agent", "marketing_agent", "finance_budget_vs_actual", "campaign_performance"],
    );
  }

  if (m.includes("budget")) {
    return wrap(
      [
        ...parallel("orchestrator", [
          {
            to: "finance_agent",
            request: "Budget vs actual by category for August 2026.",
            inner: leaf("finance_agent", "finance_budget_vs_actual", "sql", { month: "2026-08-01" }, 63, 9, [["Trading commission", "revenue", 455_000, 371_950, -83_050]]),
            ms: 1800,
          },
          {
            to: "trading_agent",
            request: "Monthly trades, volume and commission for Jun–Aug 2026.",
            inner: leaf("trading_agent", "trading_activity_summary", "sql", { start_date: "2026-06-01", end_date: "2026-08-31" }, 51, 3, [["2026-08-01", 4210, 121_000_000, 371_802]]),
            ms: 1700,
          },
        ]),
        ...delegate(
          "orchestrator",
          "marketing_agent",
          "Spend and sign-ups per campaign at NM-SG for August 2026.",
          leaf("marketing_agent", "campaign_performance", "function", { entity_id: "NM-SG", start_date: "2026-08-01", end_date: "2026-08-31" }, 34, 3, campaignRows),
          1300,
        ),
      ],
      "**We missed August revenue budget by $96k (−8.1%)**, almost entirely in **Trading commission** (−$83k).\n\n- Trading volume fell **31%** vs July (4,210 trades vs 6,110) — fewer active clients, not lower fees.\n- Costs were on plan except **NM-SG Marketing** (+$22k over).\n- Marketing: the NM-SG overspend is the **Nimbus Go launch** campaigns, which brought in about as many sign-ups as earlier, cheaper campaigns.",
      ["finance_agent", "trading_agent", "marketing_agent", "finance_budget_vs_actual", "trading_activity_summary", "campaign_performance"],
    );
  }

  if (m.includes("campaign") || m.includes("sign-up") || m.includes("marketing")) {
    return wrap(
      delegate(
        "orchestrator",
        "marketing_agent",
        "Sign-ups and spend per campaign for Q3 2026 (Jul–Sep).",
        leaf("marketing_agent", "campaign_performance", "function", { start_date: "2026-07-01", end_date: "2026-09-30" }, 38, 5, campaignRows),
        1200,
      ),
      "Top campaigns by sign-ups last quarter (marketing agent, `campaign_performance`):\n\n| # | Campaign | Sign-ups | Spend | Cost per sign-up |\n|---|---|---:|---:|---:|\n| 1 | NM-UK Q3 2026 - search ads | 38 | $21,940 | $577 |\n| 2 | Nimbus Go launch - social ads | 34 | $31,620 | $930 |\n| 3 | NM-AE Q3 2026 - app-store ads | 21 | $12,480 | $594 |",
      ["marketing_agent", "campaign_performance"],
    );
  }

  if (m.includes("instrument") || m.includes("trad") || m.includes("client")) {
    return wrap(
      delegate(
        "orchestrator",
        "trading_agent",
        "Top 5 instruments by commission for October 2026.",
        leaf("trading_agent", "trading_top_instruments", "sql", { start_date: "2026-10-01", end_date: "2026-10-31", metric: "commission", limit: 5 }, 41, 5, topRows),
        1400,
      ),
      "Top instruments by commission in October (trading agent):\n\n| # | Instrument | Commission | Trades |\n|---|---|---:|---:|\n| 1 | Bitcoin (BTCUSD) | $96,481 | 812 |\n| 2 | Gold (XAUUSD) | $61,210 | 640 |\n| 3 | EUR/USD | $48,930 | 1,204 |\n| 4 | US Tech 100 | $39,775 | 501 |\n| 5 | GBP/USD | $22,108 | 655 |",
      ["trading_agent", "trading_top_instruments"],
    );
  }

  // default: finance, with one failing call that the agent corrects
  return wrap(
    delegate(
      "orchestrator",
      "finance_agent",
      "Operating profit by month for Q3 2026 (Jul–Sep).",
      [
        ...leaf("finance_agent", "finance_monthly_pnl", "sql", { start_month: "2026-07", end_month: "2026-09" }, 12, null, null, "start_month: expected YYYY-MM-DD, got '2026-07'"),
        ...leaf("finance_agent", "finance_monthly_pnl", "sql", { start_month: "2026-07-01", end_month: "2026-09-30" }, 39, 3, [["2026-07-01", 658_200, 431_900, 226_300]]),
      ],
      1600,
    ),
    "Operating profit last quarter (finance agent, `finance_monthly_pnl`):\n\n| Month | Revenue | Expenses | Operating profit | Margin |\n|---|---:|---:|---:|---:|\n| Jul | $658,200 | $431,900 | $226,300 | 34.4% |\n| Aug | $607,450 | $455,120 | $152,330 | 25.1% |\n| Sep | $812,900 | $448,300 | $364,600 | 44.9% |\n\nAugust dipped on lower trading commission; September rebounded with a crypto volume spike.",
    ["finance_agent", "finance_monthly_pnl"],
  );
}

function chatResponse(body: { conversation_id: string; message: string }, signal?: AbortSignal | null): Response {
  const steps = scriptFor(body.message ?? "");
  const ctx: ScriptCtx = { conversationId: body.conversation_id, t0: Date.now() };
  const enc = new TextEncoder();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let i = 0;
      const next = () => {
        if (signal?.aborted) {
          controller.close();
          return;
        }
        if (i >= steps.length) {
          controller.close();
          return;
        }
        const [delay, ev] = steps[i++]!;
        timer = setTimeout(() => {
          const e = typeof ev === "function" ? ev(ctx) : ev;
          const frame = `data: ${JSON.stringify({ ...e, ts: Date.now() })}\n\n`;
          // Occasionally prepend a keepalive and split the frame to exercise the parser.
          if (i % 4 === 0) controller.enqueue(enc.encode(": ping\n\n"));
          const cut = Math.floor(frame.length / 2);
          controller.enqueue(enc.encode(frame.slice(0, cut)));
          controller.enqueue(enc.encode(frame.slice(cut)));
          next();
        }, delay);
      };
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
      next();
    },
    cancel() {
      clearTimeout(timer);
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

// ---- tools ------------------------------------------------------------------------------------

function declaration(spec: ToolSpec) {
  const props: Record<string, unknown> = {};
  const required: string[] = [];
  for (const p of spec.tool_type === "sql" ? spec.params : []) {
    const schema: Record<string, unknown> = {
      type: p.type === "date" ? "string" : p.type,
      description: [p.description, p.type === "date" ? "Format: YYYY-MM-DD." : "", p.example !== undefined && p.example !== null ? `Example: ${p.example}.` : ""].filter(Boolean).join(" "),
    };
    if (p.type === "date") schema.format = "date";
    if (p.enum?.length) schema.enum = p.enum;
    if (p.default !== undefined && p.default !== null) schema.default = p.default;
    if (typeof p.min === "number") schema.minimum = p.min;
    if (typeof p.max === "number") schema.maximum = p.max;
    props[p.name] = schema;
    if (p.required) required.push(p.name);
  }
  return {
    name: spec.name,
    description: spec.description,
    parameters: spec.tool_type === "sql" && spec.params.length ? { type: "object", properties: props, required } : null,
  };
}

function lint(spec: ToolSpec): string[] {
  const errors: string[] = [];
  if (!/^[a-z][a-z0-9_]{2,63}$/.test(spec.name ?? "")) errors.push("name: must match ^[a-z][a-z0-9_]{2,63}$");
  if (!spec.title?.trim()) errors.push("title: required");
  if (!spec.description?.trim() || spec.description.trim().length < 20) errors.push("description: write at least a sentence the LLM can use (20+ chars)");
  if (spec.tool_type === "sql") {
    const sql = (spec.sql ?? "").trim();
    if (!/^(select|with)\b/i.test(sql)) errors.push("sql: must be a single SELECT or WITH statement");
    if (/;\s*\S/.test(sql)) errors.push("sql: only one statement is allowed");
    const other = spec.agent === "finance" ? "trading" : "finance";
    if (new RegExp(`\\b(${other}|marketing|tools)\\.`, "i").test(sql)) errors.push(`sql: a ${spec.agent} tool may only read the ${spec.agent} schema`);
    const ph = extractPlaceholders(sql);
    const declared = spec.params.map((p) => p.name);
    for (const p of ph) if (!declared.includes(p)) errors.push(`params: placeholder :${p} has no declared param`);
    for (const d of declared) if (!ph.includes(d)) errors.push(`params: '${d}' is declared but not used in the SQL`);
    for (const p of spec.params) if (p.required && (p.example === undefined || p.example === null || p.example === "")) errors.push(`params.${p.name}: required params need an example for the test run`);
  } else {
    if (!spec.answer?.trim()) errors.push("answer: required for factual tools");
    if (!spec.source?.trim()) errors.push("source: required for factual tools");
  }
  return errors;
}

function testTool(spec: ToolSpec): ToolTestResponse {
  const errors = lint(spec);
  const decl = spec.name ? declaration(spec) : null;
  if (errors.length) return { ok: false, errors, declaration: decl, result: null };
  if (spec.tool_type === "factual") return { ok: true, errors: [], declaration: decl, result: { answer: spec.answer ?? "", source: spec.source ?? null } };
  const sql = spec.sql ?? "";
  const cols = [...new Set([...sql.matchAll(/\bAS\s+([a-z_][a-z0-9_]*)/gi)].map((x) => x[1]!.toLowerCase()))].filter((x) => !["b", "act"].includes(x));
  const columns = cols.length ? cols : ["value"];
  const rows = Array.from({ length: 6 }, (_, i) => columns.map((col) => (/(month|date)/.test(col) ? `2026-0${7 + (i % 3)}-01` : /(usd|pct|count|trades|clients|rate)/.test(col) ? Math.round((12000 + i * 3171.37) * 100) / 100 : `${col}_${i + 1}`)));
  return { ok: true, errors: [], declaration: decl, result: { columns, rows, row_count: rows.length, truncated: false, duration_ms: 23 + Math.round(Math.random() * 40) } };
}

// ---- router -----------------------------------------------------------------------------------

/** The graph as it is at the start of the workshop, before anyone adds the marketing agent. */
function withoutMarketing(g: Graph): Graph {
  return {
    agents: g.agents.filter((a) => a.id !== "marketing_agent"),
    tools: g.tools.filter((t) => t.agent !== "marketing_agent"),
    datasources: g.datasources.filter((d) => d.id !== "marketing"),
  };
}

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function handle(url: URL, init: RequestInit | undefined): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const path = url.pathname.replace(/^\/api/, "");
  const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
  await wait(120 + Math.random() * 180);

  if (path === "/health") return json(200, { ...fx.health, llm_key: localStorage.getItem("mock-llm-missing") ? "missing" : "configured" });
  if (path === "/graph") {
    const g = fx.graph();
    g.tools = [...tools.filter((t) => t.enabled).map((t) => ({ name: t.name, agent: `${t.agent}_agent`, tool_type: t.tool_type, title: t.title })), ...g.tools.filter((t) => t.tool_type === "function")];
    return json(200, localStorage.getItem("mock-no-marketing") ? withoutMarketing(g) : g);
  }
  if (path === "/chat/examples") return json(200, fx.examples);
  if (path === "/chat/reset") return json(200, { ok: true });
  if (path === "/chat" && method === "POST") return chatResponse(body, init?.signal);

  if (path === "/tools/test" && method === "POST") return json(200, testTool(body));
  if (path === "/tools" && method === "GET") {
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const agent = url.searchParams.get("agent");
    return json(200, tools.filter((t) => (!agent || t.agent === agent) && (!q || `${t.name} ${t.title} ${t.description}`.toLowerCase().includes(q))));
  }
  if (path === "/tools" && method === "POST") {
    const spec = body as ToolSpec;
    if (tools.some((t) => t.name === spec.name)) return json(409, { detail: `Tool '${spec.name}' already exists.` });
    const errors = lint(spec);
    if (errors.length) return json(422, { detail: "Validation failed", errors });
    const t: Tool = { ...spec, enabled: spec.enabled ?? true, params: spec.params as ToolParam[], updated_at: new Date().toISOString(), last_run: null };
    tools = [...tools, t];
    return json(201, t);
  }
  const m = path.match(/^\/tools\/([^/]+)(\/enabled)?$/);
  if (m) {
    const name = decodeURIComponent(m[1]!);
    const t = tools.find((x) => x.name === name);
    if (!t) return json(404, { detail: `Tool '${name}' not found.` });
    if (m[2] && method === "PATCH") {
      const u = { ...t, enabled: !!body.enabled, updated_at: new Date().toISOString() };
      tools = tools.map((x) => (x.name === name ? u : x));
      return json(200, u);
    }
    if (method === "GET") return json(200, { ...t, runs: fx.toolRuns(name) });
    if (method === "PUT") {
      const errors = lint({ ...body, name });
      if (errors.length) return json(422, { detail: "Validation failed", errors });
      const u: Tool = { ...t, ...body, name, updated_at: new Date().toISOString() };
      tools = tools.map((x) => (x.name === name ? u : x));
      return json(200, u);
    }
    if (method === "DELETE") {
      tools = tools.filter((x) => x.name !== name);
      return json(200, { ok: true });
    }
  }

  if (path === "/schema") return json(200, { schemas: Object.values(fx.schemas).map((s) => ({ name: s.name, comment: s.comment })) });
  const sm = path.match(/^\/schema\/([a-z]+)(?:\/([a-z_]+)\/sample)?$/);
  if (sm) {
    const schema = sm[1] as SchemaName;
    if (!fx.schemas[schema]) return json(404, { detail: `Unknown schema '${schema}'.` });
    if (sm[2]) return json(200, fx.sampleRows(schema, sm[2], Math.min(Number(url.searchParams.get("limit") ?? 5), 50)));
    const s = structuredClone(fx.schemas[schema]);
    if (schema === "tools") s.tables[0]!.row_count = tools.length;
    return json(200, s);
  }
  return json(404, { detail: `Mock has no route for ${method} ${path}` });
}

const realFetch = window.fetch.bind(window);
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  const url = new URL(raw, window.location.origin);
  if (url.origin === window.location.origin && url.pathname.startsWith("/api/")) return handle(url, init);
  return realFetch(input, init);
};

console.info("%c[mock] /api is served from src/mock (VITE_MOCK=1)", "color:#7c3aed");
