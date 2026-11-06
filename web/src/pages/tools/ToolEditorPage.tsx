import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { EditorView } from "@codemirror/view";
import { AlertTriangle, ArrowLeft, CheckCircle2, CircleDashed, Database, FileText, FlaskConical, Save } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { useSaveTool, useSchema, useTestTool, useTool } from "@/api/hooks";
import { isSqlResult, type ToolAgent, type ToolSpec, type ToolTestResponse, type ToolType } from "@/api/types";
import { JsonView } from "@/components/JsonView";
import { Markdown } from "@/components/Markdown";
import { ResultTable } from "@/components/ResultTable";
import { SqlEditor } from "@/components/SqlEditor";
import { ErrorState } from "@/components/States";
import { Button, Input, Label, Panel, Segmented, Select, Skeleton, Textarea } from "@/components/ui";
import { agentMeta, toneColor, toolAgentId } from "@/lib/agents";
import { formatMs } from "@/lib/format";
import { cleanParams, syncParams, TOOL_NAME_RE, type ParamRow } from "@/lib/placeholders";
import { cn, stableStringify } from "@/lib/utils";
import { ParamsEditor } from "./ParamsEditor";
import { SchemaBrowser } from "./SchemaBrowser";

interface FormState {
  name: string;
  agent: ToolAgent;
  tool_type: ToolType;
  title: string;
  description: string;
  sql: string;
  params: ParamRow[];
  answer: string;
  source: string;
  enabled: boolean;
}

const EMPTY: FormState = { name: "", agent: "finance", tool_type: "sql", title: "", description: "", sql: "", params: [], answer: "", source: "", enabled: true };

function toSpec(f: FormState): ToolSpec {
  const base = { name: f.name.trim(), agent: f.agent, tool_type: f.tool_type, title: f.title.trim(), description: f.description.trim(), enabled: f.enabled };
  return f.tool_type === "sql" ? { ...base, params: cleanParams(f.params), sql: f.sql } : { ...base, params: [], answer: f.answer, source: f.source.trim() };
}

export default function ToolEditorPage() {
  const { name: editName } = useParams();
  const isEdit = !!editName;
  const existing = useTool(editName);

  if (isEdit && existing.isLoading)
    return (
      <div className="mx-auto max-w-[1400px] space-y-4 px-6 py-8 lg:px-10">
        <Skeleton className="h-8 w-80" />
        <Skeleton className="h-[480px] w-full rounded-xl" />
      </div>
    );
  if (isEdit && (existing.isError || !existing.data))
    return (
      <div className="mx-auto max-w-3xl px-6 py-8">
        <ErrorState error={existing.error ?? "Tool not found"} onRetry={() => void existing.refetch()} />
      </div>
    );

  const initial: FormState = existing.data
    ? {
        name: existing.data.name,
        agent: existing.data.agent,
        tool_type: existing.data.tool_type,
        title: existing.data.title,
        description: existing.data.description,
        sql: existing.data.sql ?? "",
        params: existing.data.params.map((p) => ({ ...p, _pristine: false })),
        answer: existing.data.answer ?? "",
        source: existing.data.source ?? "",
        enabled: existing.data.enabled,
      }
    : EMPTY;
  return <Editor key={editName ?? "new"} initial={initial} editName={editName} />;
}

function Editor({ initial, editName }: { initial: FormState; editName?: string }) {
  const navigate = useNavigate();
  const [f, setF] = useState<FormState>(initial);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [answerTab, setAnswerTab] = useState<"write" | "preview">("write");
  const [test, setTest] = useState<{ hash: string; res: ToolTestResponse } | null>(null);
  const [saveErrors, setSaveErrors] = useState<string[]>([]);
  const viewRef = useRef<EditorView | null>(null);
  const testMut = useTestTool();
  const saveMut = useSaveTool(editName);
  const schemaQ = useSchema(f.agent);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((s) => ({ ...s, [k]: v }));

  // Keep params in sync with :placeholders (debounced so typing doesn't thrash).
  useEffect(() => {
    if (f.tool_type !== "sql") return;
    const t = setTimeout(() => {
      setF((s) => {
        const r = syncParams(s.sql, s.params);
        return r.changed ? { ...s, params: r.rows } : s;
      });
    }, 350);
    return () => clearTimeout(t);
  }, [f.sql, f.tool_type]);
  const orphans = useMemo(() => syncParams(f.sql, f.params).orphans, [f.sql, f.params]);

  const spec = useMemo(() => toSpec(f), [f]);
  const hash = useMemo(() => stableStringify(spec), [spec]);

  const nameError = !f.name ? "Required." : !TOOL_NAME_RE.test(f.name) ? "Use snake_case: start with a letter; 3–64 characters of a–z, 0–9 and _." : null;
  const problems: string[] = [];
  if (nameError) problems.push("name");
  if (!f.title.trim()) problems.push("title");
  if (!f.description.trim()) problems.push("description");
  if (f.tool_type === "sql" && !f.sql.trim()) problems.push("SQL");
  if (f.tool_type === "factual" && !f.answer.trim()) problems.push("answer");
  if (f.tool_type === "factual" && !f.source.trim()) problems.push("source");
  if (f.tool_type === "sql" && orphans.length) problems.push("unused params");

  const testedCurrent = !!test && test.hash === hash;
  const canSave = testedCurrent && test!.res.ok && problems.length === 0;

  const runTest = useCallback(() => {
    setTouched({ name: true, title: true, description: true, sql: true, answer: true, source: true });
    // Flush the param sync first so the test sees exactly what will be saved.
    const synced = f.tool_type === "sql" ? syncParams(f.sql, f.params).rows : f.params;
    const next = { ...f, params: synced };
    if (synced !== f.params) setF(next);
    const s = toSpec(next);
    const h = stableStringify(s);
    testMut.mutate(s, {
      onSuccess: (res) => setTest({ hash: h, res }),
      onError: (e) => setTest({ hash: h, res: { ok: false, errors: [e.message, ...(e instanceof ApiError ? e.errors : [])], declaration: null, result: null } }),
    });
  }, [f, testMut]);

  const save = () => {
    setSaveErrors([]);
    saveMut.mutate(spec, {
      onSuccess: (t) => {
        toast.success(editName ? `Saved ${spec.name}` : `Created ${spec.name}`, { description: `The ${spec.agent} agent will use it from the next question.` });
        navigate(`/tools/${encodeURIComponent(t?.name ?? spec.name)}`);
      },
      onError: (e) => {
        const errs = e instanceof ApiError ? e.errors : [];
        setSaveErrors([e.message, ...errs]);
        toast.error(`Couldn't save: ${e.message}`);
      },
    });
  };

  const insert = (text: string) => {
    const v = viewRef.current;
    if (!v) {
      set("sql", f.sql ? `${f.sql}${text}` : text);
      return;
    }
    v.dispatch(v.state.replaceSelection(text));
    v.focus();
  };

  const meta = agentMeta(toolAgentId(f.agent));

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-8 lg:px-10">
      <Link to={editName ? `/tools/${encodeURIComponent(editName)}` : "/tools"} className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> {editName ? "Back to tool" : "All tools"}
      </Link>
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-semibold tracking-tight">{editName ? <>Edit <span className="font-mono">{editName}</span></> : "New tool"}</h1>
          <p className="mt-1 max-w-[70ch] text-[15px] text-muted-foreground">Describe it, write it, test it. Save unlocks once a test of exactly this version passes.</p>
        </div>
      </header>

      <div className={cn("grid gap-8", f.tool_type === "sql" && "xl:grid-cols-[minmax(0,1fr)_360px]")}>
        <div className="min-w-0 space-y-7">
          {/* Identity */}
          <Panel className="space-y-5 p-5">
            <div className="grid gap-5 md:grid-cols-[minmax(0,1fr)_200px]">
              <div>
                <Label htmlFor="name" hint={editName ? "Name can't change after creation" : "snake_case: what the LLM calls"}>
                  Function name
                </Label>
                <Input
                  id="name"
                  value={f.name}
                  readOnly={!!editName}
                  onChange={(e) => set("name", e.target.value.toLowerCase().replace(/[\s-]+/g, "_"))}
                  onBlur={() => setTouched((t) => ({ ...t, name: true }))}
                  placeholder={`${f.agent}_fx_rates`}
                  className="h-10 font-mono text-[15px]"
                  aria-invalid={touched.name && !!nameError ? true : undefined}
                  aria-describedby="name-err"
                  autoFocus={!editName}
                />
                {touched.name && nameError ? (
                  <p id="name-err" className="mt-1 text-[12.5px] text-danger">
                    {nameError}
                  </p>
                ) : null}
              </div>
              <div>
                <Label htmlFor="agent">Agent</Label>
                <Select id="agent" value={f.agent} onChange={(e) => set("agent", e.target.value as ToolAgent)} className="h-10">
                  <option value="finance">Finance agent</option>
                  <option value="trading">Trading agent</option>
                </Select>
              </div>
            </div>

            <div>
              <Label>Tool type</Label>
              <Segmented
                value={f.tool_type}
                onChange={(v) => set("tool_type", v)}
                options={[
                  { value: "sql", label: <><Database className="size-4" aria-hidden /> SQL query</> },
                  { value: "factual", label: <><FileText className="size-4" aria-hidden /> Factual answer</> },
                ]}
              />
              <p className="mt-1.5 text-[13px] text-muted-foreground">
                {f.tool_type === "sql"
                  ? `A parameterised SELECT over the ${f.agent} schema. Each :placeholder becomes a typed argument.`
                  : "A fixed, curated answer (definitions, policies, calendars). The function takes no arguments."}
              </p>
            </div>

            <div>
              <Label htmlFor="title" hint="Short, for humans">
                Title
              </Label>
              <Input id="title" value={f.title} onChange={(e) => set("title", e.target.value)} onBlur={() => setTouched((t) => ({ ...t, title: true }))} placeholder="Daily FX rates for a currency" aria-invalid={touched.title && !f.title.trim() ? true : undefined} />
            </div>

            <div>
              <Label htmlFor="description" hint={`${f.description.length} chars`}>
                Description
              </Label>
              <Textarea
                id="description"
                rows={3}
                value={f.description}
                onChange={(e) => set("description", e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, description: true }))}
                placeholder="Returns the USD rate per day for one currency between two dates. Use for FX conversion and currency-trend questions."
                aria-invalid={touched.description && !f.description.trim() ? true : undefined}
                aria-describedby="desc-help"
              />
              <p id="desc-help" className="mt-1.5 text-[13px] text-muted-foreground">
                This is what the LLM reads. Say what it returns, the units, and when to use it.
              </p>
            </div>
          </Panel>

          {f.tool_type === "sql" ? (
            <>
              <section>
                <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-[16px] font-semibold">SQL</h2>
                  <span className="text-[13px] text-muted-foreground">
                    One SELECT/WITH over <code className="font-mono">{f.agent}.*</code> · <code className="font-mono">:name</code> placeholders · optional params arrive as NULL
                  </span>
                </div>
                <SqlEditor
                  value={f.sql}
                  onChange={(v) => set("sql", v)}
                  schema={schemaQ.data}
                  minHeight="260px"
                  maxHeight="520px"
                  onCreateEditor={(view) => {
                    viewRef.current = view;
                  }}
                  placeholder={`SELECT rate_date, usd_rate\nFROM finance.fx_rates\nWHERE currency = :currency\n  AND rate_date BETWEEN :start_date AND :end_date\nORDER BY rate_date`}
                />
              </section>
              <section>
                <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-[16px] font-semibold">Parameters</h2>
                  <span className="text-[13px] text-muted-foreground">Synced from the SQL. Required params need an example for the test run.</span>
                </div>
                <ParamsEditor rows={f.params} orphans={orphans} onChange={(rows) => set("params", rows)} sqlEmpty={!f.sql.trim()} />
              </section>
            </>
          ) : (
            <section className="space-y-4">
              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-[16px] font-semibold">Answer</h2>
                  <Segmented
                    size="sm"
                    value={answerTab}
                    onChange={setAnswerTab}
                    options={[
                      { value: "write", label: "Write" },
                      { value: "preview", label: "Preview" },
                    ]}
                  />
                </div>
                {answerTab === "write" ? (
                  <Textarea
                    rows={12}
                    value={f.answer}
                    onChange={(e) => set("answer", e.target.value)}
                    className="font-mono text-[13.5px]"
                    placeholder={"**Net revenue** = trading commission + spread revenue + subscription fees + interest income.\n\n**Operating profit** = net revenue − operating expenses."}
                    aria-label="Answer (markdown)"
                  />
                ) : (
                  <Panel className="min-h-[200px] px-5 py-4">{f.answer.trim() ? <Markdown>{f.answer}</Markdown> : <p className="text-sm text-muted-foreground">Nothing to preview yet.</p>}</Panel>
                )}
                <p className="mt-1.5 text-[13px] text-muted-foreground">Markdown. The agent quotes this verbatim, so keep it factual and self-contained.</p>
              </div>
              <div>
                <Label htmlFor="source" hint="Shown with the answer">
                  Source
                </Label>
                <Input id="source" value={f.source} onChange={(e) => set("source", e.target.value)} placeholder="Nimbus Finance Handbook §2" />
              </div>
            </section>
          )}

          {/* Test + save bar */}
          <div className="sticky bottom-0 z-20 -mx-2 rounded-xl border border-border bg-card/95 px-4 py-3 shadow-[0_-6px_24px_-12px_rgb(0_0_0/0.25)] backdrop-blur">
            <div className="flex flex-wrap items-center gap-3">
              <Button size="lg" variant="outline" onClick={runTest} loading={testMut.isPending}>
                {!testMut.isPending ? <FlaskConical className="size-4" aria-hidden /> : null} Test run
              </Button>
              <Button size="lg" variant="primary" onClick={save} disabled={!canSave} loading={saveMut.isPending}>
                {!saveMut.isPending ? <Save className="size-4" aria-hidden /> : null} {editName ? "Save changes" : "Save tool"}
              </Button>
              <TestStatus test={test} current={testedCurrent} problems={problems} pending={testMut.isPending} />
            </div>
          </div>

          {saveErrors.length ? <ErrorList title="The server rejected the save" errors={saveErrors} /> : null}
          {test ? <TestResults res={test.res} stale={!testedCurrent} /> : null}
        </div>

        {f.tool_type === "sql" ? (
          <aside className="min-w-0">
            <Panel className="flex max-h-[calc(100dvh-8rem)] flex-col overflow-hidden xl:sticky xl:top-6">
              <div className="h-1 shrink-0" style={{ background: toneColor(meta.tone) }} aria-hidden />
              <SchemaBrowser schema={f.agent} onInsert={insert} />
            </Panel>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function TestStatus({ test, current, problems, pending }: { test: { res: ToolTestResponse } | null; current: boolean; problems: string[]; pending: boolean }) {
  let icon = <CircleDashed className="size-4 text-muted-foreground" aria-hidden />;
  let text: React.ReactNode = "Run a test to unlock Save.";
  if (pending) text = "Testing…";
  else if (test && !current) {
    icon = <AlertTriangle className="size-4 text-warning" aria-hidden />;
    text = "You changed the tool since the last test. Test again to save.";
  } else if (test && !test.res.ok) {
    icon = <AlertTriangle className="size-4 text-danger" aria-hidden />;
    text = `Test failed with ${test.res.errors.length} problem${test.res.errors.length === 1 ? "" : "s"}. Fix ${test.res.errors.length === 1 ? "it" : "them"} and test again.`;
  } else if (test && problems.length) {
    icon = <AlertTriangle className="size-4 text-warning" aria-hidden />;
    text = `Test passed, but fix: ${problems.join(", ")}.`;
  } else if (test) {
    icon = <CheckCircle2 className="size-4 text-success" aria-hidden />;
    text = "Test passed. Ready to save.";
  }
  return (
    <span className="flex min-w-0 items-center gap-2 text-[13.5px]" aria-live="polite">
      {icon}
      <span>{text}</span>
    </span>
  );
}

function ErrorList({ title, errors }: { title: string; errors: string[] }) {
  return (
    <div role="alert" className="rounded-xl border border-danger/30 bg-danger/6 p-4">
      <div className="mb-1.5 flex items-center gap-2 font-semibold text-danger">
        <AlertTriangle className="size-4" aria-hidden /> {title}
      </div>
      <ul className="list-disc space-y-0.5 pl-6 text-[14px]">
        {[...new Set(errors)].map((e) => (
          <li key={e} className="font-mono text-[13px]">
            {e}
          </li>
        ))}
      </ul>
    </div>
  );
}

function TestResults({ res, stale }: { res: ToolTestResponse; stale: boolean }) {
  return (
    <div className={cn("space-y-6 transition-opacity", stale && "opacity-60")}>
      {!res.ok && res.errors.length ? <ErrorList title="Test failed" errors={res.errors} /> : null}
      <div className="grid gap-6 2xl:grid-cols-2">
        <section className="min-w-0">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[16px] font-semibold">Result</h2>
            {res.result && isSqlResult(res.result) ? (
              <span className="text-[13px] text-muted-foreground">
                {res.result.row_count} row{res.result.row_count === 1 ? "" : "s"}
                {res.result.truncated ? " (truncated)" : ""} · {formatMs(res.result.duration_ms)} · ran with the params' example/default values
              </span>
            ) : null}
          </div>
          {!res.result ? (
            <p className="rounded-xl border border-dashed border-border px-5 py-6 text-sm text-muted-foreground">No result: the tool didn't run.</p>
          ) : isSqlResult(res.result) ? (
            <ResultTable columns={res.result.columns} rows={res.result.rows} maxHeight="22rem" />
          ) : (
            <Panel className="px-5 py-4">
              <Markdown>{res.result.answer}</Markdown>
              {res.result.source ? <p className="mt-3 border-t border-border pt-2 text-[13px] text-muted-foreground">Source: {res.result.source}</p> : null}
            </Panel>
          )}
        </section>
        <section className="min-w-0">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-[16px] font-semibold">What the LLM sees</h2>
            <span className="text-[13px] text-muted-foreground">The function declaration ADK sends to the model</span>
          </div>
          {res.declaration ? <JsonView value={res.declaration} className="max-h-[22rem]" /> : <p className="rounded-xl border border-dashed border-border px-5 py-6 text-sm text-muted-foreground">No declaration: fix the errors above first.</p>}
        </section>
      </div>
    </div>
  );
}
