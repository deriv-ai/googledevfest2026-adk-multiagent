import { describe, expect, it } from "vitest";
import { cleanParams, coerceParamValue, extractPlaceholders, guessParamType, syncParams, TOOL_NAME_RE, type ParamRow } from "@/lib/placeholders";

describe("extractPlaceholders", () => {
  it("finds :name placeholders in order, deduplicated", () => {
    const sql = "SELECT * FROM t WHERE d BETWEEN :start_date AND :end_date AND (:entity_id IS NULL OR e = :entity_id) LIMIT :limit";
    expect(extractPlaceholders(sql)).toEqual(["start_date", "end_date", "entity_id", "limit"]);
  });
  it("ignores ::casts and digits after a colon", () => {
    expect(extractPlaceholders("SELECT x::date, y::numeric(18,2), '10:30' FROM t WHERE a = :a::int")).toEqual(["a"]);
  });
  it("returns [] when there are none", () => {
    expect(extractPlaceholders("SELECT 1")).toEqual([]);
  });
});

describe("guessParamType", () => {
  it("guesses from common names", () => {
    expect(guessParamType("start_date")).toBe("date");
    expect(guessParamType("month")).toBe("date");
    expect(guessParamType("limit")).toBe("integer");
    expect(guessParamType("min_amount")).toBe("number");
    expect(guessParamType("include_open")).toBe("boolean");
    expect(guessParamType("segment")).toBe("string");
  });
});

describe("syncParams", () => {
  const row = (name: string, extra: Partial<ParamRow> = {}): ParamRow => ({ name, type: "string", required: true, ...extra });

  it("adds a row for every new placeholder", () => {
    const r = syncParams("SELECT :a, :b", []);
    expect(r.rows.map((x) => x.name)).toEqual(["a", "b"]);
    expect(r.added).toEqual(["a", "b"]);
    expect(r.rows.every((x) => x._pristine)).toBe(true);
    expect(r.changed).toBe(true);
  });

  it("keeps existing rows (by identity) and follows SQL order", () => {
    const a = row("a", { description: "A" });
    const b = row("b");
    const r = syncParams("SELECT :b, :a", [a, b]);
    expect(r.rows).toEqual([b, a]);
    expect(r.rows[1]).toBe(a);
    expect(r.orphans).toEqual([]);
  });

  it("reports edited rows whose placeholder vanished as orphans, and keeps them last", () => {
    const r = syncParams("SELECT :a", [row("old", { description: "edited" }), row("a")]);
    expect(r.rows.map((x) => x.name)).toEqual(["a", "old"]);
    expect(r.orphans).toEqual(["old"]);
  });

  it("silently drops untouched auto-added rows (typing debris)", () => {
    let rows = syncParams("SELECT :start_d", []).rows;
    rows = syncParams("SELECT :start_date", rows).rows;
    expect(rows.map((x) => x.name)).toEqual(["start_date"]);
  });

  it("reports unchanged when already in sync", () => {
    const rows = [row("a")];
    expect(syncParams("SELECT :a", rows).changed).toBe(false);
  });
});

describe("cleanParams / coerceParamValue", () => {
  it("strips UI fields and empty optionals", () => {
    expect(
      cleanParams([{ name: " limit ", type: "integer", required: false, description: " ", default: 10, example: null, enum: [], min: 1, max: null, _pristine: true }]),
    ).toEqual([{ name: "limit", type: "integer", required: false, default: 10, min: 1 }]);
  });
  it("coerces typed values", () => {
    expect(coerceParamValue("integer", "10")).toBe(10);
    expect(coerceParamValue("number", "2.5")).toBe(2.5);
    expect(coerceParamValue("boolean", "yes")).toBe(true);
    expect(coerceParamValue("date", " 2026-07-01 ")).toBe("2026-07-01");
    expect(coerceParamValue("string", "")).toBeNull();
  });
  it("validates tool names", () => {
    expect(TOOL_NAME_RE.test("finance_fx_rates")).toBe(true);
    expect(TOOL_NAME_RE.test("Fx")).toBe(false);
    expect(TOOL_NAME_RE.test("ab")).toBe(false);
    expect(TOOL_NAME_RE.test("9abc")).toBe(false);
  });
});
