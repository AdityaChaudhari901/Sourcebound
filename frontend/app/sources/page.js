"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2, Upload } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const TERMINAL = new Set(["succeeded", "failed"]);

const STATE_LABEL = {
  queued: "Queued",
  running: "Processing",
  succeeded: "Ready",
  failed: "Failed",
};

export default function SourcesPage() {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState("");
  const [jobId, setJobId] = useState(null);

  // 1) Upload -> enqueue -> returns a job id immediately (202).
  const upload = useMutation({
    mutationFn: ({ file, title }) => {
      const form = new FormData();
      form.append("file", file);
      if (title.trim()) form.append("title", title.trim());
      return api.upload("/ingest", form);
    },
    onSuccess: (data) => setJobId(data.job_id),
  });

  // 2) Poll job status until it reaches a terminal state.
  const status = useQuery({
    queryKey: ["ingest-status", jobId],
    queryFn: () => api.get(`/ingest/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) =>
      TERMINAL.has(query.state.data?.state) ? false : 1500,
  });

  const job = status.data;
  const polling = !!jobId && (!job || !TERMINAL.has(job.state));

  const submit = (event) => {
    event.preventDefault();
    if (!file || upload.isPending || polling) return;
    setJobId(null);
    upload.mutate({ file, title });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-base font-medium">Add a source</h2>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          Upload a PDF or Markdown file. Ingestion runs in the background — you&apos;ll see
          live status as it&apos;s parsed, chunked, embedded, and indexed.
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

        <Button type="submit" disabled={!file || upload.isPending || polling} className="w-full">
          {upload.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Uploading…
            </>
          ) : polling ? (
            <>
              <Loader2 className="size-4 animate-spin" /> {STATE_LABEL[job?.state] ?? "Queued"}…
            </>
          ) : (
            <>
              <Upload className="size-4" /> Ingest
            </>
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

      {/* Live job status */}
      {job && (
        <div className="border-border bg-card rounded-lg border p-4">
          <div className="flex items-center gap-2">
            {job.state === "succeeded" ? (
              <CheckCircle2 className="text-primary size-4" />
            ) : job.state === "failed" ? (
              <AlertCircle className="size-4 text-red-400" />
            ) : (
              <Loader2 className="text-muted-foreground size-4 animate-spin" />
            )}
            <p className="text-sm font-medium">{STATE_LABEL[job.state] ?? job.state}</p>
            <span className="text-muted-foreground/50 ml-auto font-mono text-[10px] uppercase tracking-wider">
              {job.state}
            </span>
          </div>

          <dl className="mt-3 grid grid-cols-[7rem_1fr] gap-y-1 font-mono text-xs">
            <dt className="text-muted-foreground/60">job_id</dt>
            <dd className="text-foreground/90 truncate" title={job.job_id}>{job.job_id}</dd>
            <dt className="text-muted-foreground/60">document_id</dt>
            <dd className="text-foreground/90 truncate" title={job.document_id}>{job.document_id}</dd>
            {job.state === "succeeded" && (
              <>
                <dt className="text-muted-foreground/60">chunks</dt>
                <dd className="text-primary">{job.chunk_count}</dd>
              </>
            )}
          </dl>

          {job.state === "failed" && job.error && (
            <p className="mt-2 text-xs leading-relaxed text-red-400">{job.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
