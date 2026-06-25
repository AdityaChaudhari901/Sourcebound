"use client";

import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";

/** 👍/👎 on an assistant answer. Idempotent on the backend (re-rating updates). */
export function FeedbackButtons({ messageId }) {
  const [rating, setRating] = useState(null);
  const [busy, setBusy] = useState(false);

  const send = async (value) => {
    if (busy || !messageId) return;
    const previous = rating;
    setRating(value);
    setBusy(true);
    try {
      await api.post("/feedback", { message_id: messageId, rating: value });
      toast.success("Thanks for the feedback");
    } catch (err) {
      setRating(previous);
      toast.error(err?.message ?? "Couldn't save feedback");
    } finally {
      setBusy(false);
    }
  };

  const cls = (active) =>
    [
      "rounded-md p-1.5 transition-colors",
      active
        ? "bg-primary/15 text-primary"
        : "text-muted-foreground/60 hover:bg-sidebar-accent hover:text-foreground",
    ].join(" ");

  return (
    <div className="flex items-center gap-1">
      <button type="button" onClick={() => send("up")} className={cls(rating === "up")} aria-label="Helpful">
        <ThumbsUp className="size-3.5" />
      </button>
      <button type="button" onClick={() => send("down")} className={cls(rating === "down")} aria-label="Not helpful">
        <ThumbsDown className="size-3.5" />
      </button>
    </div>
  );
}
