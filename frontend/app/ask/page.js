"use client";

import { useRef, useState } from "react";
import { AlertCircle, Loader2, Plus, Send } from "lucide-react";

import { streamSSE } from "@/lib/sse";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CitationList } from "@/components/citation-list";
import { FeedbackButtons } from "@/components/feedback-buttons";

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState([]); // {role, content, citations?, messageId?}
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(null);
  const conversationId = useRef(null);

  const newConversation = () => {
    conversationId.current = null;
    setTurns([]);
    setStreamingAnswer("");
    setError(null);
  };

  const submit = async (event) => {
    event.preventDefault();
    const q = question.trim();
    if (!q || streaming) return;

    setQuestion("");
    setError(null);
    setTurns((t) => [...t, { role: "user", content: q }]);
    setStreamingAnswer("");
    setStreaming(true);

    try {
      await streamSSE(
        "/query/stream",
        { question: q, conversation_id: conversationId.current },
        {
          onEvent: (name, data) => {
            if (name === "token") {
              setStreamingAnswer((prev) => prev + (data.text ?? ""));
            } else if (name === "citations") {
              conversationId.current = data.conversation_id ?? conversationId.current;
              setTurns((t) => [
                ...t,
                {
                  role: "assistant",
                  content: data.answer ?? "",
                  citations: data.citations ?? [],
                  messageId: data.message_id,
                },
              ]);
              setStreamingAnswer("");
            } else if (name === "error") {
              setError(data.message ?? "Stream error");
            }
          },
        },
      );
    } catch (err) {
      setError(err?.message ?? "Request failed.");
    } finally {
      setStreaming(false);
    }
  };

  const empty = turns.length === 0 && !streaming;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col">
      {/* Thread */}
      <div className="flex-1 space-y-5 overflow-auto pb-4">
        {empty && (
          <p className="text-muted-foreground/60 max-w-md text-sm leading-relaxed">
            Ask a question about your sources. Answers stream in, cite their sources, and
            follow-ups keep the thread&apos;s context. If nothing matches, you&apos;ll be told —
            not guessed at.
          </p>
        )}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="space-y-1">
              <p className="text-muted-foreground/60 font-mono text-[10px] uppercase tracking-[0.18em]">
                You
              </p>
              <p className="text-foreground text-sm">{turn.content}</p>
            </div>
          ) : (
            <div key={i} className="space-y-3">
              <div className="border-border bg-card rounded-lg border p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">
                    Answer
                  </p>
                  {turn.messageId && <FeedbackButtons messageId={turn.messageId} />}
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{turn.content}</p>
              </div>
              <CitationList citations={turn.citations} />
            </div>
          ),
        )}

        {streaming && (
          <div className="border-border bg-card rounded-lg border p-4">
            <p className="text-muted-foreground/70 mb-2 font-mono text-[10px] uppercase tracking-[0.18em]">
              Answer
            </p>
            {streamingAnswer ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {streamingAnswer}
                <span className="bg-primary ml-0.5 inline-block h-4 w-[2px] animate-pulse align-middle" />
              </p>
            ) : (
              <p className="text-muted-foreground/70 flex items-center gap-2 text-sm">
                <Loader2 className="size-3.5 animate-spin" /> Retrieving and generating…
              </p>
            )}
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="size-4" />
            <AlertTitle>Couldn&apos;t get an answer</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Composer */}
      <form onSubmit={submit} className="border-border space-y-2 border-t pt-3">
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
          placeholder={turns.length ? "Ask a follow-up…" : "Ask a question about your sources…"}
          rows={2}
          className="resize-none"
        />
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={newConversation}
            disabled={streaming || empty}
            className="text-muted-foreground/60 hover:text-foreground flex items-center gap-1 font-mono text-[11px] disabled:opacity-40"
          >
            <Plus className="size-3" /> New conversation
          </button>
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
    </div>
  );
}
