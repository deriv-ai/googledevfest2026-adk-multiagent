import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { Workflow } from "@/components/icons";
import { cn } from "@/lib/utils";

const MIN = 30;
const MAX = 75;
const DEFAULT = 58;

interface Pane {
  width: number; // right pane, % of the container
  collapsed: boolean;
}

const clamp = (width: number) => Math.min(MAX, Math.max(MIN, width));

function load(key: string): Pane {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? "null");
    if (typeof saved?.width === "number") return { width: clamp(saved.width), collapsed: !!saved.collapsed };
  } catch {
    // storage blocked or malformed: fall back to the default
  }
  return { width: DEFAULT, collapsed: false };
}

/**
 * Two panes side by side on large screens, stacked below that. The right pane can be resized by
 * dragging the divider (or arrow keys on it) and collapsed into a slim strip; both are remembered.
 */
export function SplitView({ storageKey, left, right, rightLabel }: {
  storageKey: string;
  left: ReactNode;
  right: (collapse: () => void) => ReactNode;
  rightLabel: string;
}) {
  const [pane, setPane] = useState(() => load(storageKey));
  const [dragging, setDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (dragging) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(pane));
    } catch {
      // not remembered this time; the layout still works
    }
  }, [pane, dragging, storageKey]);

  const resizeTo = (width: number) => setPane((p) => ({ ...p, width: clamp(width) }));
  const setCollapsed = (collapsed: boolean) => setPane((p) => ({ ...p, collapsed }));

  const onPointerMove = (e: React.PointerEvent) => {
    const box = containerRef.current?.getBoundingClientRect();
    if (dragging && box) resizeTo(((box.right - e.clientX) / box.width) * 100);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowLeft") resizeTo(pane.width + 2);
    else if (e.key === "ArrowRight") resizeTo(pane.width - 2);
    else if (e.key === "Enter") setCollapsed(true);
    else return;
    e.preventDefault();
  };

  return (
    <div ref={containerRef} className={cn("flex h-full flex-col overflow-y-auto lg:flex-row lg:overflow-hidden", dragging && "select-none")}>
      <div className="flex min-h-[70dvh] min-w-0 flex-1 flex-col lg:min-h-0">{left}</div>

      {pane.collapsed ? (
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          aria-label={`Show ${rightLabel.toLowerCase()}`}
          className="hidden w-11 shrink-0 flex-col items-center gap-3 border-l border-border bg-card py-4 text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground lg:flex"
        >
          <Workflow className="size-4" aria-hidden />
          <span className="[writing-mode:vertical-rl]">{rightLabel}</span>
        </button>
      ) : (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label={`Resize ${rightLabel.toLowerCase()}`}
          aria-valuemin={MIN}
          aria-valuemax={MAX}
          aria-valuenow={Math.round(pane.width)}
          tabIndex={0}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            setDragging(true);
          }}
          onPointerMove={onPointerMove}
          onPointerUp={() => setDragging(false)}
          onDoubleClick={() => resizeTo(DEFAULT)}
          onKeyDown={onKeyDown}
          className="group relative hidden w-px shrink-0 cursor-col-resize bg-border outline-none lg:block"
        >
          {/* A wider invisible hit area, and a visible line while hovered, dragged or focused. */}
          <span className="absolute inset-y-0 -left-1.5 w-3" aria-hidden />
          <span
            aria-hidden
            className={cn(
              "absolute inset-y-0 -left-px w-[3px] bg-ring opacity-0 transition-opacity duration-150 group-hover:opacity-60 group-focus-visible:opacity-100",
              dragging && "opacity-100",
            )}
          />
        </div>
      )}

      <section
        aria-label={rightLabel}
        style={{ "--pane-w": `${pane.width}%` } as CSSProperties}
        className={cn(
          "h-[860px] min-w-0 border-t border-border bg-card lg:h-auto lg:min-h-0 lg:w-(--pane-w) lg:shrink-0 lg:border-t-0",
          pane.collapsed && "lg:hidden",
        )}
      >
        {right(() => setCollapsed(true))}
      </section>
    </div>
  );
}
