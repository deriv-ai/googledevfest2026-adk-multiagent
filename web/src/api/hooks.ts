import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { endpoints } from "./client";
import type { SchemaName, Tool, ToolSpec } from "./types";

export const keys = {
  health: ["health"] as const,
  graph: ["graph"] as const,
  examples: ["chat", "examples"] as const,
  tools: (agent?: string, q?: string) => ["tools", agent ?? "", q ?? ""] as const,
  toolsAll: ["tools"] as const,
  tool: (name: string) => ["tool", name] as const,
  schemas: ["schemas"] as const,
  schema: (name: SchemaName) => ["schema", name] as const,
  sample: (schema: SchemaName, table: string) => ["sample", schema, table] as const,
};

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: endpoints.health, refetchInterval: 15_000, retry: 0 });
}

export function useGraph() {
  return useQuery({ queryKey: keys.graph, queryFn: endpoints.graph, staleTime: 10_000 });
}

export function useChatExamples() {
  return useQuery({ queryKey: keys.examples, queryFn: endpoints.chatExamples, staleTime: 5 * 60_000 });
}

export function useTools(agent?: string, q?: string) {
  return useQuery({ queryKey: keys.tools(agent, q), queryFn: () => endpoints.tools({ agent, q }), placeholderData: keepPreviousData });
}

export function useTool(name: string | undefined) {
  return useQuery({ queryKey: keys.tool(name ?? ""), queryFn: () => endpoints.tool(name!), enabled: !!name });
}

export function useSchema(name: SchemaName | undefined) {
  return useQuery({ queryKey: keys.schema(name ?? "finance"), queryFn: () => endpoints.schema(name!), enabled: !!name, staleTime: 60_000 });
}

export function useSample(schema: SchemaName, table: string, enabled: boolean) {
  return useQuery({ queryKey: keys.sample(schema, table), queryFn: () => endpoints.sample(schema, table, 5), enabled, staleTime: 60_000 });
}

function useInvalidateTools() {
  const qc = useQueryClient();
  return (name?: string) => {
    void qc.invalidateQueries({ queryKey: keys.toolsAll });
    void qc.invalidateQueries({ queryKey: keys.graph });
    if (name) void qc.invalidateQueries({ queryKey: keys.tool(name) });
  };
}

export function useSetToolEnabled() {
  const qc = useQueryClient();
  const invalidate = useInvalidateTools();
  return useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) => endpoints.setToolEnabled(name, enabled),
    onMutate: async ({ name, enabled }) => {
      await qc.cancelQueries({ queryKey: keys.toolsAll });
      const snapshots = qc.getQueriesData<Tool[]>({ queryKey: keys.toolsAll });
      for (const [key, data] of snapshots) {
        if (Array.isArray(data)) qc.setQueryData(key, data.map((t) => (t.name === name ? { ...t, enabled } : t)));
      }
      return { snapshots };
    },
    onError: (_e, _v, ctx) => {
      for (const [key, data] of ctx?.snapshots ?? []) qc.setQueryData(key, data);
    },
    onSettled: (_d, _e, v) => invalidate(v.name),
  });
}

export function useSaveTool(existingName?: string) {
  const invalidate = useInvalidateTools();
  return useMutation({
    mutationFn: (spec: ToolSpec) => (existingName ? endpoints.updateTool(existingName, spec) : endpoints.createTool(spec)),
    onSuccess: (t) => invalidate(t?.name ?? existingName),
  });
}

export function useDeleteTool() {
  const invalidate = useInvalidateTools();
  return useMutation({ mutationFn: (name: string) => endpoints.deleteTool(name), onSuccess: (_d, name) => invalidate(name) });
}

export function useTestTool() {
  return useMutation({ mutationFn: endpoints.testTool });
}
