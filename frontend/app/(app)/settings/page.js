"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Copy, KeyRound, Loader2, Plus, ShieldCheck, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";
import { fmtDate, timeAgo } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/states";

function CreatedKeyBanner({ apiKey, onDismiss }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — select and copy manually");
    }
  };
  return (
    <div
      role="status"
      className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4"
    >
      <p className="text-foreground/90 text-sm font-medium">Your new API key</p>
      <p className="text-muted-foreground/80 mt-0.5 text-xs">
        Copy it now — for security it won&apos;t be shown again.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <code className="border-border bg-card text-foreground/90 min-w-0 flex-1 truncate rounded-md border px-3 py-2 font-mono text-xs">
          {apiKey}
        </code>
        <Button type="button" variant="outline" onClick={copy} aria-label="Copy API key">
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </Button>
        <Button type="button" variant="ghost" onClick={onDismiss} aria-label="Dismiss">
          <X className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function ApiKeysSection() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [createdKey, setCreatedKey] = useState(null);
  const [confirmingId, setConfirmingId] = useState(null);

  const { data: keys, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get("/auth/api-keys"),
  });

  const create = useMutation({
    mutationFn: (name) => api.post("/auth/api-keys", { name }),
    onSuccess: (res) => {
      setCreatedKey(res.api_key);
      setName("");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success(`API key “${res.name}” created`);
    },
    onError: (err) => toast.error(err?.message ?? "Couldn't create key"),
  });

  const revoke = useMutation({
    mutationFn: (id) => api.del(`/auth/api-keys/${id}`),
    onSuccess: () => {
      setConfirmingId(null);
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success("API key revoked");
    },
    onError: (err) => toast.error(err?.message ?? "Couldn't revoke key"),
  });

  const submit = (e) => {
    e.preventDefault();
    if (!name.trim() || create.isPending) return;
    create.mutate(name.trim());
  };

  const active = (keys ?? []).filter((k) => !k.revoked_at);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <KeyRound className="text-muted-foreground/60 size-4" aria-hidden />
        <h2 className="text-sm font-medium">API keys</h2>
      </div>
      <p className="text-muted-foreground -mt-2 text-sm">
        Programmatic access to the API. Keys are shown once at creation and stored hashed.
      </p>

      {createdKey && <CreatedKeyBanner apiKey={createdKey} onDismiss={() => setCreatedKey(null)} />}

      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1 space-y-1.5">
          <Label htmlFor="key-name" className="text-xs">Key name</Label>
          <Input
            id="key-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. CI pipeline"
            maxLength={80}
          />
        </div>
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          {create.isPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
          Create key
        </Button>
      </form>

      <div className="border-border overflow-hidden rounded-lg border">
        {isLoading ? (
          <div className="space-y-3 p-4">
            {[0, 1].map((i) => <Skeleton key={i} className="h-8 w-full" />)}
          </div>
        ) : isError ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : active.length ? (
          active.map((k) => (
            <div
              key={k.id}
              className="border-border flex items-center gap-4 border-t px-4 py-3 first:border-t-0"
            >
              <div className="min-w-0 flex-1">
                <p className="text-foreground/90 truncate text-sm">{k.name}</p>
                <p className="text-muted-foreground/50 truncate font-mono text-[11px]">
                  {k.prefix}··· · created {fmtDate(k.created_at)} ·{" "}
                  {k.last_used_at ? `used ${timeAgo(k.last_used_at)}` : "never used"}
                </p>
              </div>
              {confirmingId === k.id ? (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">Revoke?</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    onClick={() => revoke.mutate(k.id)}
                    disabled={revoke.isPending}
                  >
                    {revoke.isPending ? <Loader2 className="size-3.5 animate-spin" /> : "Yes"}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmingId(null)}>
                    No
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmingId(k.id)}
                  aria-label={`Revoke ${k.name}`}
                  className="text-muted-foreground/60 hover:bg-sidebar-accent rounded-md p-1.5 transition-colors hover:text-red-400"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>
          ))
        ) : (
          <p className="text-muted-foreground/60 px-4 py-8 text-center text-sm">
            No API keys yet. Create one above for programmatic access.
          </p>
        )}
      </div>
    </section>
  );
}

function ConfigRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className="text-foreground/90 truncate font-mono text-xs" title={String(value)}>
        {value}
      </span>
    </div>
  );
}

function Bool({ value }) {
  return (
    <span className={`font-mono text-xs ${value ? "text-emerald-400/90" : "text-muted-foreground/60"}`}>
      {value ? "enabled" : "off"}
    </span>
  );
}

function InfoCard({ title, children }) {
  return (
    <div className="border-border bg-card/50 rounded-lg border p-4">
      <p className="text-muted-foreground/70 mb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
        {title}
      </p>
      <div className="divide-border divide-y">{children}</div>
    </div>
  );
}

function ConfigSection() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["settings-info"],
    queryFn: () => api.get("/settings/info"),
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-40 w-full rounded-lg" />)}
      </div>
    );
  }
  if (isError) return <ErrorState error={error} onRetry={refetch} />;

  const { providers: p, retrieval: r, features: f } = data;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <InfoCard title="Language model">
        <ConfigRow label="Provider" value={p.llm_provider} />
        <ConfigRow label="Model" value={p.llm_model ?? "(provider default)"} />
        <ConfigRow label="Temperature" value={p.llm_temperature} />
        {p.vertex_project && <ConfigRow label="Vertex project" value={p.vertex_project} />}
        {p.vertex_project && <ConfigRow label="Region" value={p.vertex_region} />}
      </InfoCard>

      <InfoCard title="Embeddings & rerank">
        <ConfigRow label="Embeddings" value={p.embedding_model} />
        <ConfigRow label="Sparse" value={p.sparse_embedding_model} />
        <ConfigRow label="Reranker" value={p.reranker_model} />
        <div className="flex items-center justify-between gap-4 py-1.5">
          <span className="text-muted-foreground text-sm">Rerank</span>
          <Bool value={p.rerank_enabled} />
        </div>
      </InfoCard>

      <InfoCard title="Retrieval">
        <ConfigRow label="Mode" value={r.retriever_mode} />
        <ConfigRow label="Retrieve N → top k" value={`${r.retrieve_top_n} → ${r.query_top_k}`} />
        <ConfigRow label="Max self-corrections" value={r.max_query_retries} />
        <ConfigRow label="Chunk size / overlap" value={`${r.chunk_size} / ${r.chunk_overlap}`} />
      </InfoCard>

      <InfoCard title="Features & observability">
        <div className="flex items-center justify-between gap-4 py-1.5">
          <span className="text-muted-foreground text-sm">Web search</span>
          <Bool value={f.web_search_configured} />
        </div>
        <div className="flex items-center justify-between gap-4 py-1.5">
          <span className="text-muted-foreground text-sm">Langfuse tracing</span>
          <Bool value={f.langfuse_configured} />
        </div>
        <ConfigRow label="Vector collection" value={data.qdrant_collection} />
        <ConfigRow label="Environment" value={`${data.environment} · v${data.app_version}`} />
      </InfoCard>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-base font-medium">Settings</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          API keys and the active backend configuration.
        </p>
      </div>

      <ApiKeysSection />

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="text-muted-foreground/60 size-4" aria-hidden />
          <h2 className="text-sm font-medium">Configuration</h2>
        </div>
        <p className="text-muted-foreground -mt-2 text-sm">
          Read-only. Set via environment variables on the backend — secrets are never shown here.
        </p>
        <ConfigSection />
      </section>
    </div>
  );
}
