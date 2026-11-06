/**
 * Incremental parser for a `text/event-stream` body read with fetch().
 *
 * Frames are separated by a blank line. Inside a frame, `data:` lines carry the
 * payload (several are joined with "\n"), lines starting with ":" are comments
 * (the server's `: ping` keepalive) and other fields (event:, id:, retry:) are
 * ignored. Chunks can split a frame anywhere — even mid-"\r\n" — so the parser
 * keeps the tail until the separator arrives.
 */
export interface SseParser<T> {
  /** Feed a decoded text chunk; returns the payloads of every frame it completed. */
  push(chunk: string): T[];
  /** End of stream: parse whatever is left (a final frame without the trailing blank line). */
  flush(): T[];
}

export interface SseParserOptions<T> {
  /** Turn a frame's data string into a value. Default: JSON.parse. Return undefined to drop it. */
  decode?: (data: string) => T | undefined;
  /** Called when decode throws (malformed JSON). Default: drop the frame silently. */
  onError?: (err: unknown, data: string) => void;
}

const FRAME_SEPARATOR = /\r\n\r\n|\n\n|\r\r/;

export function parseFrame(frame: string): string | null {
  const data: string[] = [];
  for (const raw of frame.split(/\r\n|\n|\r/)) {
    if (raw === "" || raw.startsWith(":")) continue;
    const colon = raw.indexOf(":");
    const field = colon === -1 ? raw : raw.slice(0, colon);
    if (field !== "data") continue;
    let value = colon === -1 ? "" : raw.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    data.push(value);
  }
  return data.length ? data.join("\n") : null;
}

export function createSseParser<T = unknown>(opts: SseParserOptions<T> = {}): SseParser<T> {
  const decode = opts.decode ?? ((s: string) => JSON.parse(s) as T);
  let buffer = "";

  const emit = (frame: string, out: T[]) => {
    const data = parseFrame(frame);
    if (data === null) return;
    try {
      const value = decode(data);
      if (value !== undefined) out.push(value);
    } catch (err) {
      opts.onError?.(err, data);
    }
  };

  return {
    push(chunk) {
      buffer += chunk;
      const out: T[] = [];
      // A lone trailing "\r" might be the first half of "\r\n" — wait for more.
      for (;;) {
        const m = FRAME_SEPARATOR.exec(buffer);
        if (!m) break;
        if (m[0] === "\r\r" && buffer.length === m.index + 2) break;
        const frame = buffer.slice(0, m.index);
        buffer = buffer.slice(m.index + m[0].length);
        emit(frame, out);
      }
      return out;
    },
    flush() {
      const out: T[] = [];
      const rest = buffer;
      buffer = "";
      if (rest.trim()) emit(rest, out);
      return out;
    },
  };
}
