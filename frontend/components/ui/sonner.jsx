"use client";

import { Toaster as Sonner } from "sonner";

/**
 * Global toast surface. Themed to the Sourcebound dark tokens (card surface,
 * hairline border) and tinted per type via classNames.
 */
export function Toaster(props) {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      style={{
        "--normal-bg": "var(--card)",
        "--normal-text": "var(--foreground)",
        "--normal-border": "var(--border)",
      }}
      toastOptions={{
        classNames: {
          toast: "font-sans text-sm rounded-lg shadow-lg",
          description: "text-muted-foreground",
          success: "!border-emerald-500/30",
          error: "!border-red-500/30",
        },
      }}
      {...props}
    />
  );
}
