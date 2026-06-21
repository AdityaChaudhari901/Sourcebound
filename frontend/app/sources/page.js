"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Clock, FileText, Loader2, RefreshCw, Upload } from "lucide-react";

import { api } from "@/lib/api";
import { daysSince, timeAgo } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";

const STALE_DAYS = 30;
const ACTIVE = new Set(["pending", "processing"]);

function DocumentRow({ doc }) {
  const qc = useQueryClient();
  const reingest = useMutation({
    mutationFn: () => api.post(`/documents/${doc.id}/reingest`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const stale = (() => {
    const d = daysSince(doc.last_modified ?? doc.created_at);
    return d != null && d > STALE_DAYS;
  })();

  return (
    <div className="border-border grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-4 border-t px-4 py-3 first:border-t-0">
      <div className="flex min-w-0 items-center gap-2.5">
        <FileText className="text-muted-foreground/50 size-4 shrink-0" aria-hidden />
        <div className="min-w-0">
          <p className="text-foreground/90 truncate text-sm">{doc.title || doc.uri}</p>
          <p className="text-muted-foreground/50 truncate font-mono text-[11px]">{doc.uri}</p>
        </div>
      </div>
      <span className="text-muted-foreground/60 hidden font-mono text-[11px] uppercase sm:block">
        {doc.source_type}
      </span>
      <span className="text-foreground/80 font-mono text-sm tabular-nums">{doc.chunk_count}</span>
      <div className="flex items-center gap-2">
        <StatusBadge status={doc.status} />
        {stale && (
          <span
            className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber-400/90"
            title={`Not synced in over ${STALE_DAYS} days`}
          >
            <Clock className="size-3" aria-hidden /> stale
          </span>
        )}
      </div>
      <div className="flex items-center justify-end gap-3">
        <span className="text-muted-foreground/40 hidden font-mono text-[11px] md:block">
          {timeAgo(doc.last_modified ?? doc.created_at)}
        </span>
        <button
          type="button"
          onClick={() => reingest.mutate()}
          disabled={reingest.isPending || ACTIVE.has(doc.status)}
          title="Re-index this document"
          className="text-muted-foreground/60 hover:bg-sidebar-accent hover:text-foreground rounded-md p-1.5 transition-colors disabled:opacity-40"
        >
          <RefreshCw className={`size-3.5 ${reingest.isPending ? "animate-spin" : ""}`} />
        </button>
      </div>
    </div>
  );
}

export default function SourcesPage() {
  const qc = useQueryClient();
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");

  const { data: documents, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get("/documents"),
    refetchInterval: (q) =>
      (q.state.data ?? []).some((d) => ACTIVE.has(d.status)) ? 2000 : false,
  });

  const upload = useMutation({
    mutationFn: ({ file, title }) => {
      const form = new FormData();
      form.append("file", file);
      if (title.trim()) form.append("title", title.trim());
      return api.upload("/ingest", form);
    },
    onSuccess: () => {
      setFile(null);
      setTitle("");
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const submit = (e) => {
    e.preventDefault();
    if (!file || upload.isPending) return;
    upload.mutate({ file, title });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-base font-medium">Sources</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Ingested documents, indexing status, and re-indexing.
        </p>
      </div>

      {/* Add a source */}
      <form
        onSubmit={submit}
        className="border-border bg-card flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-end"
      >
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="file" className="text-xs">File (PDF or Markdown)</Label>
          <Input
            id="file"
            type="file"
            accept=".pdf,.md,.markdown,application/pdf,text/markdown"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="title" className="text-xs">Title (optional)</Label>
          <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Payments Runbook" />
        </div>
        <Button type="submit" disabled={!file || upload.isPending}>
          {upload.isPending ? (
            <><Loader2 className="size-4 animate-spin" /> Uploading…</>
          ) : (
            <><Upload className="size-4" /> Ingest</>
          )}
        </Button>
      </form>

      {upload.isError && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Upload failed</AlertTitle>
          <AlertDescription>{upload.error?.message ?? "Could not enqueue ingestion."}</AlertDescription>
        </Alert>
      )}

      {/* Documents table */}
      <div className="border-border overflow-hidden rounded-lg border">
        <div className="border-border text-muted-foreground/60 grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b px-4 py-2.5 font-mono text-[10px] uppercase tracking-wider">
          <span>Document</span>
          <span className="hidden sm:block">Type</span>
          <span>Chunks</span>
          <span>Status</span>
          <span className="text-right">Actions</span>
        </div>
        {isLoading ? (
          <div className="space-y-3 p-4">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-8 w-full" />)}
          </div>
        ) : documents?.length ? (
          documents.map((doc) => <DocumentRow key={doc.id} doc={doc} />)
        ) : (
          <p className="text-muted-foreground/60 px-4 py-8 text-center text-sm">
            No documents yet. Upload one above to get started.
          </p>
        )}
      </div>
    </div>
  );
}
