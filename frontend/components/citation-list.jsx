import { FileText } from "lucide-react";

/**
 * Renders the sources behind an answer. Each citation shows its source (mono,
 * accent) and a snippet (muted), numbered to match the [n] markers in the answer.
 */
export function CitationList({ citations }) {
  if (!citations?.length) return null;

  return (
    <div className="space-y-2">
      <p className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">
        Sources · {citations.length}
      </p>
      <ol className="space-y-2">
        {citations.map((c, i) => (
          <li
            key={c.chunk_id ?? i}
            className="border-border bg-card/60 rounded-md border p-3"
          >
            <div className="flex items-center gap-2">
              <span className="bg-primary/10 text-primary border-primary/20 flex size-5 shrink-0 items-center justify-center rounded border font-mono text-[10px]">
                {i + 1}
              </span>
              <FileText className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
              <span className="text-primary truncate font-mono text-xs" title={c.source_uri}>
                {c.source_uri}
              </span>
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{c.snippet}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
