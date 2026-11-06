import type { SchemaTable } from "@/api/types";

/** A ready-to-paste SELECT for a table, columns one per line. */
export function selectSnippet(schema: string, table: SchemaTable, limit = 10): string {
  const cols = table.columns.map((c) => `  ${c.name}`).join(",\n");
  return `SELECT\n${cols}\nFROM ${schema}.${table.name}\nLIMIT ${limit}`;
}
