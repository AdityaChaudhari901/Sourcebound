export default function Home() {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
      <span className="bg-primary/10 text-primary border-primary/20 mb-4 rounded-full border px-2.5 py-1 font-mono text-[11px] uppercase tracking-wider">
        shell ready
      </span>
      <h2 className="text-foreground text-lg font-medium">The Ask workspace lives here</h2>
      <p className="text-muted-foreground mt-2 max-w-md text-sm leading-relaxed">
        Connect your sources, then ask a question and get an answer with citations back to
        every source. Nothing to query yet — this is the app shell.
      </p>
    </div>
  );
}
