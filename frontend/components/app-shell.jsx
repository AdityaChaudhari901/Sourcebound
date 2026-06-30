"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Database,
  FlaskConical,
  LayoutGrid,
  LogOut,
  Menu,
  MessageSquareText,
  Settings2,
  X,
} from "lucide-react";

import { useAuth, isDemoUser } from "@/lib/auth";
import { WorkspaceSwitcher } from "@/components/workspace-switcher";

const NAV_ITEMS = [
  { label: "Dashboard", code: "dsh", icon: LayoutGrid, href: "/dashboard" },
  { label: "Ask", code: "ask", icon: MessageSquareText, href: "/ask" },
  { label: "Sources", code: "src", icon: Database, href: "/sources" },
  { label: "Evaluations", code: "eval", icon: FlaskConical, href: "/evaluations" },
  { label: "Traces", code: "trc", icon: Activity, href: "/traces" },
  { label: "Settings", code: "cfg", icon: Settings2, href: "/settings" },
];


export function AppShell({ children }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false); // mobile drawer

  const active = NAV_ITEMS.find((item) => item.href === pathname);
  const title = active?.label ?? "Sourcebound";

  // Close the drawer on navigation and on Escape.
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="lg:grid lg:h-screen lg:grid-cols-[240px_1fr] lg:overflow-hidden">
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar (off-canvas on mobile, static on lg) */}
      <aside
        className={[
          "bg-sidebar border-border fixed inset-y-0 left-0 z-40 flex w-[240px] flex-col border-r",
          "transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        aria-label="Sidebar"
      >
        <div className="border-border flex h-14 items-center justify-between gap-2.5 border-b px-5">
          <div className="flex items-center gap-2.5">
            <img src="/images/sourcebound-logo.png" alt="Sourcebound" className="h-5 w-auto" />
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
            className="text-muted-foreground hover:text-foreground -mr-1 rounded-md p-1 lg:hidden"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="border-border border-b py-1">
          <WorkspaceSwitcher />
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Primary">
          <p className="text-muted-foreground/70 px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
            Navigation
          </p>
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ label, code, icon: Icon, href }) => {
              const isActive = href === pathname;
              return (
                <li key={code}>
                  <Link
                    href={href}
                    aria-current={isActive ? "page" : undefined}
                    className={[
                      "group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors",
                      "focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-2",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full transition-opacity",
                        isActive ? "bg-primary opacity-100" : "opacity-0",
                      ].join(" ")}
                      aria-hidden
                    />
                    <Icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
                    <span className="flex-1 text-left">{label}</span>
                    <span className="text-muted-foreground/50 font-mono text-[10px] uppercase tracking-wider">
                      {code}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-border flex items-center gap-2 border-t px-3 py-2.5">
          <div className="min-w-0 flex-1 px-2">
            <p className="text-muted-foreground/60 font-mono text-[10px] uppercase tracking-wider">
              Signed in
            </p>
            <p className="text-foreground/90 truncate text-xs" title={user?.email}>
              {user?.email ?? "…"}
            </p>
          </div>
          <button
            type="button"
            onClick={logout}
            aria-label="Sign out"
            className="text-muted-foreground hover:bg-sidebar-accent hover:text-foreground focus-visible:ring-ring rounded-md p-2 transition-colors focus-visible:outline-none focus-visible:ring-2"
          >
            <LogOut className="size-4" aria-hidden />
          </button>
        </div>

      </aside>

      {/* Main column */}
      <div className="flex min-h-screen min-w-0 flex-col lg:min-h-0">
        {isDemoUser(user) && (
          <div className="bg-primary/10 text-primary border-primary/20 shrink-0 border-b px-4 py-2 text-center text-xs sm:px-6">
            Demo workspace — read-only, pre-loaded with sample docs. Sign up to add your own
            sources.
          </div>
        )}
        <header className="border-border bg-background flex h-14 shrink-0 items-center justify-between gap-3 border-b px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label="Open menu"
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring -ml-1 rounded-md p-1 focus-visible:outline-none focus-visible:ring-2 lg:hidden"
            >
              <Menu className="size-5" />
            </button>
            <h1 className="truncate text-sm font-medium">{title}</h1>
            <span className="text-muted-foreground/70 hidden font-mono text-[11px] sm:inline">
              / workspace
            </span>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
