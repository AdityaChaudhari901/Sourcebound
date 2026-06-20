"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2, Upload } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function SourcesPage() {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");

  const mutation = useMutation({
    mutationFn: ({ file, title }) => {
      const form = new FormData();
      form.append("file", file);
      if (title.trim()) form.append("title", title.trim());
      return api.upload("/ingest", form);
    },
  });

  const submit = (event) => {
    event.preventDefault();
    if (!file || mutation.isPending) return;
    mutation.mutate({ file, title });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-base font-medium">Add a source</h2>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Upload a PDF or Markdown file. It&apos;s parsed, chunked, embedded, and indexed so the
          Ask page can answer from it — with citations.
        </p>
      </div>

      <form onSubmit={submit} className="border-border bg-card space-y-4 rounded-lg border p-5">
        <div className="space-y-2">
          <Label htmlFor="file">File</Label>
          <Input
            id="file"
            type="file"
            accept=".pdf,.md,.markdown,application/pdf,text/markdown"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file && (
            <p className="text-muted-foreground font-mono text-xs">
              {file.name} · {(file.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="title">
            Title <span className="text-muted-foreground/60">(optional)</span>
          </Label>
          <Input
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Payments Runbook"
          />
        </div>

        <Button type="submit" disabled={!file || mutation.isPending} className="w-full">
          {mutation.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Ingesting…
            </>
          ) : (
            <>
              <Upload className="size-4" /> Ingest
            </>
          )}
        </Button>
      </form>

      {mutation.isError && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Ingestion failed</AlertTitle>
          <AlertDescription>{mutation.error?.message ?? "Upload failed."}</AlertDescription>
        </Alert>
      )}

      {mutation.isSuccess && (
        <div className="border-primary/30 bg-primary/5 rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="text-primary size-4" />
            <p className="text-sm font-medium">Ingested</p>
          </div>
          <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-y-1 font-mono text-xs">
            <dt className="text-muted-foreground/60">document_id</dt>
            <dd className="text-foreground/90 truncate" title={mutation.data.document_id}>
              {mutation.data.document_id}
            </dd>
            <dt className="text-muted-foreground/60">chunks</dt>
            <dd className="text-primary">{mutation.data.chunk_count}</dd>
            <dt className="text-muted-foreground/60">type</dt>
            <dd className="text-foreground/90">{mutation.data.source_type}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
