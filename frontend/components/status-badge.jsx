const TONES = {
  ready: "border-emerald-500/30 text-emerald-400/90 bg-emerald-500/10",
  succeeded: "border-emerald-500/30 text-emerald-400/90 bg-emerald-500/10",
  processing: "border-primary/30 text-primary bg-primary/10",
  pending: "border-primary/30 text-primary bg-primary/10",
  running: "border-primary/30 text-primary bg-primary/10",
  queued: "border-border text-muted-foreground bg-card",
  failed: "border-red-500/30 text-red-400/90 bg-red-500/10",
};

/** Small status pill used across the management pages. */
export function StatusBadge({ status }) {
  const tone = TONES[status] ?? "border-border text-muted-foreground bg-card";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${tone}`}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {status}
    </span>
  );
}
