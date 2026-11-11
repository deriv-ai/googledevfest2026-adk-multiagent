import { useState } from "react";
import { Check, Copy } from "@/components/icons";
import { Button } from "./ui";

export function CopyButton({ text, label = "Copy", size = "sm", variant = "outline" }: { text: string; label?: string; size?: "sm" | "md" | "icon"; variant?: "outline" | "ghost" | "secondary" }) {
  const [state, setState] = useState<"idle" | "copied" | "blocked">("idle");
  return (
    <Button
      size={size}
      variant={variant}
      aria-label={label}
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(text);
          setState("copied");
        } catch {
          setState("blocked");
        }
        setTimeout(() => setState("idle"), 1600);
      }}
    >
      {state === "copied" ? <Check className="size-3.5 text-success" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      {size === "icon" ? null : state === "copied" ? "Copied" : state === "blocked" ? "Clipboard blocked" : label}
    </Button>
  );
}
