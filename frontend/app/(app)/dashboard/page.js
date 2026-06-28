"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Database,
  FileText,
  Gauge,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Tile } from "@/components/dashboard/tile";
import { Sparkline } from "@/components/dashboard/sparkline";
import { ErrorState } from "@/components/states";

function timeAgo(iso) {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtMs(ms) {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)}%`);

function Stat({ label, value, accent }) {
  return (
    <div>
      <p className={`font-mono text-2xl tabular-nums ${accent ? "text-primary" : "text-foreground"}`}>
        {value}
      </p>
      <p className="text-muted-foreground/60 mt-0.5 text-[11px] uppercase tracking-wider">{label}</p>
    </div>
  );
}

function ScoreCard({ label, value, accent }) {
  return (
    <div className="border-border/70 rounded-lg border px-3 py-2.5">
      <p className={`font-mono text-lg tabular-nums ${accent ? "text-primary" : "text-foreground"}`}>
        {value}
      </p>
      <p className="text-muted-foreground/60 mt-0.5 text-[10px] uppercase tracking-wider">{label}</p>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get("/dashboard"),
    refetchInterval: 30000,
  });

  const sc = data?.source_coverage;
  const aq = data?.answer_quality;
  const recent = data?.recent_answers ?? [];
  const ing = data?.ingestion_status;
  const lat = data?.latency;

  if (isError) return <ErrorState error={error} onRetry={refetch} />;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:auto-rows-[11rem]">
      {/* Ask Sourcebound — hero */}
      <Tile
        href="/ask"
        className="from-card to-card/40 bg-gradient-to-br sm:col-span-2 lg:col-span-2 lg:row-span-2"
      >
        <div className="flex h-full flex-col justify-between">
          <div className="flex items-center gap-2">
            <span className="bg-primary h-4 w-[3px] rounded-full" aria-hidden />
            <span className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">
              Ask Sourcebound
            </span>
          </div>
          <div>
            <h2 className="text-foreground max-w-sm text-2xl font-medium leading-tight tracking-tight">
              Ask your knowledge base.
            </h2>
            <p className="text-muted-foreground mt-2 max-w-md text-sm leading-relaxed">
              Citation-grounded answers over your own sources — streamed live, with every
              claim traceable to where it came from.
            </p>
          </div>
          <span className="text-primary inline-flex items-center gap-1.5 text-sm font-medium">
            Start asking <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </span>
        </div>
      </Tile>

      {/* Source Coverage */}
      <Tile title="Source Coverage" icon={Database} className="sm:col-span-2 lg:col-span-2">
        {isLoading ? (
          <div className="flex gap-8">
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-20" />
            <Skeleton className="h-12 w-24" />
          </div>
        ) : sc?.documents ? (
          <div className="flex h-full items-end justify-between gap-4">
            <Stat label="Documents" value={sc.documents} />
            <Stat label="Chunks" value={sc.chunks} />
            <Stat label="Ready" value={sc.ready} />
            <div className="text-right">
              <p className="text-foreground/80 font-mono text-sm">{timeAgo(sc.last_sync)}</p>
              <p className="text-muted-foreground/60 mt-0.5 text-[11px] uppercase tracking-wider">
                Last sync
              </p>
            </div>
          </div>
        ) : (
          <EmptyState text="No sources yet" href="/sources" cta="Add a source" />
        )}
      </Tile>

      {/* Answer Quality */}
      <Tile title="Answer Quality" icon={Gauge} className="lg:col-span-1">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : aq ? (
          <div className="grid h-full grid-cols-2 content-center gap-2">
            <ScoreCard label="Faithful" value={pct(aq.faithfulness)} accent />
            <ScoreCard label="Relevancy" value={pct(aq.answer_relevancy)} />
            <ScoreCard label="Precision" value={pct(aq.context_precision)} />
            <ScoreCard label="Recall" value={pct(aq.context_recall)} />
          </div>
        ) : (
          <EmptyState text="No eval run yet" />
        )}
      </Tile>

      {/* Ingestion Status */}
      <Tile title="Ingestion" icon={Activity} className="lg:col-span-1">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : ing ? (
          <div className="flex h-full flex-col justify-center gap-2 text-sm">
            <Row dot="bg-primary" label="Active" value={ing.queued + ing.running} />
            <Row dot="bg-emerald-500/70" label="Succeeded" value={ing.succeeded} />
            <Row dot="bg-red-500/70" label="Failed" value={ing.failed} muted={ing.failed === 0} />
          </div>
        ) : (
          <EmptyState text="No ingestion jobs" />
        )}
      </Tile>

      {/* Recent Answers */}
      <Tile title="Recent Answers" icon={MessageSquareText} className="sm:col-span-2 lg:col-span-2 lg:row-span-2">
        {isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : recent.length ? (
          <ul className="h-full divide-y divide-[var(--border)] overflow-auto">
            {recent.map((a) => (
              <li key={a.id} className="flex items-start gap-3 py-2.5 first:pt-0">
                <FileText className="text-muted-foreground/40 mt-0.5 size-3.5 shrink-0" aria-hidden />
                <p className="text-foreground/90 flex-1 truncate text-sm">{a.snippet}</p>
                <span className="text-muted-foreground/60 shrink-0 font-mono text-[11px]">
                  {a.citation_count} cite{a.citation_count === 1 ? "" : "s"}
                </span>
                <span className="text-muted-foreground/40 shrink-0 font-mono text-[11px]">
                  {timeAgo(a.created_at)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState text="No answers yet" href="/ask" cta="Ask a question" />
        )}
      </Tile>

      {/* Latency & Cost */}
      <Tile title="Latency & Cost" icon={Sparkles} className="sm:col-span-2 lg:col-span-2 lg:row-span-2">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : lat?.recent_ms?.length ? (
          <div className="flex h-full flex-col justify-between">
            <div className="flex items-start justify-between">
              <Stat label="Avg latency" value={fmtMs(lat.avg_ms)} accent />
              <Stat label="p95" value={fmtMs(lat.p95_ms)} />
              <div className="text-right">
                <p className="text-foreground font-mono text-2xl tabular-nums">
                  ${lat.est_cost_usd?.toFixed?.(3) ?? "0.000"}
                </p>
                <p className="text-muted-foreground/60 mt-0.5 text-[11px] uppercase tracking-wider">
                  Est. cost
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Sparkline data={lat.recent_ms} className="h-12" />
              <p className="text-muted-foreground/50 mt-1 font-mono text-[10px]">
                last {lat.recent_ms.length} answers · {lat.answers_total} total
              </p>
            </div>
          </div>
        ) : (
          <EmptyState text="No queries yet" href="/ask" cta="Ask a question" />
        )}
      </Tile>
    </div>
  );
}

function Row({ dot, label, value, muted }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`size-2 rounded-full ${muted ? "bg-muted-foreground/30" : dot}`} aria-hidden />
      <span className="text-muted-foreground flex-1">{label}</span>
      <span className={`font-mono tabular-nums ${muted ? "text-muted-foreground/60" : "text-foreground"}`}>
        {value}
      </span>
    </div>
  );
}

function EmptyState({ text, href, cta }) {
  return (
    <div className="flex h-full flex-col items-start justify-center gap-2">
      <p className="text-muted-foreground/60 text-sm">{text}</p>
      {href && (
        <Link href={href} className="text-primary inline-flex items-center gap-1 text-xs hover:underline">
          {cta} <ArrowRight className="size-3" />
        </Link>
      )}
    </div>
  );
}
