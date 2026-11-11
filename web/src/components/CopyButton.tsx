import { useState } from "react";
import { Check, Copy } from "@/components/icons";
import { toast } from "sonner";
import { Button } from "./ui";

export function CopyButton({ text, label = "Copy", size = "sm", variant = "outline", toastMessage }: { text: string; label?: string; size?: "sm" | "md" | "icon"; variant?: "outline" | "ghost" | "secondary"; toastMessage?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size={size}
      variant={variant}
      aria-label={label}
      onClick={async (e) => {
        e.stopPropagation();
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          if (toastMessage) toast.success(toastMessage);
          setTimeout(() => setDone(false), 1400);
        } catch {
          toast.error("Clipboard is blocked in this browser.");
        }
      }}
    >
      {done ? <Check className="size-3.5 text-success" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
      {size === "icon" ? null : done ? "Copied" : label}
    </Button>
  );
}
