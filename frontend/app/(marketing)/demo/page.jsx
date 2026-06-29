"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { TOKEN_KEY } from "@/lib/auth";

/**
 * Zero-click demo entry. The landing's "View live demo" CTA points here (the
 * marketing group has no AuthProvider): we fetch a demo token, store it under the
 * same key the app reads, then hard-navigate into the app — which boots straight
 * into the read-only demo workspace.
 */
export default function DemoEntry() {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.post("/auth/demo", {});
        if (cancelled) return;
        localStorage.setItem(TOKEN_KEY, res.access_token);
        window.location.replace("/ask");
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#0b0b0d",
        color: "#ecebe5",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
      }}
    >
      <div style={{ textAlign: "center" }}>
        {failed ? (
          <>
            <p style={{ marginBottom: 12 }}>Couldn’t start the demo.</p>
            <a href="/ask" style={{ color: "#E8A24A" }}>
              Go to sign in →
            </a>
          </>
        ) : (
          <p style={{ color: "#a3a199" }}>Starting the demo…</p>
        )}
      </div>
    </main>
  );
}
