"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, Loader2, Send } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { CitationList } from "@/components/citation-list";

export default function AskPage() {
  const [question, setQuestion] = useState("");

  const mutation = useMutation({
    mutationFn: (q) => api.post("/query", { question: q }),
  });

  const submit = (event) => {
    event.preventDefault();
    const q = question.trim();
    if (!q || mutation.isPending) return;
    mutation.mutate(q);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <form onSubmit={submit} className="space-y-3">
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
          placeholder="Ask a question about your sources…"
          rows={3}
          className="resize-none"
        />
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground/60 font-mono text-[11px]">
            ⌘↵ to send · answers cite their sources
          </span>
          <Button type="submit" disabled={!question.trim() || mutation.isPending}>
            {mutation.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" /> Asking…
              </>
            ) : (
              <>
                <Send className="size-4" /> Ask
              </>
            )}
          </Button>
        </div>
      </form>

      {mutation.isPending && (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}

      {mutation.isError && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Couldn&apos;t get an answer</AlertTitle>
          <AlertDescription>{mutation.error?.message ?? "Request failed."}</AlertDescription>
        </Alert>
      )}

      {mutation.isSuccess && (
        <div className="space-y-5">
          <div className="border-border bg-card rounded-lg border p-4">
            <p className="text-muted-foreground/70 mb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
              Answer
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {mutation.data.answer}
            </p>
          </div>
          <CitationList citations={mutation.data.citations} />
        </div>
      )}

      {mutation.isIdle && (
        <p className="text-muted-foreground/60 max-w-md text-sm leading-relaxed">
          Answers are grounded only in your ingested sources. If nothing matches, you&apos;ll be
          told — not guessed at. Add sources on the Sources page first.
        </p>
      )}
    </div>
  );
}
