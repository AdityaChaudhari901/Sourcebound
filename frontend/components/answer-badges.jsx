import { Globe, RefreshCw, ShieldCheck } from "lucide-react";

function GroundingBadge({ value }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.8
      ? "border-emerald-500/30 text-emerald-400/90 bg-emerald-500/10"
      : value >= 0.5
        ? "border-primary/30 text-primary bg-primary/10"
        : "border-red-500/30 text-red-400/90 bg-red-500/10";
  const label = value >= 0.8 ? "Grounded" : value >= 0.5 ? "Partial" : "Low confidence";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] ${tone}`}
      title="Grounding confidence from the verify node"
    >
      <ShieldCheck className="size-3" aria-hidden /> {label} {pct}%
    </span>
  );
}

function PathBadge({ icon: Icon, label, title }) {
  return (
    <span
      className="border-border text-muted-foreground/80 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px]"
      title={title}
    >
      <Icon className="size-3" aria-hidden /> {label}
    </span>
  );
}

/** Subtle per-answer signals: grounding + which corrective paths fired. */
export function AnswerBadges({ grounding, selfCorrected, usedWebSearch }) {
  if (grounding == null && !selfCorrected && !usedWebSearch) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {grounding != null && <GroundingBadge value={grounding} />}
      {selfCorrected && (
        <PathBadge icon={RefreshCw} label="self-corrected" title="The query was rewritten and re-retrieved" />
      )}
      {usedWebSearch && (
        <PathBadge icon={Globe} label="web fallback" title="Answered from a web search fallback" />
      )}
    </div>
  );
}
