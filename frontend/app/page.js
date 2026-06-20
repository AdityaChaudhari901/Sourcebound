"use client";

import { useState } from "react";
import { AlertCircle, Loader2, Send } from "lucide-react";

import { streamSSE } from "@/lib/sse";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CitationList } from "@/components/citation-list";

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | streaming | done | error
  const [error, setError] = useState(null);

  const streaming = status === "streaming";

  const submit = async (event) => {
    event.preventDefault();
    const q = question.trim();
    if (!q || streaming) return;

    setAnswer("");
    setCitations([]);
    setError(null);
    setStatus("streaming");

    try {
      await streamSSE(
        "/query/stream",
        { question: q },
        {
          onEvent: (name, data) => {
            if (name === "token") {
              setAnswer((prev) => prev + (data.text ?? ""));
            } else if (name === "citations") {
              if (data.answer) setAnswer(data.answer);
              setCitations(data.citations ?? []);
            } else if (name === "error") {
              setError(data.message ?? "Stream error");
              setStatus("error");
            }
          },
        },
      );
      setStatus((prev) => (prev === "error" ? prev : "done"));
    } catch (err) {
      setError(err?.message ?? "Request failed.");
      setStatus("error");
    }
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
            ⌘↵ to send · answers stream live and cite their sources
          </span>
          <Button type="submit" disabled={!question.trim() || streaming}>
            {streaming ? (
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

      {status === "error" && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Couldn&apos;t get an answer</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* While streaming with no text yet, the model is thinking/retrieving. */}
      {streaming && !answer && (
        <p className="text-muted-foreground/70 flex items-center gap-2 text-sm">
          <Loader2 className="size-3.5 animate-spin" /> Retrieving sources and generating…
        </p>
      )}

      {answer && (
        <div className="space-y-5">
          <div className="border-border bg-card rounded-lg border p-4">
            <p className="text-muted-foreground/70 mb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
              Answer
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {answer}
              {streaming && (
                <span className="bg-primary ml-0.5 inline-block h-4 w-[2px] animate-pulse align-middle" />
              )}
            </p>
          </div>
          {status === "done" && <CitationList citations={citations} />}
        </div>
      )}

      {status === "idle" && (
        <p className="text-muted-foreground/60 max-w-md text-sm leading-relaxed">
          Answers are grounded only in your ingested sources and stream in as they
          generate. If nothing matches, you&apos;ll be told — not guessed at. Add sources
          on the Sources page first.
        </p>
      )}
    </div>
  );
}
