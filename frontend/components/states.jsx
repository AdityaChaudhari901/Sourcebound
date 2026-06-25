import Link from "next/link";
import { AlertCircle, Inbox, RefreshCw } from "lucide-react";

/** Consistent empty state: icon, message, optional CTA (link or button). */
export function EmptyState({ icon: Icon = Inbox, title, hint, href, cta, onAction, actionLabel }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <Icon className="text-muted-foreground/40 size-6" aria-hidden />
      <p className="text-foreground/80 text-sm">{title}</p>
      {hint && <p className="text-muted-foreground/60 max-w-sm text-xs">{hint}</p>}
      {href && (
        <Link href={href} className="text-primary mt-1 text-xs hover:underline">
          {cta}
        </Link>
      )}
      {onAction && (
        <button type="button" onClick={onAction} className="text-primary mt-1 text-xs hover:underline">
          {actionLabel}
        </button>
      )}
    </div>
  );
}

/** Consistent error state: explains the failure and offers a retry. */
export function ErrorState({ error, onRetry }) {
  return (
    <div
      role="alert"
      className="border-border flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-12 text-center"
    >
      <AlertCircle className="size-6 text-red-400/80" aria-hidden />
      <p className="text-foreground/80 text-sm">Couldn&apos;t load this.</p>
      <p className="text-muted-foreground/60 max-w-sm text-xs">
        {error?.message ?? "Something went wrong. The backend may be unreachable."}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="border-border hover:bg-sidebar-accent text-foreground/80 mt-1 inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition-colors"
        >
          <RefreshCw className="size-3" aria-hidden /> Retry
        </button>
      )}
    </div>
  );
}
