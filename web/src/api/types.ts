// Mirrors docs/CONTRACT.md. Keep in sync when the contract changes.

// ---- Health / graph -----------------------------------------------------------------

export interface Health {
  ok: boolean;
  db: "ok" | "error";
  llm_key: "configured" | "missing";
  /** How the backend reaches the model (never the URL itself). */
  llm_mode?: "proxy" | "direct";
  model: string;
  router_model: string;
}

export type AgentRole = "root" | "router" | "specialist";
export type DatasourceId = "finance" | "trading" | "marketing" | (string & {});

export interface GraphAgent {
  id: string;
  label: string;
  role: AgentRole;
  description?: string;
  model?: string;
  parent?: string;
  datasource?: DatasourceId;
}

export type GraphToolType = "sql" | "factual" | "function";

export interface GraphTool {
  name: string;
  agent: string;
  tool_type: GraphToolType;
  title: string;
}

export interface GraphDatasource {
  id: DatasourceId;
  label: string;
}

export interface Graph {
  agents: GraphAgent[];
  tools: GraphTool[];
  datasources: GraphDatasource[];
}

// ---- Chat SSE -----------------------------------------------------------------------

export type ToolKind = "agent" | "sql" | "factual" | "function";

interface EventBase {
  ts?: number;
}

export interface StartEvent extends EventBase {
  type: "start";
  conversation_id: string;
}
export interface AgentStartEvent extends EventBase {
  type: "agent_start";
  agent: string;
  invocation_id?: string;
}
export interface AgentEndEvent extends EventBase {
  type: "agent_end";
  agent: string;
  invocation_id?: string;
  ms?: number | null;
}
export interface ToolCallEvent extends EventBase {
  type: "tool_call";
  agent: string;
  tool: string;
  call_id: string;
  args?: Record<string, unknown> | null;
  kind: ToolKind;
}
export interface ToolResultEvent extends EventBase {
  type: "tool_result";
  agent: string;
  tool: string;
  call_id: string;
  ms?: number | null;
  kind: ToolKind;
  ok: boolean;
  row_count?: number | null;
  error?: string | null;
  preview?: unknown;
}
export interface AnswerEvent extends EventBase {
  type: "answer";
  text: string;
  route?: string[];
  elapsed_ms?: number;
}
/** The next chunk of the main agent's answer, as the model writes it. */
export interface AnswerDeltaEvent {
  type: "answer_delta";
  text: string;
  ts?: number;
}
export interface ErrorEvent extends EventBase {
  type: "error";
  message: string;
}

export type ChatEvent =
  | StartEvent
  | AgentStartEvent
  | AgentEndEvent
  | ToolCallEvent
  | ToolResultEvent
  | AnswerDeltaEvent
  | AnswerEvent
  | ErrorEvent;

export interface ChatExample {
  label: string;
  prompt: string;
}

// ---- Tools --------------------------------------------------------------------------

export type ToolAgent = "finance" | "trading";
export type ToolType = "sql" | "factual";
export type ParamType = "date" | "string" | "integer" | "number" | "boolean";
export const PARAM_TYPES: ParamType[] = ["date", "string", "integer", "number", "boolean"];

export type ParamValue = string | number | boolean;

export interface ToolParam {
  name: string;
  type: ParamType;
  required?: boolean;
  description?: string;
  example?: ParamValue | null;
  default?: ParamValue | null;
  enum?: ParamValue[] | null;
  min?: number | null;
  max?: number | null;
}

/** The body for POST /api/tools, PUT /api/tools/{name} and POST /api/tools/test. */
export interface ToolSpec {
  name: string;
  agent: ToolAgent;
  tool_type: ToolType;
  title: string;
  description: string;
  params: ToolParam[];
  sql?: string | null;
  answer?: string | null;
  source?: string | null;
  enabled?: boolean;
}

export interface ToolRunSummary {
  created_at: string;
  row_count: number | null;
  duration_ms: number | null;
  error: string | null;
}

export interface ToolRun extends ToolRunSummary {
  id?: number;
  name?: string;
  agent?: string;
  args?: Record<string, unknown> | null;
}

export interface Tool extends ToolSpec {
  enabled: boolean;
  updated_at: string;
  created_at?: string;
  last_run: ToolRunSummary | null;
}

export interface ToolDetail extends Tool {
  runs: ToolRun[];
}

export interface FunctionDeclaration {
  name: string;
  description: string;
  parameters?: Record<string, unknown> | null;
}

export interface SqlTestResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  duration_ms: number;
}

export interface FactualTestResult {
  answer: string;
  source: string | null;
}

export interface ToolTestResponse {
  ok: boolean;
  errors: string[];
  declaration: FunctionDeclaration | null;
  result: SqlTestResult | FactualTestResult | null;
}

export function isSqlResult(r: ToolTestResponse["result"]): r is SqlTestResult {
  return !!r && Array.isArray((r as SqlTestResult).columns);
}

// ---- Schema -------------------------------------------------------------------------

export type SchemaName = "finance" | "trading" | "marketing" | "tools";

export interface SchemaSummary {
  name: SchemaName;
  comment: string | null;
}

export interface ColumnFk {
  table: string;
  column: string;
  /** Optional: present when the FK points into another schema. */
  schema?: string;
}

export interface SchemaColumn {
  name: string;
  type: string;
  nullable: boolean;
  pk: boolean;
  fk: ColumnFk | null;
  comment: string | null;
}

export interface SchemaTable {
  name: string;
  comment: string | null;
  row_count: number | null;
  columns: SchemaColumn[];
}

export interface SchemaDetail {
  name: SchemaName;
  comment: string | null;
  tables: SchemaTable[];
}

export interface SampleRows {
  columns: string[];
  rows: unknown[][];
}
