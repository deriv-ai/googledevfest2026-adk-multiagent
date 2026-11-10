// Dev-only fixtures for VITE_MOCK=1. Fictional "Nimbus Markets" data — all synthetic.
import type { ChatExample, Graph, Health, SchemaColumn, SchemaDetail, SchemaName, Tool, ToolRun } from "@/api/types";

export const health: Health = {
  ok: true,
  db: "ok",
  news_mcp: "ok",
  llm_key: "configured",
  llm_mode: "direct",
  model: "gemini/gemini-2.5-flash",
  router_model: "gemini/gemini-2.5-flash",
};

export const examples: ChatExample[] = [
  { label: "Finance", prompt: "What was our operating profit by month last quarter?" },
  { label: "Trading", prompt: "What were the top 5 instruments by commission last month?" },
  { label: "News", prompt: "What's in the news about gold prices today?" },
  { label: "Reconcile (parallel)", prompt: "Does the commission revenue we booked in Q3 match what the trading desk earned?" },
  { label: "Driver + news (sequential)", prompt: "Which instrument drove the most commission last month, and what's in the news about it?" },
  { label: "Budget miss (all agents)", prompt: "Why did we miss revenue budget in August?" },
];

const now = Date.now();
const iso = (minsAgo: number) => new Date(now - minsAgo * 60_000).toISOString();

export const tools: Tool[] = [
  {
    name: "finance_monthly_pnl",
    agent: "finance",
    tool_type: "sql",
    title: "Monthly P&L: revenue, expenses, operating profit",
    description:
      "Monthly profit and loss in USD for a range of months: revenue, expenses, operating profit and margin %. Optionally for one entity (entity_id, e.g. NM-UK). Use for profit, margin and 'how did we do' questions.",
    enabled: true,
    params: [
      { name: "start_month", type: "date", required: true, description: "First month (any day in it), YYYY-MM-DD", example: "2026-07-01" },
      { name: "end_month", type: "date", required: true, description: "Last month (any day in it), YYYY-MM-DD", example: "2026-09-30" },
      { name: "entity_id", type: "string", required: false, description: "Optional entity filter, e.g. NM-UK", enum: ["NM-UK", "NM-SG", "NM-AE", "NM-INTL"] },
    ],
    sql: `SELECT date_trunc('month', g.entry_date)::date AS month,
       SUM(g.amount_usd) FILTER (WHERE a.account_type = 'revenue') AS revenue_usd,
       SUM(g.amount_usd) FILTER (WHERE a.account_type = 'expense') AS expenses_usd,
       SUM(CASE WHEN a.account_type = 'revenue' THEN g.amount_usd ELSE -g.amount_usd END) AS operating_profit_usd
FROM finance.gl_entries g
JOIN finance.accounts a USING (account_code)
WHERE g.entry_date >= date_trunc('month', :start_month::date)
  AND g.entry_date < date_trunc('month', :end_month::date) + interval '1 month'
  AND a.account_type IN ('revenue', 'expense')
  AND (:entity_id IS NULL OR g.entity_id = :entity_id)
GROUP BY 1
ORDER BY 1`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: { created_at: iso(14), row_count: 3, duration_ms: 38, error: null },
  },
  {
    name: "finance_revenue_breakdown",
    agent: "finance",
    tool_type: "sql",
    title: "Revenue breakdown by account, category or entity",
    description:
      "Revenue in USD for a date range grouped by account, category (Trading commission, Spread revenue, Subscription fees, Interest income) or entity, with each line's share of total. Use for 'where does revenue come from' and commission-revenue questions.",
    enabled: true,
    params: [
      { name: "start_date", type: "date", required: true, description: "Inclusive start, YYYY-MM-DD", example: "2026-07-01" },
      { name: "end_date", type: "date", required: true, description: "Inclusive end, YYYY-MM-DD", example: "2026-09-30" },
      { name: "group_by", type: "string", required: false, default: "category", enum: ["account", "category", "entity"], description: "How to group the revenue lines" },
    ],
    sql: `SELECT CASE :group_by WHEN 'account' THEN a.account_name WHEN 'entity' THEN g.entity_id ELSE a.category END AS line,
       SUM(g.amount_usd) AS revenue_usd,
       ROUND(100.0 * SUM(g.amount_usd) / SUM(SUM(g.amount_usd)) OVER (), 1) AS share_pct
FROM finance.gl_entries g
JOIN finance.accounts a USING (account_code)
WHERE a.account_type = 'revenue'
  AND g.entry_date BETWEEN :start_date AND :end_date
GROUP BY 1
ORDER BY 2 DESC`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: { created_at: iso(40), row_count: 4, duration_ms: 52, error: null },
  },
  {
    name: "finance_budget_vs_actual",
    agent: "finance",
    tool_type: "sql",
    title: "Budget vs actual by category for a month",
    description:
      "For one month: budget, actual, variance in USD and %, and an over/under flag per account category. Optional entity filter. Use for 'did we hit budget' and cost-overrun questions.",
    enabled: true,
    params: [
      { name: "month", type: "date", required: true, description: "Any day in the month, YYYY-MM-DD", example: "2026-08-01" },
      { name: "entity_id", type: "string", required: false, description: "Optional entity filter, e.g. NM-SG" },
    ],
    sql: `WITH b AS (
  SELECT a.category, a.account_type, SUM(bu.budget_usd) AS budget_usd
  FROM finance.budgets bu JOIN finance.accounts a USING (account_code)
  WHERE bu.month = date_trunc('month', :month::date)
    AND (:entity_id IS NULL OR bu.entity_id = :entity_id)
  GROUP BY 1, 2
), act AS (
  SELECT a.category, SUM(g.amount_usd) AS actual_usd
  FROM finance.gl_entries g JOIN finance.accounts a USING (account_code)
  WHERE date_trunc('month', g.entry_date) = date_trunc('month', :month::date)
    AND (:entity_id IS NULL OR g.entity_id = :entity_id)
  GROUP BY 1
)
SELECT b.category, b.account_type, b.budget_usd, act.actual_usd,
       act.actual_usd - b.budget_usd AS variance_usd
FROM b LEFT JOIN act USING (category)
ORDER BY ABS(act.actual_usd - b.budget_usd) DESC`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: null,
  },
  {
    name: "trading_activity_summary",
    agent: "trading",
    tool_type: "sql",
    title: "Monthly trading activity: trades, volume, commission, PnL",
    description:
      "Per month for a date range: number of closed trades, notional volume USD, commission USD, client PnL USD, active clients and new clients. Optional asset_class filter (forex, crypto, commodities, indices).",
    enabled: true,
    params: [
      { name: "start_date", type: "date", required: true, description: "Inclusive start, YYYY-MM-DD", example: "2026-07-01" },
      { name: "end_date", type: "date", required: true, description: "Inclusive end, YYYY-MM-DD", example: "2026-09-30" },
      { name: "asset_class", type: "string", required: false, enum: ["forex", "crypto", "commodities", "indices"], description: "Optional asset class filter" },
    ],
    sql: `SELECT date_trunc('month', t.close_time)::date AS month,
       COUNT(*) AS trades,
       SUM(t.notional_usd) AS notional_usd,
       SUM(t.commission_usd) AS commission_usd,
       SUM(t.pnl_usd) AS client_pnl_usd,
       COUNT(DISTINCT t.client_id) AS active_clients
FROM trading.trades t
JOIN trading.instruments i USING (symbol)
WHERE t.status = 'closed'
  AND t.close_time::date BETWEEN :start_date AND :end_date
  AND (:asset_class IS NULL OR i.asset_class = :asset_class)
GROUP BY 1
ORDER BY 1`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: { created_at: iso(9), row_count: 3, duration_ms: 61, error: null },
  },
  {
    name: "trading_top_instruments",
    agent: "trading",
    tool_type: "sql",
    title: "Top instruments by commission, volume or client PnL",
    description:
      "Ranks instruments for a date range by notional volume, commission earned, or client PnL. Returns symbol, name, asset class, trades, notional USD, commission USD and client PnL USD.",
    enabled: true,
    params: [
      { name: "start_date", type: "date", required: true, description: "Inclusive start, YYYY-MM-DD", example: "2026-10-01" },
      { name: "end_date", type: "date", required: true, description: "Inclusive end, YYYY-MM-DD", example: "2026-10-31" },
      { name: "metric", type: "string", required: false, default: "commission", enum: ["volume", "commission", "client_pnl"] },
      { name: "limit", type: "integer", required: false, default: 10, min: 1, max: 50 },
    ],
    sql: `SELECT i.symbol, i.name, i.asset_class, COUNT(*) AS trades,
       SUM(t.notional_usd) AS notional_usd,
       SUM(t.commission_usd) AS commission_usd,
       SUM(t.pnl_usd) AS client_pnl_usd
FROM trading.trades t JOIN trading.instruments i USING (symbol)
WHERE t.close_time::date BETWEEN :start_date AND :end_date
GROUP BY 1, 2, 3
ORDER BY CASE :metric WHEN 'volume' THEN SUM(t.notional_usd)
                      WHEN 'client_pnl' THEN SUM(t.pnl_usd)
                      ELSE SUM(t.commission_usd) END DESC
LIMIT :limit`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: { created_at: iso(3), row_count: 5, duration_ms: 44, error: null },
  },
  {
    name: "trading_client_segment_performance",
    agent: "trading",
    tool_type: "sql",
    title: "Client segment performance by country",
    description:
      "Per client segment (retail, pro, vip) and country for a date range: active clients, trades, commission USD, average client PnL and win rate. Optional segment and country filters.",
    enabled: true,
    params: [
      { name: "start_date", type: "date", required: true, example: "2026-07-01", description: "Inclusive start, YYYY-MM-DD" },
      { name: "end_date", type: "date", required: true, example: "2026-09-30", description: "Inclusive end, YYYY-MM-DD" },
      { name: "segment", type: "string", required: false, enum: ["retail", "pro", "vip"] },
      { name: "country", type: "string", required: false, description: "ISO-2 country code, e.g. GB" },
    ],
    sql: `SELECT c.segment, c.country,
       COUNT(DISTINCT c.client_id) AS active_clients,
       COUNT(*) AS trades,
       SUM(t.commission_usd) AS commission_usd,
       ROUND(AVG(t.pnl_usd), 2) AS avg_client_pnl_usd,
       ROUND(100.0 * AVG((t.pnl_usd > 0)::int), 1) AS win_rate_pct
FROM trading.trades t JOIN trading.clients c USING (client_id)
WHERE t.close_time::date BETWEEN :start_date AND :end_date
  AND (:segment IS NULL OR c.segment = :segment)
  AND (:country IS NULL OR c.country = :country)
GROUP BY 1, 2
ORDER BY commission_usd DESC`,
    answer: null,
    source: null,
    updated_at: iso(60 * 26),
    last_run: { created_at: iso(60 * 3), row_count: 0, duration_ms: 70, error: "relation does not exist (mock example of a failed run)" },
  },
  {
    name: "finance_kpi_definitions",
    agent: "finance",
    tool_type: "factual",
    title: "How Nimbus defines its finance KPIs",
    description: "Definitions of net revenue, operating profit and margin as used by Nimbus Markets finance. No arguments. Use when the user asks what a KPI means or how it is calculated.",
    enabled: false,
    params: [],
    sql: null,
    answer:
      "**Net revenue** = trading commission + spread revenue + subscription fees + interest income.\n\n**Operating profit** = net revenue − operating expenses (staff, marketing, technology, office, payment processing, professional fees).\n\n**Margin %** = operating profit ÷ net revenue × 100.",
    source: "Nimbus Finance Handbook §2 (fictional)",
    updated_at: iso(60 * 2),
    last_run: null,
  },
];

export function toolRuns(name: string): ToolRun[] {
  const t = tools.find((x) => x.name === name);
  if (!t?.last_run) return [];
  return Array.from({ length: 4 }, (_, i) => ({
    id: 100 - i,
    name,
    agent: t.agent,
    args: Object.fromEntries(t.params.filter((p) => p.example !== undefined).map((p) => [p.name, p.example])),
    created_at: iso(i * 37 + 3),
    row_count: i === 2 ? 0 : (t.last_run?.row_count ?? 3),
    duration_ms: 30 + i * 11,
    error: i === 2 ? "end_date: expected YYYY-MM-DD" : null,
  }));
}

export function graph(): Graph {
  return {
    agents: [
      { id: "main_agent", label: "Main agent", role: "root", description: "Nimbus assistant persona. Answers small talk itself; sends data and news questions to the orchestrator and writes the final answer.", model: health.router_model },
      { id: "orchestrator", label: "Orchestrator", role: "router", parent: "main_agent", description: "Routes each request to finance, trading and/or news specialists — in parallel when independent.", model: health.router_model },
      { id: "finance_agent", label: "Finance agent", role: "specialist", parent: "orchestrator", datasource: "finance", description: "General ledger, P&L, budgets, FX and entities.", model: health.model },
      { id: "trading_agent", label: "Trading agent", role: "specialist", parent: "orchestrator", datasource: "trading", description: "Clients, trades, instruments, prices and commissions.", model: health.model },
      { id: "news_agent", label: "News agent", role: "specialist", parent: "orchestrator", datasource: "internet", description: "Live market headlines through the news MCP server.", model: health.model },
    ],
    tools: [
      ...tools.filter((t) => t.enabled).map((t) => ({ name: t.name, agent: `${t.agent}_agent`, tool_type: t.tool_type, title: t.title })),
      { name: "latest_headlines", agent: "news_agent", tool_type: "mcp" as const, title: "Latest headlines for a topic" },
      { name: "search_news", agent: "news_agent", tool_type: "mcp" as const, title: "Search news" },
      { name: "list_feeds", agent: "news_agent", tool_type: "mcp" as const, title: "List RSS feeds" },
    ],
    datasources: [
      { id: "finance", label: "finance schema" },
      { id: "trading", label: "trading schema" },
      { id: "internet", label: "Internet (RSS)" },
    ],
  };
}

// ---- schema ------------------------------------------------------------------------------

const c = (name: string, type: string, comment: string, extra: Partial<SchemaColumn> = {}): SchemaColumn => ({
  name,
  type,
  nullable: false,
  pk: false,
  fk: null,
  comment,
  ...extra,
});

export const schemas: Record<SchemaName, SchemaDetail> = {
  finance: {
    name: "finance",
    comment: "Nimbus Markets general ledger, budgets and FX (synthetic).",
    tables: [
      {
        name: "entities",
        comment: "Legal entities of Nimbus Markets (fictional).",
        row_count: 4,
        columns: [
          c("entity_id", "text", "Entity code, e.g. NM-UK", { pk: true }),
          c("name", "text", "Legal name, e.g. Nimbus Markets UK Ltd"),
          c("country", "text", "ISO-2 country of incorporation"),
          c("currency", "character(3)", "Functional currency (ISO 4217)"),
        ],
      },
      {
        name: "accounts",
        comment: "Chart of accounts.",
        row_count: 24,
        columns: [
          c("account_code", "text", "Account code, e.g. 4100", { pk: true }),
          c("account_name", "text", "Account name"),
          c("account_type", "text", "revenue | expense | asset | liability | equity"),
          c("category", "text", "Reporting category, e.g. Trading commission, Staff costs"),
        ],
      },
      {
        name: "fx_rates",
        comment: "Daily FX rates: 1 unit of currency = usd_rate USD.",
        row_count: 2740,
        columns: [
          c("rate_date", "date", "Rate date", { pk: true }),
          c("currency", "character(3)", "ISO 4217 currency", { pk: true }),
          c("usd_rate", "numeric(18,8)", "USD per 1 unit of currency"),
        ],
      },
      {
        name: "gl_entries",
        comment: "General ledger lines. Amounts are positive magnitudes; account_type says revenue vs expense.",
        row_count: 15120,
        columns: [
          c("entry_id", "bigint", "Surrogate key", { pk: true }),
          c("entry_date", "date", "Posting date"),
          c("entity_id", "text", "Booking entity", { fk: { table: "entities", column: "entity_id" } }),
          c("account_code", "text", "GL account", { fk: { table: "accounts", column: "account_code" } }),
          c("amount_local", "numeric(18,2)", "Amount in the entry currency"),
          c("currency", "character(3)", "Entry currency"),
          c("amount_usd", "numeric(18,2)", "Amount converted to USD at the day's rate"),
          c("description", "text", "Free-text memo", { nullable: true }),
        ],
      },
      {
        name: "budgets",
        comment: "Monthly budget per entity and account.",
        row_count: 1728,
        columns: [
          c("month", "date", "First day of the budget month", { pk: true }),
          c("entity_id", "text", "Entity", { pk: true, fk: { table: "entities", column: "entity_id" } }),
          c("account_code", "text", "Account", { pk: true, fk: { table: "accounts", column: "account_code" } }),
          c("budget_usd", "numeric(18,2)", "Budgeted amount in USD"),
        ],
      },
    ],
  },
  trading: {
    name: "trading",
    comment: "Nimbus Markets clients, instruments, trades and prices (synthetic).",
    tables: [
      {
        name: "clients",
        comment: "Trading clients. Names are generated; entity mapping by country (GB→NM-UK, SG/MY→NM-SG, AE→NM-AE, others→NM-INTL).",
        row_count: 600,
        columns: [
          c("client_id", "text", "Client code, e.g. C00042", { pk: true }),
          c("full_name", "text", "Generated full name"),
          c("country", "text", "ISO-2 country of residence"),
          c("segment", "text", "retail | pro | vip"),
          c("signup_date", "date", "Account opening date"),
          c("risk_level", "text", "low | medium | high"),
        ],
      },
      {
        name: "instruments",
        comment: "Tradable instruments. Prices are synthetic random walks.",
        row_count: 16,
        columns: [
          c("symbol", "text", "Symbol, e.g. EURUSD, BTCUSD, XAUUSD, US100", { pk: true }),
          c("name", "text", "Display name"),
          c("asset_class", "text", "forex | crypto | commodities | indices"),
        ],
      },
      {
        name: "trades",
        comment: "Client trades. commission_usd reconciles with GL Trading commission revenue.",
        row_count: 20410,
        columns: [
          c("trade_id", "bigint", "Surrogate key", { pk: true }),
          c("client_id", "text", "Client", { fk: { table: "clients", column: "client_id" } }),
          c("symbol", "text", "Instrument", { fk: { table: "instruments", column: "symbol" } }),
          c("side", "text", "buy | sell"),
          c("quantity", "numeric(18,4)", "Units traded"),
          c("open_price", "numeric(18,6)", "Fill price at open"),
          c("close_price", "numeric(18,6)", "Fill price at close", { nullable: true }),
          c("open_time", "timestamp with time zone", "Open time"),
          c("close_time", "timestamp with time zone", "Close time (null while open)", { nullable: true }),
          c("notional_usd", "numeric(18,2)", "quantity × open_price in USD"),
          c("pnl_usd", "numeric(18,2)", "Client PnL in USD", { nullable: true }),
          c("commission_usd", "numeric(18,2)", "Commission charged in USD"),
          c("status", "text", "open | closed"),
        ],
      },
      {
        name: "daily_prices",
        comment: "Daily OHLCV per instrument (synthetic).",
        row_count: 8768,
        columns: [
          c("symbol", "text", "Instrument", { pk: true, fk: { table: "instruments", column: "symbol" } }),
          c("price_date", "date", "Trading day", { pk: true }),
          c("open", "numeric(18,6)", "Open"),
          c("high", "numeric(18,6)", "High"),
          c("low", "numeric(18,6)", "Low"),
          c("close", "numeric(18,6)", "Close"),
          c("volume", "bigint", "Synthetic volume"),
        ],
      },
    ],
  },
  tools: {
    name: "tools",
    comment: "Tool registry: every row becomes an ADK FunctionTool.",
    tables: [
      {
        name: "tools",
        comment: "Registered tools (sql or factual). Agents reload them on the next question.",
        row_count: tools.length,
        columns: [
          c("name", "text", "Function name the LLM calls; ^[a-z][a-z0-9_]{2,63}$", { pk: true }),
          c("agent", "text", "finance | trading"),
          c("tool_type", "text", "sql | factual"),
          c("title", "text", "Short human title"),
          c("description", "text", "What the LLM reads to decide when to call it"),
          c("sql_text", "text", "Parameterised SELECT (sql tools)", { nullable: true }),
          c("params", "jsonb", "Typed parameters"),
          c("answer_text", "text", "Curated markdown answer (factual tools)", { nullable: true }),
          c("source", "text", "Citation for factual answers", { nullable: true }),
          c("enabled", "boolean", "Disabled tools are hidden from agents"),
          c("created_at", "timestamp with time zone", "Created"),
          c("updated_at", "timestamp with time zone", "Last change (drives hot reload)"),
        ],
      },
      {
        name: "tool_runs",
        comment: "One row per tool execution.",
        row_count: 312,
        columns: [
          c("id", "bigint", "Surrogate key", { pk: true }),
          c("name", "text", "Tool name", { fk: { table: "tools", column: "name" } }),
          c("agent", "text", "Agent that ran it"),
          c("args", "jsonb", "Arguments", { nullable: true }),
          c("row_count", "integer", "Rows returned", { nullable: true }),
          c("duration_ms", "integer", "Execution time", { nullable: true }),
          c("error", "text", "Error message, if any", { nullable: true }),
          c("created_at", "timestamp with time zone", "When it ran"),
        ],
      },
    ],
  },
};

const firsts = ["Ava", "Leo", "Mia", "Noah", "Iris", "Omar", "Zara", "Kai"];
const lasts = ["Hart", "Quill", "Reyes", "Okafor", "Lindqvist", "Tan", "Novak", "Moreau"];

export function sampleRows(schema: SchemaName, table: string, limit: number): { columns: string[]; rows: unknown[][] } {
  const t = schemas[schema]?.tables.find((x) => x.name === table);
  if (!t) return { columns: [], rows: [] };
  const rows = Array.from({ length: limit }, (_, i) =>
    t.columns.map((col) => {
      const n = col.name;
      if (n === "entity_id") return ["NM-UK", "NM-SG", "NM-AE", "NM-INTL"][i % 4];
      if (n === "client_id") return `C${String(42 + i * 7).padStart(5, "0")}`;
      if (n === "full_name") return `${firsts[i % 8]} ${lasts[(i * 3) % 8]}`;
      if (n === "symbol") return ["EURUSD", "BTCUSD", "XAUUSD", "US100", "GBPUSD"][i % 5];
      if (n === "segment") return ["retail", "pro", "vip"][i % 3];
      if (n === "country") return ["GB", "SG", "AE", "DE", "BR"][i % 5];
      if (n === "currency") return ["GBP", "SGD", "AED", "USD"][i % 4];
      if (n === "name" && table === "entities") return ["Nimbus Markets UK Ltd", "Nimbus Markets SG Pte", "Nimbus Markets AE", "Nimbus Markets Intl"][i % 4];
      if (col.type.startsWith("timestamp")) return `2026-09-${String(10 + i).padStart(2, "0")}T0${i}:15:00Z`;
      if (col.type === "date") return `2026-09-${String(1 + i).padStart(2, "0")}`;
      if (col.type.startsWith("numeric")) return Math.round((1000 + i * 137.31) * 100) / 100;
      if (col.type === "bigint" || col.type === "integer") return 1000 + i;
      if (col.type === "boolean") return i % 2 === 0;
      if (col.type === "jsonb") return { start_date: "2026-07-01" };
      if (n === "side") return i % 2 ? "sell" : "buy";
      if (n === "status") return "closed";
      if (n === "account_type") return ["revenue", "expense"][i % 2];
      if (n === "category") return ["Trading commission", "Staff costs", "Spread revenue", "Marketing", "Technology"][i % 5];
      return `${n}_${i + 1}`;
    }),
  );
  return { columns: t.columns.map((x) => x.name), rows };
}
