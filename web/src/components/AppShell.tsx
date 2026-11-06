import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Database, LayoutGrid, MessagesSquare, PanelLeftClose, PanelLeftOpen, Wrench } from "lucide-react";
import { useHealth } from "@/api/hooks";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Overview", Icon: LayoutGrid, end: true },
  { to: "/chat", label: "Chat", Icon: MessagesSquare, end: false },
  { to: "/tools", label: "Tools", Icon: Wrench, end: false },
  { to: "/schema", label: "Data schema", Icon: Database, end: false },
];

const COLLAPSE_KEY = "nimbus-nav-collapsed";

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="hsl(var(--agent-main))" />
      <circle cx="16" cy="9.5" r="3.2" fill="#fff" />
      <circle cx="8.5" cy="22" r="3.2" fill="#fff" />
      <circle cx="23.5" cy="22" r="3.2" fill="#fff" />
      <path d="M16 12.7v4.3M16 17l-6 3.2M16 17l6 3.2" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function HealthDot({ collapsed }: { collapsed: boolean }) {
  const { data, isError } = useHealth();
  const bad = isError || data?.db === "error" || data?.llm_key === "missing";
  const label = isError ? "API unreachable" : !data ? "Checking…" : bad ? (data.llm_key === "missing" ? "LLM key missing" : "Degraded") : "All systems go";
  return (
    <NavLink to="/" className={cn("flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground", collapsed && "justify-center")} title={label}>
      <span className={cn("size-2 shrink-0 rounded-full", !data && !isError ? "bg-input" : bad ? "bg-danger" : "bg-success")} aria-hidden />
      {collapsed ? <span className="sr-only">{label}</span> : label}
    </NavLink>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const v = localStorage.getItem(COLLAPSE_KEY);
      return v === null ? window.innerWidth < 1360 : v === "1";
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);
  const { pathname } = useLocation();
  const fullBleed = pathname.startsWith("/chat");

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      {/* Sidebar (md+) */}
      <aside className={cn("hidden shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200 md:flex", collapsed ? "w-[68px]" : "w-60")}>
        <div className={cn("flex h-16 items-center gap-2.5 px-4", collapsed && "justify-center px-0")}>
          <BrandMark className="size-8 shrink-0" />
          {!collapsed && (
            <div className="min-w-0 leading-tight">
              <div className="text-[15px] font-semibold tracking-tight">Nimbus Agents</div>
              <div className="text-xs text-muted-foreground">ADK multi-agent demo</div>
            </div>
          )}
        </div>
        <nav className="mt-2 flex flex-1 flex-col gap-0.5 px-3" aria-label="Main">
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex h-10 items-center gap-3 rounded-lg px-3 text-[14.5px] font-medium transition-colors",
                  collapsed && "justify-center px-0",
                  isActive ? "bg-card text-foreground shadow-[0_1px_3px_rgb(0_0_0/0.08)] dark:bg-muted" : "text-muted-foreground hover:bg-card/60 hover:text-foreground dark:hover:bg-muted/60",
                )
              }
            >
              <Icon className="size-[18px] shrink-0" aria-hidden />
              {collapsed ? <span className="sr-only">{label}</span> : label}
            </NavLink>
          ))}
        </nav>
        <div className={cn("flex flex-col gap-2 border-t border-border p-3", collapsed && "items-center")}>
          <HealthDot collapsed={collapsed} />
          <div className={cn("flex items-center justify-between gap-2", collapsed && "flex-col")}>
            {collapsed ? <ThemeToggle compact /> : <ThemeToggle />}
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            </button>
          </div>
        </div>
      </aside>

      {/* Top bar (small screens) */}
      <header className="flex shrink-0 items-center gap-2 border-b border-border bg-sidebar px-3 py-2 md:hidden">
        <BrandMark className="size-7" />
        <nav className="flex flex-1 gap-1 overflow-x-auto" aria-label="Main">
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cn("flex h-9 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium whitespace-nowrap", isActive ? "bg-card text-foreground" : "text-muted-foreground")}>
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <ThemeToggle compact />
      </header>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <main className={cn("min-h-0 flex-1", fullBleed ? "overflow-hidden" : "overflow-y-auto")}>
          <Outlet />
        </main>
        <footer className="shrink-0 border-t border-border bg-sidebar px-4 py-1.5 text-center text-xs text-muted-foreground">
          All data is synthetic and generated for demonstration purposes. Nimbus Markets is a fictional company.
        </footer>
      </div>
    </div>
  );
}
