"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";

import { api } from "@/lib/api";
import { fmtDate, pct } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline } from "@/components/dashboard/sparkline";
import { EmptyState, ErrorState } from "@/components/states";

const METRICS = [
  { key: "faithfulness", label: "Faithfulness", accent: true },
  { key: "answer_relevancy", label: "Answer relevancy" },
  { key: "context_precision", label: "Context precision" },
  { key: "context_recall", label: "Context recall" },
];

function TrendCard({ label, accent, series }) {
  const latest = series[series.length - 1];
  return (
    <div className="border-border bg-card/60 rounded-xl border p-4">
      <p className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">
        {label}
      </p>
      <p className={`mt-1 font-mono text-2xl tabular-nums ${accent ? "text-primary" : "text-foreground"}`}>
        {pct(latest)}
      </p>
      <div className="mt-2 h-8">{series.length > 1 && <Sparkline data={series} className="h-8" />}</div>
    </div>
  );
}

function RunSelect({ label, value, onChange, runs }) {
  return (
    <label className="flex-1 space-y-1.5">
      <span className="text-muted-foreground/60 font-mono text-[10px] uppercase tracking-wider">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="border-border bg-card text-foreground/90 focus-visible:ring-ring w-full rounded-md border px-2.5 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2"
      >
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            {fmtDate(r.created_at)} · {r.dataset}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function EvaluationsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["eval-runs"],
    queryFn: () => api.get("/eval-runs"),
  });

  const runs = useMemo(() => data ?? [], [data]); // newest first
  const chrono = useMemo(() => [...runs].reverse(), [runs]); // oldest first

  const [baselineId, setBaselineId] = useState(null);
  const [candidateId, setCandidateId] = useState(null);
  const baseline = runs.find((r) => r.id === baselineId) ?? chrono[0];
  const candidate = runs.find((r) => r.id === candidateId) ?? runs[0];

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 w-full" />)}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-base font-medium">Evaluations</h1>
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  if (!runs.length) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <h1 className="text-base font-medium">Evaluations</h1>
        <EmptyState
          icon={FlaskConical}
          title="No eval runs yet"
          hint="Run python eval/run_eval.py from the backend to score answer quality."
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-base font-medium">Evaluations</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Answer-quality metrics over {runs.length} run{runs.length === 1 ? "" : "s"}.
        </p>
      </div>

      {/* Trends */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {METRICS.map((m) => (
          <TrendCard key={m.key} label={m.label} accent={m.accent} series={chrono.map((r) => r[m.key])} />
        ))}
      </div>

      {/* Before / after compare */}
      <div className="border-border bg-card/60 rounded-xl border p-5">
        <p className="text-muted-foreground/70 mb-3 font-mono text-[10px] uppercase tracking-[0.18em]">
          Before / after
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <RunSelect label="Baseline" value={baseline?.id} onChange={setBaselineId} runs={runs} />
          <RunSelect label="Candidate" value={candidate?.id} onChange={setCandidateId} runs={runs} />
        </div>
        <div className="mt-4 space-y-1">
          {METRICS.map((m) => {
            const a = baseline?.[m.key];
            const b = candidate?.[m.key];
            const delta = b - a;
            const tone = delta > 0.001 ? "text-emerald-400" : delta < -0.001 ? "text-red-400" : "text-muted-foreground/60";
            return (
              <div key={m.key} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 font-mono text-sm">
                <span className="text-muted-foreground">{m.label}</span>
                <span className="text-foreground/80 w-12 text-right tabular-nums">{pct(a)}</span>
                <span className="text-foreground w-12 text-right tabular-nums">{pct(b)}</span>
                <span className={`w-16 text-right tabular-nums ${tone}`}>
                  {delta > 0 ? "+" : ""}{Math.round(delta * 100)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Runs table */}
      <div className="border-border overflow-hidden rounded-lg border">
        <div className="border-border text-muted-foreground/60 grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b px-4 py-2.5 font-mono text-[10px] uppercase tracking-wider">
          <span>Run</span><span>Faith</span><span>Relev</span><span>Prec</span><span>Recall</span>
        </div>
        {runs.map((r) => (
          <div key={r.id} className="border-border grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-4 border-t px-4 py-3 first:border-t-0">
            <div className="min-w-0">
              <p className="text-foreground/90 flex items-center gap-2 text-sm">
                <FlaskConical className="text-muted-foreground/40 size-3.5" aria-hidden />
                {fmtDate(r.created_at)}
              </p>
              <p className="text-muted-foreground/50 truncate font-mono text-[11px]">
                {r.dataset} · {r.num_questions}q · {r.llm_model}
              </p>
            </div>
            <span className="text-primary w-10 text-right font-mono text-sm tabular-nums">{pct(r.faithfulness)}</span>
            <span className="text-foreground/80 w-10 text-right font-mono text-sm tabular-nums">{pct(r.answer_relevancy)}</span>
            <span className="text-foreground/80 w-10 text-right font-mono text-sm tabular-nums">{pct(r.context_precision)}</span>
            <span className="text-foreground/80 w-10 text-right font-mono text-sm tabular-nums">{pct(r.context_recall)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
