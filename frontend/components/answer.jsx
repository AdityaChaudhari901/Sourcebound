"use client";

import { FileText, Globe } from "lucide-react";

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";

function CitationMarker({ n, citation }) {
  return (
    <HoverCard openDelay={60} closeDelay={80}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          className="text-primary bg-primary/10 border-primary/20 hover:bg-primary/20 mx-px inline-flex h-[15px] min-w-[15px] items-center justify-center rounded border px-1 align-[1px] font-mono text-[10px] leading-none"
        >
          {n}
        </button>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="border-border bg-card w-80 p-3">
        <div className="flex items-center gap-2">
          {citation.external ? (
            <Globe className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
          ) : (
            <FileText className="text-muted-foreground size-3.5 shrink-0" aria-hidden />
          )}
          {citation.external ? (
            <a
              href={citation.source_uri}
              target="_blank"
              rel="noreferrer"
              className="text-primary truncate font-mono text-xs hover:underline"
              title={citation.source_uri}
            >
              {citation.source_uri}
            </a>
          ) : (
            <span className="text-primary truncate font-mono text-xs" title={citation.source_uri}>
              {citation.source_uri}
            </span>
          )}
          {citation.external && (
            <span className="border-border text-muted-foreground/80 ml-auto shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider">
              external
            </span>
          )}
        </div>
        <p className="text-muted-foreground mt-2 text-xs leading-relaxed">{citation.snippet}</p>
      </HoverCardContent>
    </HoverCard>
  );
}

/**
 * Renders an answer with inline [n] citation markers turned into interactive
 * chips — hover/focus reveals the source snippet and (for web sources) a link.
 */
export function Answer({ text, citations }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-wrap text-sm leading-relaxed">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const citation = citations?.[Number(match[1]) - 1];
          if (citation) return <CitationMarker key={i} n={match[1]} citation={citation} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
}
