import { FileText, Globe } from "lucide-react";

/**
 * Renders the sources behind an answer, numbered to match the [n] markers.
 * Internal docs show a file icon + mono path; external (web) sources show a globe
 * icon, an "external" badge, and a clickable link.
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
          <li key={c.chunk_id ?? i} className="border-border bg-card/60 rounded-md border p-3">
            <div className="flex items-center gap-2">
              <span className="bg-primary/10 text-primary border-primary/20 flex size-5 shrink-0 items-center justify-center rounded border font-mono text-[10px]">
                {i + 1}
              </span>
              {c.external ? (
                <>
                  <Globe className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
                  <a
                    href={c.source_uri}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary truncate font-mono text-xs underline-offset-2 hover:underline"
                    title={c.source_uri}
                  >
                    {c.source_uri}
                  </a>
                  <span className="border-border text-muted-foreground/80 ml-auto shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider">
                    external
                  </span>
                </>
              ) : (
                <>
                  <FileText className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
                  <span className="text-primary truncate font-mono text-xs" title={c.source_uri}>
                    {c.source_uri}
                  </span>
                </>
              )}
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{c.snippet}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
