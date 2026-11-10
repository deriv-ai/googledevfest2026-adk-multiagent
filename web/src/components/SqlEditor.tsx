import { useMemo } from "react";
import CodeMirror, { EditorView, type ReactCodeMirrorProps } from "@uiw/react-codemirror";
import { PostgreSQL, sql, type SQLNamespace } from "@codemirror/lang-sql";
import type { SchemaDetail } from "@/api/types";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const baseTheme = EditorView.theme({
  "&": { backgroundColor: "transparent" },
  ".cm-content": { padding: "10px 0" },
  ".cm-gutters": { backgroundColor: "transparent", color: "hsl(var(--muted-foreground))" },
  ".cm-activeLine": { backgroundColor: "hsl(var(--muted) / 0.6)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "hsl(var(--foreground))" },
  ".cm-placeholder": { color: "hsl(var(--muted-foreground))" },
});

export interface SqlEditorProps {
  value: string;
  onChange?: (v: string) => void;
  readOnly?: boolean;
  schema?: SchemaDetail | null;
  minHeight?: string;
  maxHeight?: string;
  className?: string;
  placeholder?: string;
  onCreateEditor?: ReactCodeMirrorProps["onCreateEditor"];
  ariaLabel?: string;
}

export function SqlEditor({ value, onChange, readOnly, schema, minHeight = "220px", maxHeight, className, placeholder, onCreateEditor, ariaLabel = "SQL editor" }: SqlEditorProps) {
  const { resolved } = useTheme();
  const extensions = useMemo(() => {
    const ns: SQLNamespace = {};
    if (schema) {
      const tables: Record<string, string[]> = {};
      for (const t of schema.tables) tables[t.name] = t.columns.map((c) => c.name);
      ns[schema.name] = tables;
    }
    return [sql({ dialect: PostgreSQL, schema: ns, defaultSchema: schema?.name, upperCaseKeywords: true }), baseTheme, EditorView.lineWrapping, EditorView.contentAttributes.of({ "aria-label": ariaLabel })];
  }, [schema, ariaLabel]);

  return (
    <div className={cn("overflow-hidden rounded-lg border border-input bg-card focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/15", readOnly && "bg-muted/30", className)}>
      <CodeMirror
        value={value}
        onChange={onChange}
        readOnly={readOnly}
        editable={!readOnly}
        theme={resolved}
        extensions={extensions}
        minHeight={minHeight}
        maxHeight={maxHeight}
        placeholder={placeholder}
        onCreateEditor={onCreateEditor}
        basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: !readOnly, highlightActiveLineGutter: !readOnly, autocompletion: !readOnly }}
      />
    </div>
  );
}
