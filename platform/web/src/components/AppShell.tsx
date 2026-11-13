import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Database, LayoutGrid, MessageSquarePlus, MessagesSquare, PanelLeftClose, PanelLeftOpen, Wrench } from "@/components/icons";
import { ThemeToggle } from "./ThemeToggle";
import { PRESS } from "./ui";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Overview", Icon: LayoutGrid, end: true },
  { to: "/chat", label: "Chat", Icon: MessagesSquare, end: false },
  { to: "/tools", label: "Tools", Icon: Wrench, end: false },
  { to: "/schema", label: "Data schema", Icon: Database, end: false },
];

const COLLAPSE_KEY = "nimbus.sidebarCollapsed";

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

export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
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
  const navigate = useNavigate();
  const fullBleed = pathname.startsWith("/chat");
  const startNewChat = () => navigate("/chat", { state: { newChat: Date.now() } });

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      {/* Sidebar (md+) */}
      <aside className={cn("hidden shrink-0 flex-col bg-sidebar transition-[width] duration-200 ease-out motion-reduce:transition-none md:flex", collapsed ? "w-[60px]" : "w-[260px]")}>
        <div className={cn("flex h-14 items-center gap-2 px-3", collapsed ? "justify-center" : "justify-between")}>
          {collapsed ? null : (
            <div className="flex min-w-0 items-center gap-2.5 px-1">
              <BrandMark className="size-7 shrink-0" />
              <span className="truncate text-[15px] font-semibold tracking-tight">Nimbus Agents</span>
            </div>
          )}
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            className={cn("inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-[background-color,color,scale] duration-160 ease-out hover:bg-muted hover:text-foreground", PRESS)}
            aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
            title={collapsed ? "Open sidebar" : "Close sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
          </button>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2 pt-1" aria-label="Main">
          <button type="button" onClick={startNewChat} title={collapsed ? "New chat" : undefined} className={cn(navItem(false), collapsed && "justify-center px-0")}>
            <MessageSquarePlus className="size-[18px] shrink-0" aria-hidden />
            {collapsed ? <span className="sr-only">New chat</span> : "New chat"}
          </button>
          <div className="my-2 h-px bg-border" aria-hidden />
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              className={({ isActive }) => cn(navItem(isActive), collapsed && "justify-center px-0")}
            >
              <Icon className="size-[18px] shrink-0" aria-hidden />
              {collapsed ? <span className="sr-only">{label}</span> : label}
            </NavLink>
          ))}
        </nav>
        <div className={cn("p-3", collapsed && "flex justify-center")}>{collapsed ? <ThemeToggle compact /> : <ThemeToggle />}</div>
      </aside>

      {/* Top bar (small screens) */}
      <header className="flex shrink-0 items-center gap-2 border-b border-border bg-sidebar px-3 py-2 md:hidden">
        <BrandMark className="size-7 shrink-0" />
        <nav className="flex min-w-0 flex-1 gap-1 overflow-x-auto [scrollbar-width:none]" aria-label="Main">
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              aria-label={label}
              className={({ isActive }) =>
                cn(
                  "flex h-9 min-w-9 shrink-0 items-center focus-visible:-outline-offset-2 justify-center gap-1.5 rounded-md px-2.5 text-sm font-medium whitespace-nowrap transition-[background-color,color,scale] duration-160 ease-out",
                  PRESS,
                  isActive ? "bg-muted text-foreground" : "text-muted-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className="size-4 shrink-0" aria-hidden />
                  {isActive ? label : null}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <ThemeToggle compact />
      </header>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <main className={cn("min-h-0 flex-1", fullBleed ? "overflow-hidden" : "overflow-y-auto")}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function navItem(active: boolean) {
  return cn(
    "flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-left text-[14px] transition-[background-color,color,scale] duration-160 ease-out",
    PRESS,
    active ? "bg-muted font-medium text-foreground" : "text-foreground/80 hover:bg-muted/70 hover:text-foreground",
  );
}
