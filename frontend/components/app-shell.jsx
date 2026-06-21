"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Database,
  FlaskConical,
  LayoutGrid,
  LogOut,
  MessageSquareText,
  Settings2,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { WorkspaceSwitcher } from "@/components/workspace-switcher";

// `href: null` = not built yet (inert placeholder). `code` is the mono shorthand.
const NAV_ITEMS = [
  { label: "Dashboard", code: "dsh", icon: LayoutGrid, href: "/" },
  { label: "Ask", code: "ask", icon: MessageSquareText, href: "/ask" },
  { label: "Sources", code: "src", icon: Database, href: "/sources" },
  { label: "Evaluations", code: "eval", icon: FlaskConical, href: "/evaluations" },
  { label: "Traces", code: "trc", icon: Activity, href: "/traces" },
  { label: "Settings", code: "cfg", icon: Settings2, href: null },
];

const ENV = process.env.NEXT_PUBLIC_ENV ?? "local";
const VERSION = "0.1.0";

export function AppShell({ children }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const active = NAV_ITEMS.find((item) => item.href === pathname);
  const title = active?.label ?? "Sourcebound";

  return (
    <div className="grid h-screen grid-cols-[240px_1fr] overflow-hidden">
      {/* Sidebar */}
      <aside className="bg-sidebar border-border flex flex-col border-r">
        <div className="border-border flex h-14 items-center gap-2.5 border-b px-5">
          <span className="bg-primary h-4 w-[3px] rounded-full" aria-hidden />
          <span className="text-sm font-semibold tracking-tight">Sourcebound</span>
        </div>

        {/* Active workspace switcher */}
        <div className="border-border border-b py-1">
          <WorkspaceSwitcher />
        </div>

        <nav className="flex-1 px-3 py-4" aria-label="Primary">
          <p className="text-muted-foreground/70 px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
            Navigation
          </p>
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ label, code, icon: Icon, href }) => {
              const isActive = href === pathname;
              const content = (
                <>
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
                </>
              );
              const base =
                "group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors";

              return (
                <li key={code}>
                  {href ? (
                    <Link
                      href={href}
                      aria-current={isActive ? "page" : undefined}
                      className={[
                        base,
                        "focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-2",
                        isActive
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                      ].join(" ")}
                    >
                      {content}
                    </Link>
                  ) : (
                    <span
                      aria-disabled="true"
                      title="Coming soon"
                      className={[base, "text-muted-foreground/40 cursor-not-allowed"].join(" ")}
                    >
                      {content}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Signed-in user + logout */}
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
            title="Sign out"
            className="text-muted-foreground hover:bg-sidebar-accent hover:text-foreground focus-visible:ring-ring rounded-md p-2 transition-colors focus-visible:outline-none focus-visible:ring-2"
          >
            <LogOut className="size-4" aria-hidden />
          </button>
        </div>

        <div className="border-border text-muted-foreground border-t px-5 py-3 font-mono text-[11px] leading-5">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground/60">env</span>
            <span className="text-foreground/80">{ENV}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground/60">ver</span>
            <span className="text-foreground/80">{VERSION}</span>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-col">
        <header className="border-border flex h-14 shrink-0 items-center justify-between border-b px-6">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-medium">{title}</h1>
            <span className="text-muted-foreground/70 font-mono text-[11px]">/ workspace</span>
          </div>
          <span className="text-muted-foreground/60 font-mono text-[11px]">sourcebound · {ENV}</span>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
