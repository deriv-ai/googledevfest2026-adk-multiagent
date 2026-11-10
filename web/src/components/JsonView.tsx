import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Pretty-printed, syntax-highlighted JSON without a dependency. */
export function JsonView({ value, className }: { value: unknown; className?: string }) {
  const text = JSON.stringify(value, null, 2) ?? "null";
  return (
    <pre className={cn("overflow-auto rounded-lg border border-border bg-muted/50 p-4 text-[13px] leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]", className)}>
      <code>{highlight(text)}</code>
    </pre>
  );
}

const TOKEN = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

function highlight(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let i = 0;
  for (const m of text.matchAll(TOKEN)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push(<Fragment key={i++}>{text.slice(last, idx)}</Fragment>);
    if (m[1]) {
      out.push(
        <span key={i++} className={m[2] ? "json-key" : "json-string"}>
          {m[1]}
        </span>,
      );
      if (m[2]) out.push(<Fragment key={i++}>{m[2]}</Fragment>);
    } else if (m[3]) out.push(<span key={i++} className="json-literal">{m[3]}</span>);
    else if (m[4]) out.push(<span key={i++} className="json-number">{m[4]}</span>);
    last = idx + m[0].length;
  }
  if (last < text.length) out.push(<Fragment key={i++}>{text.slice(last)}</Fragment>);
  return out;
}
