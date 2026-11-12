import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "@/components/icons";
import { Button } from "./ui";
import { cn } from "@/lib/utils";

export function ErrorState({ error, onRetry, className, title = "Couldn't load this" }: { error: unknown; onRetry?: () => void; className?: string; title?: string }) {
  const msg = error instanceof Error ? error.message : String(error ?? "Unknown error");
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-3 rounded-xl border border-danger/30 bg-danger/6 p-5", className)}>
      <div className="flex items-center gap-2 font-semibold text-danger">
        <AlertTriangle className="size-4" aria-hidden />
        {title}
      </div>
      <p className="text-sm text-foreground/85">{msg}</p>
      {onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw className="size-3.5" aria-hidden /> Try again
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ icon, title, children, action, className }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-input/70 px-6 py-12 text-center", className)}>
      {icon ? <div className="mb-1 text-muted-foreground">{icon}</div> : null}
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {children ? <div className="max-w-md text-sm text-muted-foreground">{children}</div> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function PageHeader({ title, description, actions, className }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <header className={cn("mb-8 flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        <h1 className="text-2xl leading-tight font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1.5 max-w-[68ch] text-[15px] text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
