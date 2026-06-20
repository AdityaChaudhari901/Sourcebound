import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

/**
 * Bento tile: hairline border, near-black surface, generous padding, and a
 * restrained hover elevation (Linear/Vercel style). Becomes a link when `href`
 * is set (e.g. the Ask tile).
 */
export function Tile({ title, icon: Icon, href, headerRight, className = "", children }) {
  const Root = href ? Link : "div";
  const rootProps = href ? { href } : {};

  return (
    <Root
      {...rootProps}
      className={[
        "group border-border bg-card/60 relative flex flex-col overflow-hidden rounded-xl border p-5",
        "transition-[transform,border-color,background-color] duration-200",
        "hover:border-foreground/15 hover:bg-card hover:-translate-y-px",
        className,
      ].join(" ")}
    >
      {title && (
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="text-muted-foreground/60 size-3.5" aria-hidden />}
            <h3 className="text-muted-foreground/70 font-mono text-[10px] uppercase tracking-[0.18em]">
              {title}
            </h3>
          </div>
          {headerRight}
          {href && (
            <ArrowUpRight className="text-muted-foreground/40 group-hover:text-foreground size-4 transition-colors" />
          )}
        </div>
      )}
      <div className="min-h-0 flex-1">{children}</div>
    </Root>
  );
}
