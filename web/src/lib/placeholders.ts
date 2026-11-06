import type { ParamType, ToolParam } from "@/api/types";

/** Same rule as the backend (contract): `:name` is a placeholder, `::cast` is not. */
export const PLACEHOLDER_RE = /(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)/g;

/** Unique placeholder names in order of first appearance. */
export function extractPlaceholders(sql: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const m of sql.matchAll(PLACEHOLDER_RE)) {
    const name = m[1]!;
    if (!seen.has(name)) {
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/** A params-editor row. `_pristine` marks a row the editor added itself and the user hasn't touched. */
export type ParamRow = ToolParam & { _pristine?: boolean };

export function guessParamType(name: string): ParamType {
  const n = name.toLowerCase();
  if (/(^|_)(date|day|month|from|to|start|end|since|until)($|_)/.test(n) || n.endsWith("_at") || n.endsWith("_on")) return "date";
  if (/(^|_)(limit|count|top|n|days|months|year|offset)($|_)/.test(n)) return "integer";
  if (/(^|_)(amount|min|max|threshold|rate|pct|percent)($|_)/.test(n)) return "number";
  if (/^(is|has|include|only)_/.test(n)) return "boolean";
  return "string";
}

export function newParamRow(name: string): ParamRow {
  return { name, type: guessParamType(name), required: true, description: "", example: null, default: null, enum: null, min: null, max: null, _pristine: true };
}

export interface ParamSync {
  rows: ParamRow[];
  /** Declared params with no matching placeholder (the backend rejects these). */
  orphans: string[];
  /** Placeholders that just got a new row. */
  added: string[];
  changed: boolean;
}

/**
 * Bring the params list in line with the SQL:
 *  - every new placeholder gets a row (type guessed from its name);
 *  - rows the editor added and the user never touched disappear when their
 *    placeholder does (so typing `:start_d…ate` doesn't leave debris);
 *  - rows the user edited are kept and reported as orphans instead.
 * Order follows the SQL; orphans go last.
 */
export function syncParams(sql: string, rows: ParamRow[]): ParamSync {
  const names = extractPlaceholders(sql);
  const nameSet = new Set(names);
  const byName = new Map(rows.map((r) => [r.name, r] as const));
  const added: string[] = [];
  const next: ParamRow[] = [];
  for (const n of names) {
    const existing = byName.get(n);
    if (existing) next.push(existing);
    else {
      next.push(newParamRow(n));
      added.push(n);
    }
  }
  const orphans: string[] = [];
  for (const r of rows) {
    if (nameSet.has(r.name)) continue;
    if (r._pristine) continue;
    next.push(r);
    orphans.push(r.name);
  }
  const changed = next.length !== rows.length || next.some((r, i) => r !== rows[i]);
  return { rows: next, orphans, added, changed };
}

/** Strip UI-only fields and empty optionals before sending to the API. */
export function cleanParams(rows: ParamRow[]): ToolParam[] {
  return rows.map((r) => {
    const p: ToolParam = { name: r.name.trim(), type: r.type, required: !!r.required };
    if (r.description?.trim()) p.description = r.description.trim();
    if (r.example !== null && r.example !== undefined && r.example !== "") p.example = r.example;
    if (r.default !== null && r.default !== undefined && r.default !== "") p.default = r.default;
    if (r.enum && r.enum.length) p.enum = r.enum;
    if (typeof r.min === "number") p.min = r.min;
    if (typeof r.max === "number") p.max = r.max;
    return p;
  });
}

/** Parse a text input into a value of the param's type (for example/default/enum fields). */
export function coerceParamValue(type: ParamType, raw: string): string | number | boolean | null {
  const s = raw.trim();
  if (s === "") return null;
  if (type === "integer") {
    const n = Number(s);
    return Number.isInteger(n) ? n : s;
  }
  if (type === "number") {
    const n = Number(s);
    return Number.isFinite(n) ? n : s;
  }
  if (type === "boolean") {
    if (/^(true|yes|1)$/i.test(s)) return true;
    if (/^(false|no|0)$/i.test(s)) return false;
    return s;
  }
  return s;
}

export const TOOL_NAME_RE = /^[a-z][a-z0-9_]{2,63}$/;
