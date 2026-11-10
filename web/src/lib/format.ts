export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return "–";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
  const m = Math.floor(ms / 60_000);
  return `${m}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export function formatCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return "–";
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  const s = Math.round(diff / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d} d ago`;
  return new Date(t).toLocaleDateString();
}

export function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "NULL";
  if (typeof v === "number") {
    return Number.isInteger(v) ? new Intl.NumberFormat("en-US").format(v) : new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(v);
  }
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** One-line summary of tool args, e.g. `start_date=2026-07-01, metric=commission`. */
export function summarizeArgs(args: Record<string, unknown> | null | undefined, max = 90): string {
  if (!args) return "";
  const keys = Object.keys(args);
  if (keys.length === 1 && keys[0] === "request") {
    const s = String(args.request ?? "");
    return s.length > max ? `${s.slice(0, max - 1)}…` : s;
  }
  const s = keys.map((k) => `${k}=${typeof args[k] === "string" ? args[k] : JSON.stringify(args[k])}`).join(", ");
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}
