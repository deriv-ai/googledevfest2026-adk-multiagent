import { formatCell } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ResultTable({ columns, rows, className, maxHeight = "24rem", compact }: { columns: string[]; rows: unknown[][]; className?: string; maxHeight?: string; compact?: boolean }) {
  if (!columns.length) return <p className="text-sm text-muted-foreground">No columns returned.</p>;
  return (
    <div className={cn("overflow-auto rounded-lg border border-border", className)} style={{ maxHeight }}>
      <table className="w-full border-collapse text-left text-[13px]">
        <thead className="sticky top-0 z-10 bg-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} className={cn("font-mono font-medium whitespace-nowrap text-muted-foreground", compact ? "px-2.5 py-1.5 text-xs" : "px-3 py-2")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                The query ran but returned no rows.
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={i} className="border-t border-border hover:bg-muted/40">
                {r.map((v, j) => (
                  <td
                    key={j}
                    className={cn(
                      "max-w-[28rem] truncate whitespace-nowrap",
                      compact ? "px-2.5 py-1.5" : "px-3 py-2",
                      typeof v === "number" && "text-right font-mono",
                      (v === null || v === undefined) && "text-muted-foreground/70 italic",
                    )}
                    title={formatCell(v)}
                  >
                    {formatCell(v)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
