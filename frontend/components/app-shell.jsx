import {
  Activity,
  Database,
  FlaskConical,
  MessageSquareText,
  Settings2,
} from "lucide-react";

// Nav placeholders only — routing is wired up in later slices.
// `code` is the monospace shorthand shown on the right of each item.
const NAV_ITEMS = [
  { label: "Ask", code: "ask", icon: MessageSquareText, active: true },
  { label: "Sources", code: "src", icon: Database },
  { label: "Evaluations", code: "eval", icon: FlaskConical },
  { label: "Traces", code: "trc", icon: Activity },
  { label: "Settings", code: "cfg", icon: Settings2 },
];

const ENV = process.env.NEXT_PUBLIC_ENV ?? "local";
const VERSION = "0.1.0";

export function AppShell({ children }) {
  return (
    <div className="grid h-screen grid-cols-[240px_1fr] overflow-hidden">
      {/* Sidebar */}
      <aside className="bg-sidebar border-border flex flex-col border-r">
        {/* Brand — the small amber bar is the "source rail" motif */}
        <div className="border-border flex h-14 items-center gap-2.5 border-b px-5">
          <span className="bg-primary h-4 w-[3px] rounded-full" aria-hidden />
          <span className="text-sm font-semibold tracking-tight">Sourcebound</span>
        </div>

        {/* Primary navigation */}
        <nav className="flex-1 px-3 py-4" aria-label="Primary">
          <p className="text-muted-foreground/70 px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
            Workspace
          </p>
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ label, code, icon: Icon, active }) => (
              <li key={code}>
                <button
                  type="button"
                  aria-current={active ? "page" : undefined}
                  className={[
                    "group relative flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors",
                    "focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-2",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                  ].join(" ")}
                >
                  {/* active "source rail" */}
                  <span
                    className={[
                      "absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full transition-opacity",
                      active ? "bg-primary opacity-100" : "opacity-0",
                    ].join(" ")}
                    aria-hidden
                  />
                  <Icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
                  <span className="flex-1 text-left">{label}</span>
                  <span className="text-muted-foreground/50 font-mono text-[10px] uppercase tracking-wider">
                    {code}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Status readout — monospace instrument footer (the signature) */}
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
            <h1 className="text-sm font-medium">Ask</h1>
            <span className="text-muted-foreground/70 font-mono text-[11px]">/ workspace</span>
          </div>
          <span className="text-muted-foreground/60 font-mono text-[11px]">
            sourcebound · {ENV}
          </span>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
