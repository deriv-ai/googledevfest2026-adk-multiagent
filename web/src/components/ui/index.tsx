import { forwardRef, useEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Loader2 } from "@/components/icons";
import { cn } from "@/lib/utils";

// ---- Button ------------------------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg" | "icon";

/** Press feedback for anything clickable: a quick, subtle scale-down on :active. */
export const PRESS = "active:scale-[0.97]";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-primary-foreground shadow-xs hover:bg-primary/90",
  secondary: "bg-muted text-foreground hover:bg-subtle",
  outline: "border border-border bg-card text-foreground shadow-xs hover:border-input hover:bg-muted",
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
  danger: "bg-danger text-white shadow-xs hover:bg-danger/90",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-9 px-3.5 text-sm gap-2",
  lg: "h-10 px-4 text-sm gap-2",
  icon: "h-9 w-9 justify-center",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "secondary", size = "md", loading, className, children, disabled, ...rest }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      disabled={disabled || loading}
      className={cn(
        "inline-flex shrink-0 items-center rounded-md font-medium whitespace-nowrap transition-[background-color,border-color,color,box-shadow,opacity,scale] duration-160 ease-out disabled:pointer-events-none disabled:opacity-45",
        PRESS,
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
});

// ---- Inputs ------------------------------------------------------------------------------

const field =
  "w-full rounded-md border border-input bg-card px-3 text-sm text-foreground shadow-xs placeholder:text-muted-foreground transition-[border-color,box-shadow] duration-150 ease-out hover:border-muted-foreground/40 focus:border-ring focus:outline-none focus:ring-3 focus:ring-ring/20 disabled:opacity-60 aria-invalid:border-danger aria-invalid:focus:ring-danger/20";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cn(field, "h-9 read-only:bg-muted/40 read-only:focus:ring-0", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cn(field, "py-2 leading-relaxed", className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...rest }, ref) {
  return (
    <select ref={ref} className={cn(field, "h-9 pr-8", className)} {...rest}>
      {children}
    </select>
  );
});

export function Label({ children, htmlFor, hint, className }: { children: ReactNode; htmlFor?: string; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn("mb-1.5 flex items-baseline justify-between gap-3", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-foreground">
        {children}
      </label>
      {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled, size = "md" }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean; size?: "sm" | "md" }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
      className={cn(
        "relative inline-flex shrink-0 items-center rounded-full transition-[background-color,scale] duration-160 ease-out active:scale-[0.95] disabled:opacity-50",
        size === "sm" ? "h-5 w-9" : "h-6 w-11",
        checked ? "bg-success" : "bg-input",
      )}
    >
      <span
        className={cn(
          "inline-block rounded-full bg-white shadow-[0_1px_3px_rgb(0_0_0/0.25)] transition-transform duration-200 ease-out motion-reduce:transition-none",
          size === "sm" ? "size-4" : "size-5",
          checked ? (size === "sm" ? "translate-x-[18px]" : "translate-x-[22px]") : "translate-x-0.5",
        )}
      />
    </button>
  );
}

// ---- Segmented control / tabs -----------------------------------------------------------------

export function Segmented<T extends string>({ value, onChange, options, className, size = "md" }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; disabled?: boolean }[]; className?: string; size?: "sm" | "md" }) {
  return (
    <div role="tablist" className={cn("inline-flex max-w-full overflow-x-auto rounded-lg bg-muted p-0.5 [scrollbar-width:none]", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          type="button"
          aria-selected={o.value === value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-md font-medium whitespace-nowrap focus-visible:-outline-offset-2 transition-[background-color,color,box-shadow,scale] duration-160 ease-out disabled:opacity-40",
            PRESS,
            size === "sm" ? "h-7 px-2.5 text-[13px]" : "h-8 px-3 text-[13px]",
            o.value === value ? "bg-card text-foreground shadow-xs dark:bg-subtle" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---- Feedback ----------------------------------------------------------------------------------

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton h-4", className)} />;
}

export function Panel({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("rounded-xl border border-border bg-card shadow-xs", className)} {...rest}>
      {children}
    </section>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">{children}</kbd>;
}

// ---- Confirm dialog (native <dialog>: focus trap + Esc for free) -------------------------------

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  onConfirm,
  onClose,
  busy,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className="dialog m-auto w-[min(440px,calc(100vw-32px))] rounded-xl border border-border bg-card p-0 text-foreground shadow-lg"
    >
      <div className="p-6">
        <h2 className="text-base font-semibold">{title}</h2>
        <div className="mt-2 text-sm text-muted-foreground">{body}</div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={busy} autoFocus>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
