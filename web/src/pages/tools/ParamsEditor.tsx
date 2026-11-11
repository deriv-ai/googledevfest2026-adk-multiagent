import { useEffect, useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { PARAM_TYPES, type ParamType, type ParamValue } from "@/api/types";
import { coerceParamValue, type ParamRow } from "@/lib/placeholders";
import { Button, Input, Select } from "@/components/ui";
import { cn } from "@/lib/utils";

/** Text input that keeps what the user types and commits a parsed value on blur. */
function CommitInput({ value, toText, parse, onCommit, ...rest }: { value: unknown; toText: (v: unknown) => string; parse: (s: string) => unknown; onCommit: (v: unknown) => void } & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const [text, setText] = useState(() => toText(value));
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    if (!focused) setText(toText(value));
  }, [value, focused, toText]);
  return (
    <Input
      {...rest}
      value={text}
      onFocus={() => setFocused(true)}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        setFocused(false);
        onCommit(parse(text));
      }}
    />
  );
}

const valText = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const enumText = (v: unknown) => (Array.isArray(v) ? v.join(", ") : "");
const numText = valText;

export function ParamsEditor({ rows, orphans, onChange, sqlEmpty }: { rows: ParamRow[]; orphans: string[]; onChange: (rows: ParamRow[]) => void; sqlEmpty: boolean }) {
  const update = (i: number, patch: Partial<ParamRow>) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch, _pristine: false } : r)));
  const remove = (i: number) => onChange(rows.filter((_, j) => j !== i));

  if (!rows.length)
    return (
      <div className="rounded-xl border border-dashed border-input/70 px-5 py-6 text-sm text-muted-foreground">
        {sqlEmpty ? (
          <>Parameters appear here automatically as you type <code className="rounded bg-muted px-1 font-mono">:placeholders</code> in the SQL.</>
        ) : (
          <>
            This query has no <code className="rounded bg-muted px-1 font-mono">:placeholders</code>, so the function takes no arguments. Add e.g.{" "}
            <code className="rounded bg-muted px-1 font-mono">WHERE entry_date &gt;= :start_date</code> to let the LLM pass values in.
          </>
        )}
      </div>
    );

  return (
    <ul className="space-y-3">
      {rows.map((r, i) => {
        const orphan = orphans.includes(r.name);
        const numeric = r.type === "integer" || r.type === "number";
        const id = `p-${r.name}`;
        return (
          <li key={r.name} className={cn("rounded-xl border bg-card p-4", orphan ? "border-warning/60" : "border-border")}>
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <code className="rounded-md bg-muted px-2 py-1 font-mono text-sm font-semibold">:{r.name}</code>
              {orphan ? (
                <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-warning">
                  <AlertTriangle className="size-3.5" aria-hidden /> Not used in the SQL. Remove it, or add <code className="font-mono">:{r.name}</code> back.
                </span>
              ) : r._pristine ? (
                <span className="text-xs text-muted-foreground">added from the SQL · type guessed from the name</span>
              ) : null}
              <div className="ml-auto flex items-center gap-3">
                <label className="flex items-center gap-2 text-[13px] font-medium">
                  <input type="checkbox" className="size-4 accent-[hsl(var(--ring))]" checked={!!r.required} onChange={(e) => update(i, { required: e.target.checked })} />
                  Required
                </label>
                {orphan ? (
                  <Button size="sm" variant="ghost" className="text-danger hover:bg-danger/10 hover:text-danger" onClick={() => remove(i)}>
                    <Trash2 className="size-3.5" aria-hidden /> Remove
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
              <Field label="Type" htmlFor={`${id}-type`} className="col-span-1">
                <Select id={`${id}-type`} value={r.type} onChange={(e) => update(i, { type: e.target.value as ParamType })}>
                  {PARAM_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Description" htmlFor={`${id}-desc`} className="col-span-2 md:col-span-5">
                <Input
                  id={`${id}-desc`}
                  value={r.description ?? ""}
                  onChange={(e) => update(i, { description: e.target.value })}
                  placeholder={r.type === "date" ? "e.g. Inclusive start date, YYYY-MM-DD" : "What the value means, units, accepted values"}
                />
              </Field>
              <Field label={r.required ? "Example (used by Test run)" : "Example"} htmlFor={`${id}-ex`} className="col-span-1 md:col-span-2">
                <CommitInput
                  id={`${id}-ex`}
                  value={r.example}
                  toText={valText}
                  parse={(s) => coerceParamValue(r.type, s)}
                  onCommit={(v) => update(i, { example: v as ParamValue | null })}
                  placeholder={r.type === "date" ? "2026-07-01" : r.type === "boolean" ? "true" : ""}
                  aria-invalid={r.required && (r.example === null || r.example === undefined || r.example === "") ? true : undefined}
                  className="font-mono"
                />
              </Field>
              <Field label="Default" htmlFor={`${id}-def`} className="col-span-1 md:col-span-1">
                <CommitInput id={`${id}-def`} value={r.default} toText={valText} parse={(s) => coerceParamValue(r.type, s)} onCommit={(v) => update(i, { default: v as ParamValue | null })} className="font-mono" />
              </Field>
              {numeric ? (
                <>
                  <Field label="Min" htmlFor={`${id}-min`}>
                    <CommitInput id={`${id}-min`} inputMode="decimal" value={r.min} toText={numText} parse={(s) => (s.trim() === "" || Number.isNaN(Number(s)) ? null : Number(s))} onCommit={(v) => update(i, { min: v as number | null })} className="font-mono" />
                  </Field>
                  <Field label="Max" htmlFor={`${id}-max`}>
                    <CommitInput id={`${id}-max`} inputMode="decimal" value={r.max} toText={numText} parse={(s) => (s.trim() === "" || Number.isNaN(Number(s)) ? null : Number(s))} onCommit={(v) => update(i, { max: v as number | null })} className="font-mono" />
                  </Field>
                </>
              ) : (
                <Field label="Allowed values (comma-separated)" htmlFor={`${id}-enum`} className="col-span-2 md:col-span-3">
                  <CommitInput
                    id={`${id}-enum`}
                    value={r.enum}
                    toText={enumText}
                    parse={(s) =>
                      s
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean)
                        .map((x) => coerceParamValue(r.type, x))
                        .filter((x): x is ParamValue => x !== null)
                    }
                    onCommit={(v) => update(i, { enum: (v as ParamValue[]).length ? (v as ParamValue[]) : null })}
                    placeholder={r.type === "string" ? "e.g. volume, commission, client_pnl" : ""}
                    disabled={r.type === "boolean"}
                    className="font-mono"
                  />
                </Field>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Field({ label, htmlFor, children, className }: { label: string; htmlFor: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
