import { useEffect, useRef } from "react";
import { useNodesInitialized, useNodesState, useReactFlow, type Node } from "@xyflow/react";

/**
 * Fit the viewport once nodes are measured, whenever `key` (the topology)
 * changes, and when the container resizes. Returns a ref for the wrapper.
 * Must be used inside a ReactFlowProvider.
 */
export function useAutoFit(key: string, padding = 0.06) {
  const { fitView } = useReactFlow();
  const measured = useNodesInitialized();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!measured) return;
    const t = setTimeout(() => void fitView({ padding, duration: 250 }), 20);
    return () => clearTimeout(t);
  }, [key, measured, fitView, padding]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const ro = new ResizeObserver(() => {
      clearTimeout(t);
      t = setTimeout(() => void fitView({ padding }), 80);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      clearTimeout(t);
    };
  }, [fitView, padding]);
  return ref;
}

/**
 * Controlled nodes that keep React Flow's measured size (and drag position)
 * across re-renders. Passing brand-new node objects on every status tick would
 * otherwise reset `measured`, so fitView would work from unmeasured nodes.
 */
export function useSyncedNodes<N extends Node>(next: N[], keepPosition = false) {
  const [nodes, setNodes, onNodesChange] = useNodesState<N>(next);
  useEffect(() => {
    setNodes((prev) => {
      const old = new Map(prev.map((p) => [p.id, p] as const));
      return next.map((n) => {
        const o = old.get(n.id);
        if (!o) return n;
        return { ...n, measured: o.measured, ...(keepPosition ? { position: o.position } : {}) };
      });
    });
  }, [next, setNodes, keepPosition]);
  return [nodes, onNodesChange] as const;
}
