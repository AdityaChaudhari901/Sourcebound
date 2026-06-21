"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Gauge, Globe, MessageSquareText, RefreshCw, Zap } from "lucide-react";

import { api } from "@/lib/api";
import { fmtDate, fmtMs, pct, timeAgo } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";

// Per-trace deep links require instrumenting the query path with Langfuse spans;
// for now we link to the project dashboard.
const LANGFUSE_URL = "https://us.cloud.langfuse.com";

function NodeBadges({ trace }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {trace.grounding != null && (
        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-400/90">
          <Gauge className="size-3" aria-hidden /> {pct(trace.grounding)}
        </span>
      )}
      {trace.self_corrected && (
        <span className="border-border text-muted-foreground/80 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]">
          <RefreshCw className="size-3" aria-hidden /> self-corrected
        </span>
      )}
      {trace.used_web_search && (
        <span className="border-border text-muted-foreground/80 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]">
          <Globe className="size-3" aria-hidden /> web
        </span>
      )}
    </div>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div className="border-border rounded-lg border p-3">
      <p className="text-muted-foreground/60 flex items-center gap-1.5 text-[11px] uppercase tracking-wider">
        {Icon && <Icon className="size-3" aria-hidden />} {label}
      </p>
      <p className="text-foreground mt-1 font-mono text-lg tabular-nums">{value}</p>
    </div>
  );
}

function Detail({ trace }) {
  if (!trace) {
    return (
      <div className="border-border text-muted-foreground/50 flex h-full items-center justify-center rounded-lg border border-dashed p-8 text-sm">
        Select a trace to inspect it.
      </div>
    );
  }
  return (
    <div className="border-border bg-card/60 space-y-4 rounded-lg border p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">Trace</p>
          <p className="text-foreground/90 mt-1 font-mono text-[11px]">{trace.id}</p>
          <p className="text-muted-foreground/50 mt-0.5 text-xs">{fmtDate(trace.created_at)}</p>
        </div>
        <a
          href={LANGFUSE_URL}
          target="_blank"
          rel="noreferrer"
          className="border-border hover:border-foreground/20 hover:bg-sidebar-accent text-foreground/80 inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors"
        >
          Open in Langfuse <ArrowUpRight className="size-3.5" />
        </a>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric icon={Zap} label="Latency" value={fmtMs(trace.latency_ms)} />
        <Metric label="Tokens" value={`~${trace.est_tokens}`} />
        <Metric label="Est. cost" value={`$${trace.est_cost_usd.toFixed(4)}`} />
        <Metric icon={MessageSquareText} label="Citations" value={trace.citation_count} />
      </div>

      <div>
        <p className="text-muted-foreground/60 mb-1.5 text-[11px] uppercase tracking-wider">Nodes fired</p>
        <NodeBadges trace={trace} />
      </div>

      <div>
        <p className="text-muted-foreground/60 mb-1.5 text-[11px] uppercase tracking-wider">Answer</p>
        <p className="text-foreground/85 whitespace-pre-wrap text-sm leading-relaxed">{trace.answer}</p>
      </div>
    </div>
  );
}

export default function TracesPage() {
  const { data: traces, isLoading } = useQuery({
    queryKey: ["traces"],
    queryFn: () => api.get("/traces"),
  });
  const [selectedId, setSelectedId] = useState(null);
  const selected = (traces ?? []).find((t) => t.id === selectedId) ?? traces?.[0];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-base font-medium">Traces</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Recent query traces — latency, cost, and which graph nodes fired.
          </p>
        </div>
        <a
          href={LANGFUSE_URL}
          target="_blank"
          rel="noreferrer"
          className="text-muted-foreground/60 hover:text-foreground inline-flex items-center gap-1 font-mono text-[11px]"
        >
          Langfuse <ArrowUpRight className="size-3" />
        </a>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      ) : traces?.length ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
          {/* List */}
          <div className="border-border divide-border divide-y overflow-hidden rounded-lg border">
            {traces.map((t) => {
              const active = selected?.id === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedId(t.id)}
                  className={`flex w-full flex-col gap-2 px-4 py-3 text-left transition-colors ${
                    active ? "bg-sidebar-accent" : "hover:bg-sidebar-accent/50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-foreground/90 line-clamp-1 flex-1 text-sm">{t.snippet}</p>
                    <span className="text-muted-foreground/40 shrink-0 font-mono text-[11px]">
                      {timeAgo(t.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <NodeBadges trace={t} />
                    <span className="text-muted-foreground/60 shrink-0 font-mono text-[11px] tabular-nums">
                      {fmtMs(t.latency_ms)} · ${t.est_cost_usd.toFixed(4)}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Detail */}
          <div className="lg:sticky lg:top-6 lg:self-start">
            <Detail trace={selected} />
          </div>
        </div>
      ) : (
        <p className="text-muted-foreground/60 py-12 text-center text-sm">
          No traces yet. Ask a question to generate one.
        </p>
      )}
    </div>
  );
}
