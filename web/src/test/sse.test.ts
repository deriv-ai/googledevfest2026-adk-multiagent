import { describe, expect, it } from "vitest";
import { createSseParser, parseFrame } from "@/lib/sse";

describe("parseFrame", () => {
  it("reads a data line", () => {
    expect(parseFrame('data: {"a":1}')).toBe('{"a":1}');
  });
  it("joins multi-line data with newlines and strips one leading space only", () => {
    expect(parseFrame("data: one\ndata:  two\ndata:three")).toBe("one\n two\nthree");
  });
  it("ignores comments and other fields", () => {
    expect(parseFrame(": ping")).toBeNull();
    expect(parseFrame("event: message\nid: 7\nretry: 100")).toBeNull();
    expect(parseFrame("event: x\ndata: y")).toBe("y");
  });
});

describe("createSseParser", () => {
  it("parses complete frames and skips keepalive pings", () => {
    const p = createSseParser();
    const out = p.push(': ping\n\ndata: {"type":"start"}\n\ndata: {"type":"answer","text":"hi"}\n\n');
    expect(out).toEqual([{ type: "start" }, { type: "answer", text: "hi" }]);
  });

  it("buffers frames split across chunks at any position", () => {
    const full = 'data: {"type":"tool_call","tool":"x"}\n\n: ping\n\ndata: {"type":"answer"}\n\n';
    for (let cut = 1; cut < full.length; cut++) {
      const p = createSseParser();
      const got = [...p.push(full.slice(0, cut)), ...p.push(full.slice(cut)), ...p.flush()];
      expect(got).toEqual([{ type: "tool_call", tool: "x" }, { type: "answer" }]);
    }
  });

  it("handles CRLF separators, including one split between chunks", () => {
    const p = createSseParser();
    expect(p.push('data: {"n":1}\r\n\r')).toEqual([]);
    expect(p.push('\ndata: {"n":2}\r\n\r\n')).toEqual([{ n: 1 }, { n: 2 }]);
  });

  it("flushes a trailing frame without the blank line", () => {
    const p = createSseParser();
    expect(p.push('data: {"n":1}')).toEqual([]);
    expect(p.flush()).toEqual([{ n: 1 }]);
    expect(p.flush()).toEqual([]);
  });

  it("drops malformed JSON and reports it", () => {
    const bad: string[] = [];
    const p = createSseParser({ onError: (_e, d) => bad.push(d) });
    expect(p.push('data: {nope\n\ndata: {"ok":true}\n\n')).toEqual([{ ok: true }]);
    expect(bad).toEqual(["{nope"]);
  });

  it("supports a custom decoder that filters frames", () => {
    const p = createSseParser<{ type: string }>({
      decode: (d) => {
        const v = JSON.parse(d);
        return typeof v.type === "string" ? v : undefined;
      },
    });
    expect(p.push('data: {"x":1}\n\ndata: {"type":"start"}\n\n')).toEqual([{ type: "start" }]);
  });
});
