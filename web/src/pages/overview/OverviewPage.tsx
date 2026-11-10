import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Database, MessagesSquare, MousePointerClick, Plus } from "lucide-react";
import { HealthChips, LlmKeyCallout } from "@/components/HealthChips";
import { Panel } from "@/components/ui";
import { ARCH_NODES, ArchitectureGraph } from "@/graph/ArchitectureGraph";
import { toneColor } from "@/lib/agents";

const LINKS = [
  { to: "/chat", Icon: MessagesSquare, title: "Ask the agents", body: "Try a cross-agent question and watch the route light up." },
  { to: "/tools/new", Icon: Plus, title: "Register a tool", body: "Write SQL, test it, save it. Agents use it on the next question." },
  { to: "/schema", Icon: Database, title: "Browse the data", body: "Tables, columns and sample rows to write your own queries." },
];

export default function OverviewPage() {
  const [selected, setSelected] = useState<string | null>("orchestrator");
  const onSelect = useCallback((id: string) => setSelected((s) => (s === id ? null : id)), []);
  const info = ARCH_NODES.find((n) => n.id === selected) ?? null;

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-8 lg:px-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-5">
        <div className="min-w-0">
          <h1 className="text-[30px] leading-tight font-semibold tracking-tight">Nimbus Markets assistant</h1>
          <p className="mt-2 max-w-[68ch] text-[16px] text-muted-foreground">
            A main agent, an orchestrator and three specialists built with Google ADK. Finance and trading tools live in a database table, so you can add one from the browser and the agents use it on the next question.
          </p>
        </div>
        <HealthChips />
      </header>

      <LlmKeyCallout className="mb-6" />

      <Panel className="overflow-hidden" aria-label="Architecture diagram">
        <div className="relative h-[clamp(420px,58vh,620px)]">
          <ArchitectureGraph selected={selected} onSelect={onSelect} />
        </div>
        <div className="flex min-h-[112px] flex-wrap items-start gap-x-8 gap-y-3 border-t border-border px-5 py-4">
          {info ? (
            <div key={info.id} className="fade-up flex min-w-0 flex-[2] basis-[420px] gap-3.5">
              <span
                className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg"
                style={info.tone ? { background: toneColor(info.tone), color: "white" } : { background: "hsl(var(--muted))" }}
              >
                <info.icon className="size-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <h2 className="text-[17px] leading-tight font-semibold">
                  {info.title} <span className="ml-1 text-[13px] font-normal text-muted-foreground">{info.subtitle}</span>
                </h2>
                <p className="mt-1 max-w-[75ch] text-[15px] leading-relaxed">{info.body}</p>
                {info.link ? (
                  <Link to={info.link.to} className="mt-1.5 inline-flex items-center gap-1.5 text-[14px] font-medium text-link hover:underline">
                    {info.link.label} <ArrowRight className="size-4" aria-hidden />
                  </Link>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex flex-[2] basis-[420px] items-center gap-2 text-muted-foreground">
              <MousePointerClick className="size-5" aria-hidden />
              <p className="text-[14.5px]">Click any box in the diagram to see what it does.</p>
            </div>
          )}
          <p className="flex-1 basis-[260px] text-[13.5px] text-muted-foreground">
            Classification is the orchestrator's LLM choosing which specialist functions to call. There's no separate classifier model.
          </p>
        </div>
      </Panel>

      <nav aria-label="Get started" className="mt-8 grid gap-3 md:grid-cols-3">
        {LINKS.map(({ to, Icon, title, body }) => (
          <Link key={to} to={to} className="group flex items-start gap-3.5 rounded-xl border border-border bg-card p-4 transition-colors hover:border-input hover:bg-muted/40">
            <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground group-hover:text-foreground" aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5 text-[15px] font-semibold">
                {title} <ArrowRight className="size-4 opacity-0 transition-[opacity,transform] group-hover:translate-x-0.5 group-hover:opacity-100" aria-hidden />
              </span>
              <span className="mt-0.5 block text-[13.5px] text-muted-foreground">{body}</span>
            </span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
