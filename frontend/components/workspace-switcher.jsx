"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, Check, ChevronsUpDown } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/**
 * Active-workspace selector. One workspace per user for now, so the list has a
 * single entry; the dropdown is the seam for multi-workspace membership later.
 */
export function WorkspaceSwitcher() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  const { data: workspaces } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => api.get("/auth/workspaces"),
    enabled: !!user,
  });

  const current = user?.workspace;

  return (
    <div className="relative px-3 py-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="border-border hover:bg-sidebar-accent focus-visible:ring-ring flex w-full items-center gap-2 rounded-md border px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2"
      >
        <Building2 className="text-muted-foreground size-4 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-muted-foreground/60 font-mono text-[9px] uppercase tracking-wider">
            Workspace
          </p>
          <p className="text-foreground/90 truncate text-xs" title={current?.name}>
            {current?.name ?? "…"}
          </p>
        </div>
        <ChevronsUpDown className="text-muted-foreground/60 size-3.5 shrink-0" aria-hidden />
      </button>

      {open && (
        <div className="border-border bg-card absolute left-3 right-3 top-full z-10 mt-1 rounded-md border p-1 shadow-lg">
          <p className="text-muted-foreground/60 px-2 py-1 font-mono text-[9px] uppercase tracking-wider">
            Workspaces
          </p>
          {(workspaces ?? []).map((w) => (
            <button
              key={w.id}
              type="button"
              onClick={() => setOpen(false)}
              className="hover:bg-sidebar-accent flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs"
            >
              <span className="truncate flex-1">{w.name}</span>
              {w.id === current?.id && <Check className="text-primary size-3.5 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
