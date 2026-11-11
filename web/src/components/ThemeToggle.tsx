import { Monitor, Moon, Sun } from "@/components/icons";
import { useTheme, type ThemePref } from "@/lib/theme";
import { PRESS } from "./ui";
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
        className={cn("inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-[background-color,color,scale] duration-160 ease-out hover:bg-muted hover:text-foreground", PRESS)}
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
            "inline-flex h-7 w-8 items-center justify-center rounded-md transition-[background-color,color,box-shadow,scale] duration-160 ease-out",
            PRESS,
            pref === value ? "bg-card text-foreground shadow-xs dark:bg-subtle" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
