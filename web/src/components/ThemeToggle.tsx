import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme, type ThemePref } from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTS: { value: ThemePref; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "system", label: "System theme", Icon: Monitor },
  { value: "dark", label: "Dark theme", Icon: Moon },
];

export function ThemeToggle({ compact }: { compact?: boolean }) {
  const { pref, setPref } = useTheme();
  if (compact) {
    const i = OPTS.findIndex((o) => o.value === pref);
    const cur = OPTS[i]!;
    const next = OPTS[(i + 1) % OPTS.length]!;
    return (
      <button
        type="button"
        onClick={() => setPref(next.value)}
        className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-label={`${cur.label} (switch to ${next.label.toLowerCase()})`}
        title={cur.label}
      >
        <cur.Icon className="size-4" />
      </button>
    );
  }
  return (
    <div role="radiogroup" aria-label="Theme" className="inline-flex rounded-lg bg-muted p-0.5">
      {OPTS.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={pref === value}
          aria-label={label}
          title={label}
          onClick={() => setPref(value)}
          className={cn(
            "inline-flex h-7 w-8 items-center justify-center rounded-md transition-colors",
            pref === value ? "bg-card text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.15)]" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
